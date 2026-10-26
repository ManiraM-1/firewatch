from shop.cart import Cart


def test_empty_cart_pays_shipping_only():
    assert Cart("asha").total() == 49


def test_add_merges_lines():
    cart = Cart("ravi")
    cart.add("tea", 120, 2)
    cart.add("tea", 120)
    assert cart.subtotal() == 360


def test_tax_by_category():
    cart = Cart("meena")
    cart.add("phone case", 100)
    cart.add("rice", 100, category="reduced")
    cart.add("milk", 100, category="exempt")
    assert cart.tax() == 23


def test_bulk_discount_applies_at_threshold():
    cart = Cart("dev")
    cart.add("headphones", 1000, category="exempt")
    assert cart.discount() == 100
    assert cart.total() == 900


def test_free_shipping_threshold():
    cart = Cart("kiran")
    cart.add("book", 499, category="exempt")
    assert cart.shipping() == 0


def test_carts_are_independent():
    first, second = Cart("a"), Cart("b")
    first.add("pen", 10)
    assert second.lines == []
