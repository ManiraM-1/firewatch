from firewatch.patcher import Snapshot, apply_edit, unified_diff


def edit(repo, file, search, replace, allow_tests=False):
    snap = Snapshot(repo)
    return apply_edit(str(repo), {"file": file, "search": search, "replace": replace}, snap, allow_tests), snap


def test_exact_match(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    result, snap = edit(tmp_path, "a.py", "y = 2", "y = 3")
    assert result.ok and result.reason == "exact match"
    assert (tmp_path / "a.py").read_text() == "x = 1\ny = 3\n"
    assert "-y = 2" in unified_diff(tmp_path, snap.originals)


def test_trailing_whitespace_tolerated(tmp_path):
    (tmp_path / "a.py").write_text("def f():   \n    return 1\n", encoding="utf-8")
    result, _ = edit(tmp_path, "a.py", "def f():\n    return 1", "def f():\n    return 2")
    assert result.ok
    assert "return 2" in (tmp_path / "a.py").read_text()


def test_wrong_indentation_is_reindented(tmp_path):
    (tmp_path / "a.py").write_text("class A:\n    def f(self):\n        return 1\n", encoding="utf-8")
    result, _ = edit(tmp_path, "a.py", "def f(self):\n    return 1", "def f(self):\n    return 2")
    assert result.ok and result.reason == "matched ignoring indentation"
    assert (tmp_path / "a.py").read_text() == "class A:\n    def f(self):\n        return 2\n"


def test_ambiguous_search_rejected(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\nx = 1\n", encoding="utf-8")
    result, _ = edit(tmp_path, "a.py", "x = 1", "x = 2")
    assert not result.ok and "2 places" in result.reason


def test_missing_search_rejected(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    result, _ = edit(tmp_path, "a.py", "y = 1", "y = 2")
    assert not result.ok and "not found" in result.reason


def test_test_files_are_protected(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("assert 1 == 2\n", encoding="utf-8")
    result, _ = edit(tmp_path, "tests/test_a.py", "assert 1 == 2", "assert True")
    assert not result.ok and "tests is disabled" in result.reason
    allowed, _ = edit(tmp_path, "tests/test_a.py", "assert 1 == 2", "assert True", allow_tests=True)
    assert allowed.ok


def test_path_traversal_blocked(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (tmp_path / "secret.py").write_text("x = 1\n", encoding="utf-8")
    result, _ = edit(repo, "../secret.py", "x = 1", "x = 2")
    assert not result.ok
    assert (tmp_path / "secret.py").read_text() == "x = 1\n"


def test_crlf_preserved(tmp_path):
    (tmp_path / "a.py").write_bytes(b"x = 1\r\ny = 2\r\n")
    result, _ = edit(tmp_path, "a.py", "y = 2", "y = 3")
    assert result.ok
    assert (tmp_path / "a.py").read_bytes() == b"x = 1\r\ny = 3\r\n"


def test_snapshot_restore(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    _, snap = edit(tmp_path, "a.py", "x = 1", "x = 2")
    snap.restore()
    assert (tmp_path / "a.py").read_text() == "x = 1\n"
