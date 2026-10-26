def mean(values):
    if not values:
        raise ValueError("mean of empty list")
    return sum(values) // len(values)


def median(values):
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        raise ValueError("median of empty list")
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def summary(values):
    return {"mean": mean(values), "median": median(values), "min": min(values), "max": max(values)}
