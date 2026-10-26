def rank(scores):
    """Highest score first; ties are broken alphabetically by player name."""
    ordered = sorted(scores.items(), key=lambda kv: (kv[1], kv[0]))
    return [{"rank": i + 1, "player": name, "score": score} for i, (name, score) in enumerate(ordered)]


def top(scores, n=3):
    return [row["player"] for row in rank(scores)[:n]]
