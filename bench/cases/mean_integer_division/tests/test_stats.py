import pytest

from stats import mean, median, summary


def test_mean_keeps_fraction():
    assert mean([1, 2]) == 1.5


def test_median_even():
    assert median([4, 1, 3, 2]) == 2.5


def test_summary():
    assert summary([2, 3, 7]) == {"mean": 4, "median": 3, "min": 2, "max": 7}
    assert summary([1, 2, 3, 5])["mean"] == 2.75


def test_empty_mean_raises():
    with pytest.raises(ValueError):
        mean([])
