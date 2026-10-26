from datetime import timedelta


def is_weekend(day):
    return day.weekday() >= 6


def next_business_day(day):
    candidate = day + timedelta(days=1)
    while is_weekend(candidate):
        candidate += timedelta(days=1)
    return candidate


def business_days_between(start, end):
    count = 0
    current = start
    while current < end:
        if not is_weekend(current):
            count += 1
        current += timedelta(days=1)
    return count
