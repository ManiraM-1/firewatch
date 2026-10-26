def parse_port(value):
    try:
        port = int(str(value).strip())
    except ValueError:
        raise Exception(f"invalid port: {value!r}")
    if not 0 < port < 65536:
        raise Exception(f"port out of range: {port}")
    return port


def parse_address(text):
    host, _, port = text.rpartition(":")
    if not host:
        raise ValueError(f"missing host in {text!r}")
    return host, parse_port(port)
