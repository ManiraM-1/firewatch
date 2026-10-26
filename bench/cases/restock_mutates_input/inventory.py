def restock(stock, deliveries):
    """Returns a new stock mapping; the input is left unchanged."""
    for sku, qty in deliveries.items():
        stock[sku] = stock.get(sku, 0) + qty
    return stock


def low_stock(stock, threshold=5):
    return sorted(sku for sku, qty in stock.items() if qty < threshold)
