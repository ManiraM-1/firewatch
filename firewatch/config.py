import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    model: str
    api_key: str = ""
    native_ollama: bool = False
    num_ctx: int = 16384


@dataclass
class Settings:
    providers: list = field(default_factory=list)
    max_attempts: int = 3
    temperature: float = 0.2
    retry_temperatures: list = field(default_factory=lambda: [0.2, 0.5, 0.8])
    request_timeout: int = 300
    test_timeout: int = 600
    allow_test_edits: bool = False
    context_char_budget: int = 24000


def _env(name, default=""):
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _provider(name):
    if name == "ollama":
        return ProviderConfig(
            name="ollama",
            base_url=_env("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            model=_env("OLLAMA_MODEL", "qwen2.5-coder:7b"),
            api_key="",
            native_ollama=True,
            num_ctx=int(_env("OLLAMA_NUM_CTX", "16384")),
        )
    if name == "remote":
        base_url = _env("LLM_BASE_URL")
        model = _env("LLM_MODEL")
        if not base_url or not model:
            return None
        return ProviderConfig(
            name="remote",
            base_url=base_url,
            model=model,
            api_key=_env("LLM_API_KEY"),
        )
    raise ValueError(f"Unknown provider '{name}'. Use 'ollama' or 'remote'.")


def load_settings(env_file=".env"):
    if load_dotenv and env_file and os.path.exists(env_file):
        load_dotenv(env_file, override=False)

    order = [p.strip() for p in _env("FIREWATCH_PROVIDERS", "ollama,remote").split(",") if p.strip()]
    providers = [p for p in (_provider(name) for name in order) if p is not None]

    return Settings(
        providers=providers,
        max_attempts=int(_env("FIREWATCH_MAX_ATTEMPTS", "3")),
        temperature=float(_env("FIREWATCH_TEMPERATURE", "0.2")),
        retry_temperatures=[float(t) for t in _env("FIREWATCH_RETRY_TEMPERATURES", "0.2,0.5,0.8").split(",") if t.strip()],
        request_timeout=int(_env("FIREWATCH_REQUEST_TIMEOUT", "300")),
        test_timeout=int(_env("FIREWATCH_TEST_TIMEOUT", "600")),
        allow_test_edits=_env("FIREWATCH_ALLOW_TEST_EDITS", "false").lower() == "true",
        context_char_budget=int(_env("FIREWATCH_CONTEXT_CHARS", "24000")),
    )
