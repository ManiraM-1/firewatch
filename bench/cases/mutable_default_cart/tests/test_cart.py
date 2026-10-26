from cart import Cart


def test_add_merges_same_sku():
    cart = Cart("asha")
    cart.add("tea", 2)
    cart.add("tea")
    assert cart.count() == 3


def test_carts_are_independent():
    first = Cart("ravi")
    second = Cart("meena")
    first.add("coffee")
    assert second.count() == 0


def test_existing_items_are_kept():
    cart = Cart("dev", [{"sku": "milk", "qty": 1}])
    cart.add("milk")
    assert cart.count() == 2
