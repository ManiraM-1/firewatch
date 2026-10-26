import json
import time
import urllib.error
import urllib.request


class LLMError(Exception):
    pass


def _send(provider, url, body, timeout):
    headers = {"Content-Type": "application/json"}
    if provider.api_key:
        headers["Authorization"] = f"Bearer {provider.api_key}"
    request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise LLMError(f"{provider.name} returned HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise LLMError(f"{provider.name} unreachable at {url}: {exc}") from exc


def ollama_native_url(base_url):
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    return base + "/api/chat"


def _post_ollama(provider, messages, temperature, timeout, json_mode=True):
    body = {
        "model": provider.model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_ctx": getattr(provider, "num_ctx", 16384)},
    }
    if json_mode:
        body["format"] = "json"
    payload = _send(provider, ollama_native_url(provider.base_url), body, timeout)
    try:
        return payload["message"]["content"] or ""
    except (KeyError, TypeError) as exc:
        raise LLMError(f"{provider.name} returned an unexpected payload: {str(payload)[:300]}") from exc


def _post_chat(provider, messages, temperature, timeout, json_mode=True):
    if getattr(provider, "native_ollama", False):
        return _post_ollama(provider, messages, temperature, timeout, json_mode)
    body = {"model": provider.model, "messages": messages, "temperature": temperature, "stream": False}
    payload = _send(provider, provider.base_url.rstrip("/") + "/chat/completions", body, timeout)
    try:
        return payload["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"{provider.name} returned an unexpected payload: {str(payload)[:300]}") from exc


class LLMClient:
    def __init__(self, providers, temperature=0.2, timeout=300):
        if not providers:
            raise LLMError(
                "No model provider configured. Set FIREWATCH_PROVIDERS and the matching "
                "OLLAMA_* or LLM_* variables in .env."
            )
        self.providers = providers
        self.temperature = temperature
        self.timeout = timeout
        self.last_provider = None

    def describe(self):
        return ", ".join(f"{p.name}:{p.model}" for p in self.providers)

    def complete(self, messages):
        errors = []
        for provider in self.providers:
            started = time.monotonic()
            try:
                text = _post_chat(provider, messages, self.temperature, self.timeout)
            except LLMError as exc:
                errors.append(str(exc))
                continue
            self.last_provider = provider
            return text, provider, time.monotonic() - started
        raise LLMError("All providers failed:\n- " + "\n- ".join(errors))


class ScriptedLLM:
    def __init__(self, responses, name="scripted", model="scripted"):
        self.responses = list(responses)
        self.calls = []
        self.last_provider = type("P", (), {"name": name, "model": model})()

    def describe(self):
        return f"{self.last_provider.name}:{self.last_provider.model}"

    def complete(self, messages):
        self.calls.append(messages)
        if not self.responses:
            raise LLMError("ScriptedLLM ran out of responses")
        response = self.responses.pop(0)
        if callable(response):
            response = response(messages)
        return response, self.last_provider, 0.0
