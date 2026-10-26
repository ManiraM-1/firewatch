import pytest

from retry import RetryError, retry


def flaky(failures):
    calls = {"n": 0}

    def func():
        calls["n"] += 1
        if calls["n"] <= failures:
            raise ConnectionError("boom")
        return "ok"

    return func, calls


def test_succeeds_on_last_attempt():
    func, calls = flaky(2)
    assert retry(func, attempts=3, sleep=lambda _: None) == "ok"
    assert calls["n"] == 3


def test_gives_up_after_all_attempts():
    func, calls = flaky(10)
    with pytest.raises(RetryError):
        retry(func, attempts=4, sleep=lambda _: None)
    assert calls["n"] == 4
