from datetime import date

from calendar_utils import business_days_between, is_weekend, next_business_day


def test_saturday_is_weekend():
    assert is_weekend(date(2026, 10, 31))


def test_friday_rolls_to_monday():
    assert next_business_day(date(2026, 10, 30)) == date(2026, 11, 2)


def test_business_days_in_a_week():
    assert business_days_between(date(2026, 10, 26), date(2026, 11, 2)) == 5
