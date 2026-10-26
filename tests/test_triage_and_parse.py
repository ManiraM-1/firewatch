from firewatch.context import build_context
from firewatch.fixer import parse_proposal
from firewatch.triage import summary_counts, triage_log
from firewatch.verifier import run_tests

GH_LOG = """2026-10-26T08:00:01.1234567Z ============================= FAILURES =============================
2026-10-26T08:00:01.1234567Z ____________________________ test_standard_tax ____________________________
2026-10-26T08:00:01.1234567Z /home/runner/work/shop/shop/tests/test_checkout.py:5: in test_standard_tax
2026-10-26T08:00:01.1234567Z     assert tax_amount(100) == 18
2026-10-26T08:00:01.1234567Z E   assert 1800 == 18
2026-10-26T08:00:01.1234567Z =========================== short test summary info ============================
2026-10-26T08:00:01.1234567Z FAILED tests/test_checkout.py::test_standard_tax - assert 1800 == 18
2026-10-26T08:00:01.1234567Z ========================= 1 failed, 3 passed in 0.12s ==========================
"""


def test_github_log_is_cleaned_and_paths_normalized(case_repo):
    repo, _ = case_repo("tax_rate_units")
    triage = triage_log(GH_LOG, repo)
    assert "2026-10-26T" not in triage.excerpt
    assert "assert 1800 == 18" in triage.excerpt
    assert any(ref.path == "tests/test_checkout.py" and ref.line == 5 for ref in triage.file_refs)
    assert triage.failing_tests == ["tests/test_checkout.py::test_standard_tax"]
    assert triage.failed_count == 1


def test_summary_counts():
    assert summary_counts("=== 2 failed, 5 passed, 1 error in 0.3s ===") == {"failed": 2, "passed": 5, "error": 1}
    assert summary_counts("no summary here") == {}


def test_context_follows_imports_across_files(case_repo, settings):
    repo, _ = case_repo("tax_rate_units")
    run = run_tests(str(repo), "python -m pytest -q -p no:cacheprovider", 120)
    triage = triage_log(run.output, repo)
    context = build_context(repo, triage, char_budget=24000)
    paths = [f.path for f in context.files]
    assert "checkout.py" in paths
    assert "tax.py" in paths
    assert paths.index("checkout.py") < paths.index("tests/test_checkout.py")


def test_import_error_case_finds_both_modules(case_repo):
    repo, _ = case_repo("renamed_import")
    run = run_tests(str(repo), "python -m pytest -q -p no:cacheprovider", 120)
    triage = triage_log(run.output, repo)
    paths = [f.path for f in build_context(repo, triage).files]
    assert "articles.py" in paths and "textutils.py" in paths


def test_parse_fenced_json_with_think_block():
    raw = '<think>hmm {"not": "this"}</think>\n```json\n{"diagnosis": "d", "edits": [{"file": "a.py", "search": "x", "replace": "y"}]}\n```'
    proposal = parse_proposal(raw)
    assert proposal.diagnosis == "d"
    assert proposal.edits == [{"file": "a.py", "search": "x", "replace": "y"}]


def test_parse_tolerates_trailing_commas_and_bare_json():
    raw = 'Sure! {"diagnosis": "d", "edits": [{"file": "a.py", "search": "x", "replace": "y"},],}'
    assert parse_proposal(raw).edits[0]["file"] == "a.py"


def test_parse_reports_missing_json():
    proposal = parse_proposal("I think the bug is in line 4.")
    assert proposal.parse_error and not proposal.edits


JAVA_LOG = """[ERROR] Tests run: 3, Failures: 1, Errors: 0
[ERROR] totalAppliesDiscount(com.shop.CartTest)  Time elapsed: 0.01 s  <<< FAILURE!
org.opentest4j.AssertionFailedError: expected: <900> but was: <1000>
	at org.junit.jupiter.api.AssertionUtils.fail(AssertionUtils.java:55)
	at com.shop.Cart.discount(Cart.java:42)
	at com.shop.CartTest.totalAppliesDiscount(CartTest.java:18)
"""


def test_java_stack_trace_filenames_resolve_to_repo_paths(tmp_path):
    src = tmp_path / "src" / "main" / "java" / "com" / "shop"
    test = tmp_path / "src" / "test" / "java" / "com" / "shop"
    src.mkdir(parents=True)
    test.mkdir(parents=True)
    (src / "Cart.java").write_text("class Cart {}")
    (test / "CartTest.java").write_text("class CartTest {}")
    refs = {(r.path, r.line) for r in triage_log(JAVA_LOG, tmp_path).file_refs}
    assert ("src/main/java/com/shop/Cart.java", 42) in refs
    assert ("src/test/java/com/shop/CartTest.java", 18) in refs
    assert not any("AssertionUtils" in path for path, _ in refs)


def test_absolute_paths_outside_repo_are_ignored(tmp_path):
    (tmp_path / "decoder.py").write_text("x = 1")
    log = 'File "C:/Python312/Lib/json/decoder.py", line 3, in decode\nValueError: bad'
    assert triage_log(log, tmp_path).file_refs == []
