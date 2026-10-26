from pricing import discount, shipping, total


def test_discount_starts_at_threshold():
    assert discount(1000) == 100


def test_no_discount_below_threshold():
    assert discount(999.99) == 0


def test_total_with_discount_and_free_shipping():
    assert total([{"price": 500, "qty": 2}]) == 900


def test_shipping_charged_below_minimum():
    assert shipping(498) == 49
