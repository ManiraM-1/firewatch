import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from firewatch.config import ProviderConfig
from firewatch.llm import LLMClient, LLMError, ollama_native_url


class FakeServer:
    def __init__(self):
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append((self.path, body, self.headers.get("Authorization")))
                if self.path == "/api/chat":
                    reply = {"message": {"role": "assistant", "content": '{"diagnosis": "native"}'}}
                else:
                    reply = {"choices": [{"message": {"content": "compatible"}}]}
                data = json.dumps(reply).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


@pytest.fixture
def server():
    fake = FakeServer()
    yield fake
    fake.close()


def test_native_url():
    assert ollama_native_url("http://localhost:11434/v1") == "http://localhost:11434/api/chat"
    assert ollama_native_url("http://localhost:11434/") == "http://localhost:11434/api/chat"


def test_ollama_uses_native_api_with_context_and_json(server):
    provider = ProviderConfig("ollama", server.url + "/v1", "qwen2.5-coder:7b", native_ollama=True, num_ctx=12288)
    text, used, _ = LLMClient([provider], 0.2, 5).complete([{"role": "user", "content": "hi"}])
    path, body, _auth = server.requests[0]
    assert path == "/api/chat"
    assert body["options"]["num_ctx"] == 12288
    assert body["format"] == "json"
    assert body["stream"] is False
    assert text == '{"diagnosis": "native"}' and used.name == "ollama"


def test_remote_uses_openai_compatible_api_with_key(server):
    provider = ProviderConfig("remote", server.url + "/v1", "some-open-model", api_key="secret")
    text, _, _ = LLMClient([provider], 0.2, 5).complete([{"role": "user", "content": "hi"}])
    path, body, auth = server.requests[0]
    assert path == "/v1/chat/completions"
    assert auth == "Bearer secret"
    assert text == "compatible"


def test_falls_back_when_first_provider_is_down(server):
    down = ProviderConfig("ollama", "http://127.0.0.1:9/v1", "m", native_ollama=True)
    up = ProviderConfig("remote", server.url + "/v1", "m")
    client = LLMClient([down, up], 0.2, 5)
    text, used, _ = client.complete([{"role": "user", "content": "hi"}])
    assert used.name == "remote" and text == "compatible"


def test_all_down_raises():
    down = ProviderConfig("ollama", "http://127.0.0.1:9/v1", "m", native_ollama=True)
    with pytest.raises(LLMError, match="All providers failed"):
        LLMClient([down], 0.2, 2).complete([{"role": "user", "content": "hi"}])


class FlakyServer:
    def __init__(self, codes):
        self.codes = list(codes)
        self.hits = 0
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                outer.hits += 1
                code = outer.codes.pop(0) if outer.codes else 200
                if code != 200:
                    data = b'{"error": "slow down"}'
                    self.send_response(code)
                    self.send_header("Retry-After", "7")
                else:
                    data = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
                    self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/v1"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()


def test_rate_limit_waits_and_retries(monkeypatch):
    import firewatch.llm as llm_module

    waits = []
    monkeypatch.setattr(llm_module, "_sleep", waits.append)
    server = FlakyServer([429, 429])
    try:
        text, _, _ = LLMClient([ProviderConfig("remote", server.url, "m")], 0.2, 5).complete([{"role": "user", "content": "hi"}])
    finally:
        server.httpd.shutdown()
    assert text == "ok"
    assert server.hits == 3
    assert waits == [7.0, 7.0]


def test_auth_errors_are_not_retried(monkeypatch):
    import firewatch.llm as llm_module

    monkeypatch.setattr(llm_module, "_sleep", lambda _s: None)
    server = FlakyServer([401])
    try:
        with pytest.raises(LLMError, match="HTTP 401"):
            LLMClient([ProviderConfig("remote", server.url, "m")], 0.2, 5).complete([{"role": "user", "content": "hi"}])
    finally:
        server.httpd.shutdown()
    assert server.hits == 1


def test_requests_identify_as_firewatch(monkeypatch):
    import io

    import firewatch.llm as llm_module

    seen = {}

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=None):
        seen.update({k.lower(): v for k, v in request.header_items()})
        return Response(json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode())

    monkeypatch.setattr(llm_module.urllib.request, "urlopen", fake_urlopen)
    LLMClient([ProviderConfig("remote", "https://api.example.com/v1", "m", api_key="k")], 0.2, 5).complete(
        [{"role": "user", "content": "hi"}]
    )
    assert seen["user-agent"].startswith("firewatch/")
    assert "urllib" not in seen["user-agent"].lower()
    assert seen["authorization"] == "Bearer k"
