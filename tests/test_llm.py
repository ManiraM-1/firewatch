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
