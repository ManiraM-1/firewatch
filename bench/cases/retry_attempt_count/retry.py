import time


class RetryError(Exception):
    pass


def retry(func, attempts=3, delay=0.0, sleep=time.sleep):
    last = None
    for attempt in range(1, attempts):
        try:
            return func()
        except Exception as exc:
            last = exc
            if attempt < attempts:
                sleep(delay)
    raise RetryError(f"failed after {attempts} attempts") from last
