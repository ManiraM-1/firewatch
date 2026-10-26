from tax import rate_for


def tax_amount(price, category="standard"):
    return round(price * rate_for(category), 2)


def price_with_tax(price, category="standard"):
    return round(price + tax_amount(price, category), 2)
