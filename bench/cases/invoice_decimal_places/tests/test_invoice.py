from invoice import format_amount, render


def test_two_decimals():
    assert format_amount(1180) == "Rs 1,180.00"


def test_usd():
    assert format_amount(12.5, "USD") == "$12.50"


def test_render():
    text = render([{"name": "Pen", "price": 10, "qty": 3}], "USD")
    assert text.splitlines() == ["Pen: $35.40", "Total: $35.40"]
