GST_RATES = {"standard": 18, "reduced": 5, "exempt": 0}


def rate_for(category):
    """Returns the GST rate for a category as a percentage, e.g. 18 for 18%."""
    return GST_RATES.get(category, GST_RATES["standard"])
