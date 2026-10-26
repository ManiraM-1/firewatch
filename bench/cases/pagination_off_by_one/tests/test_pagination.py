import pytest

from pagination import paginate


def test_first_page():
    page = paginate(list(range(25)), page=1, size=10)
    assert page.items == list(range(10))
    assert page.has_next


def test_last_page_is_partial():
    page = paginate(list(range(25)), page=3, size=10)
    assert page.items == [20, 21, 22, 23, 24]
    assert not page.has_next


def test_page_count():
    assert paginate(list(range(25)), size=10).pages == 3


def test_rejects_page_zero():
    with pytest.raises(ValueError):
        paginate([1, 2, 3], page=0)
