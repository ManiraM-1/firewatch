from dataclasses import dataclass


@dataclass
class Page:
    items: list
    page: int
    size: int
    total: int

    @property
    def pages(self):
        return max(1, -(-self.total // self.size))

    @property
    def has_next(self):
        return self.page < self.pages


def paginate(items, page=1, size=10):
    if page < 1:
        raise ValueError("page starts at 1")
    if size < 1:
        raise ValueError("size must be positive")
    start = page * size
    end = start + size
    return Page(items=items[start:end], page=page, size=size, total=len(items))
