class Cart:
    def __init__(self, owner, items=[]):
        self.owner = owner
        self.items = items

    def add(self, sku, qty=1):
        for item in self.items:
            if item["sku"] == sku:
                item["qty"] += qty
                return
        self.items.append({"sku": sku, "qty": qty})

    def count(self):
        return sum(item["qty"] for item in self.items)
