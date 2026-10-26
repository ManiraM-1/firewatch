from .tax import rate_for

FREE_SHIPPING_MIN = 499
SHIPPING_FEE = 49
BULK_DISCOUNT_MIN = 1000
BULK_DISCOUNT_RATE = 0.1


class Cart:
    def __init__(self, owner, lines=None):
        self.owner = owner
        self.lines = list(lines) if lines else []

    def add(self, name, price, qty=1, category="standard"):
        for line in self.lines:
            if line["name"] == name:
                line["qty"] += qty
                return
        self.lines.append({"name": name, "price": price, "qty": qty, "category": category})

    def subtotal(self):
        return round(sum(line["price"] * line["qty"] for line in self.lines), 2)

    def tax(self):
        return round(sum(line["price"] * line["qty"] * rate_for(line["category"]) / 100 for line in self.lines), 2)

    def discount(self):
        amount = self.subtotal()
        if amount >= BULK_DISCOUNT_MIN:
            return round(amount * BULK_DISCOUNT_RATE, 2)
        return 0

    def shipping(self):
        return 0 if self.subtotal() >= FREE_SHIPPING_MIN else SHIPPING_FEE

    def total(self):
        return round(self.subtotal() - self.discount() + self.tax() + self.shipping(), 2)
