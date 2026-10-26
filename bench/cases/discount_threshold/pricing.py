FREE_SHIPPING_MIN = 499
BULK_DISCOUNT_MIN = 1000
BULK_DISCOUNT_RATE = 0.1


def subtotal(lines):
    return sum(line["price"] * line["qty"] for line in lines)


def shipping(amount):
    return 0 if amount >= FREE_SHIPPING_MIN else 49


def discount(amount):
    """Orders of 1000 or more get 10% off."""
    if amount > BULK_DISCOUNT_MIN:
        return round(amount * BULK_DISCOUNT_RATE, 2)
    return 0


def total(lines):
    amount = subtotal(lines)
    return round(amount - discount(amount) + shipping(amount), 2)
