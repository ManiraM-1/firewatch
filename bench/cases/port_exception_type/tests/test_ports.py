import pytest

from ports import parse_address, parse_port


def test_valid():
    assert parse_port(" 8080 ") == 8080
    assert parse_address("db.local:5432") == ("db.local", 5432)


def test_non_numeric_is_value_error():
    with pytest.raises(ValueError):
        parse_port("http")


def test_out_of_range_is_value_error():
    with pytest.raises(ValueError):
        parse_port(70000)


def test_missing_host():
    with pytest.raises(ValueError):
        parse_address(":80")
