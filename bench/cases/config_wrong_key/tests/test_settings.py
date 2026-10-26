from settings import http_options, load


def test_defaults():
    options = http_options(load())
    assert options == {"base_url": "http://localhost:8080", "timeout": 30, "retries": 3}


def test_overrides():
    options = http_options(load('{"host": "api.local", "timeout": 5}'))
    assert options["base_url"] == "http://api.local:8080"
    assert options["timeout"] == 5
