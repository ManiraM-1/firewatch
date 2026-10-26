import json

DEFAULTS = {"host": "localhost", "port": 8080, "timeout": 30, "retries": 3}


def load(text=None):
    data = dict(DEFAULTS)
    if text:
        data.update(json.loads(text))
    return data


def http_options(config):
    return {
        "base_url": f"http://{config['host']}:{config['port']}",
        "timeout": config["timeout_seconds"],
        "retries": config["retries"],
    }
