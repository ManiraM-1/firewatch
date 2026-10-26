from users import display_name, full_name, initials


def test_full_name_with_middle():
    assert full_name({"first": "Ada", "middle": "King", "last": "Lovelace"}) == "Ada King Lovelace"


def test_full_name_without_middle():
    assert full_name({"first": "Alan", "last": "Turing"}) == "Alan Turing"


def test_middle_name_explicitly_none():
    assert full_name({"first": "Grace", "middle": None, "last": "Hopper"}) == "Grace Hopper"


def test_initials_and_display():
    user = {"first": "linus", "last": "torvalds", "nickname": "Linus"}
    assert initials(user) == "LT"
    assert display_name(user) == "Linus (linus torvalds)"
