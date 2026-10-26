from leaderboard import rank, top


def test_highest_first():
    assert top({"a": 10, "b": 30, "c": 20}, 2) == ["b", "c"]


def test_ties_alphabetical():
    assert top({"zed": 50, "amy": 50, "kim": 40}) == ["amy", "zed", "kim"]


def test_rank_numbers():
    rows = rank({"x": 1, "y": 2})
    assert rows[0] == {"rank": 1, "player": "y", "score": 2}
