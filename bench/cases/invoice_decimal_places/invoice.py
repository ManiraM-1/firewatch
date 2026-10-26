SYMBOLS = {"INR": "Rs ", "USD": "$"}


def format_amount(amount, currency="INR"):
    symbol = SYMBOLS.get(currency, currency + " ")
    return f"{symbol}{amount:,.1f}"


def line_total(price, qty, tax_rate=0.18):
    return round(price * qty * (1 + tax_rate), 2)


def render(lines, currency="INR"):
    rows = [f"{l['name']}: {format_amount(line_total(l['price'], l['qty']), currency)}" for l in lines]
    grand = sum(line_total(l["price"], l["qty"]) for l in lines)
    rows.append(f"Total: {format_amount(grand, currency)}")
    return "\n".join(rows)
