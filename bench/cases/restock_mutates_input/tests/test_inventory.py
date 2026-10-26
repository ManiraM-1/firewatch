from inventory import low_stock, restock


def test_restock_adds():
    assert restock({"a": 1}, {"a": 2, "b": 4}) == {"a": 3, "b": 4}


def test_restock_does_not_mutate():
    original = {"a": 1}
    restock(original, {"a": 5})
    assert original == {"a": 1}


def test_low_stock():
    assert low_stock({"a": 1, "b": 9, "c": 4}) == ["a", "c"]
