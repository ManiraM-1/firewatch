from tax import rate_for


def test_rates_are_percentages():
    assert rate_for("standard") == 18
    assert rate_for("unknown") == 18
