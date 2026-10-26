from checkout import price_with_tax, tax_amount


def test_standard_tax():
    assert tax_amount(100) == 18


def test_reduced_total():
    assert price_with_tax(200, "reduced") == 210


def test_exempt():
    assert price_with_tax(99, "exempt") == 99
