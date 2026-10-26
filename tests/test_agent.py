from pathlib import Path

from conftest import CASES, as_reply

from firewatch.agent import run_agent
from firewatch.bench import run_benchmark
from firewatch.llm import ScriptedLLM
from firewatch.report import render_markdown

TEST_CMD = "python -m pytest -q -p no:cacheprovider"


def test_fixes_on_first_attempt(case_repo, settings):
    repo, solution = case_repo("pagination_off_by_one")
    llm = ScriptedLLM([as_reply(solution, "start index uses page instead of page - 1")])
    result = run_agent(str(repo), TEST_CMD, llm, settings)
    assert result.status == "fixed"
    assert len(result.attempts) == 1
    assert result.changed_files == ["pagination.py"]
    assert "(page - 1) * size" in (repo / "pagination.py").read_text()


def test_wrong_attempt_is_reverted_then_fixed(case_repo, settings):
    repo, solution = case_repo("discount_threshold")
    wrong = [{"file": "pricing.py", "search": "BULK_DISCOUNT_RATE = 0.1", "replace": "BULK_DISCOUNT_RATE = 0.2"}]
    llm = ScriptedLLM([as_reply(wrong, "rate too low"), as_reply(solution, "threshold comparison is strict")])
    result = run_agent(str(repo), TEST_CMD, llm, settings)
    assert result.status == "fixed"
    assert [a.kept for a in result.attempts] == [False, True]
    assert "BULK_DISCOUNT_RATE = 0.1" in (repo / "pricing.py").read_text()
    second_prompt = llm.calls[1][1]["content"]
    assert "Previous attempts" in second_prompt and "BULK_DISCOUNT_RATE = 0.2" in second_prompt


def test_partial_progress_is_kept(case_repo, settings):
    repo, solution = case_repo("port_exception_type")
    llm = ScriptedLLM([as_reply(solution[:1], "first raise"), as_reply(solution[1:], "second raise")])
    result = run_agent(str(repo), TEST_CMD, llm, settings)
    assert result.status == "fixed"
    assert result.attempts[0].kept and result.attempts[0].failed_after < result.attempts[0].failed_before
    assert "Exception(" not in (repo / "ports.py").read_text()


def test_gives_up_and_restores_files(case_repo, settings):
    repo, _ = case_repo("weekend_check")
    before = (repo / "calendar_utils.py").read_text()
    bad = [{"file": "calendar_utils.py", "search": "candidate = day + timedelta(days=1)", "replace": "candidate = day + timedelta(days=2)"}]
    llm = ScriptedLLM([as_reply(bad)] * 3)
    result = run_agent(str(repo), TEST_CMD, llm, settings)
    assert result.status == "not_fixed"
    assert len(result.attempts) == 3
    assert (repo / "calendar_utils.py").read_text() == before


def test_refuses_to_edit_tests(case_repo, settings):
    repo, solution = case_repo("mean_integer_division")
    cheat = [{"file": "tests/test_stats.py", "search": "    assert mean([1, 2]) == 1.5", "replace": "    assert mean([1, 2]) == 1"}]
    llm = ScriptedLLM([as_reply(cheat), as_reply(solution)])
    result = run_agent(str(repo), TEST_CMD, llm, settings)
    assert result.status == "fixed"
    assert "editing tests is disabled" in result.attempts[0].edit_errors[0]
    assert "== 1.5" in (repo / "tests" / "test_stats.py").read_text()


def test_unparseable_reply_counts_as_attempt(case_repo, settings):
    repo, solution = case_repo("config_wrong_key")
    llm = ScriptedLLM(["The bug is the timeout key.", as_reply(solution)])
    result = run_agent(str(repo), TEST_CMD, llm, settings)
    assert result.status == "fixed" and len(result.attempts) == 2


def test_passing_repo_needs_no_fix(case_repo, settings):
    repo, solution = case_repo("leaderboard_order")
    llm = ScriptedLLM([as_reply(solution)])
    run_agent(str(repo), TEST_CMD, llm, settings)
    again = run_agent(str(repo), TEST_CMD, ScriptedLLM([]), settings)
    assert again.status == "no_failure"


def test_report_renders(case_repo, settings):
    repo, solution = case_repo("retry_attempt_count")
    result = run_agent(str(repo), TEST_CMD, ScriptedLLM([as_reply(solution, "loop stops one short")]), settings)
    markdown = render_markdown(result, "https://github.com/x/y/actions/runs/1")
    assert "loop stops one short" in markdown and "```diff" in markdown and "Failed run" in markdown


def test_benchmark_with_oracle_model_fixes_every_case(tmp_path, settings):
    import json

    def oracle(case):
        return ScriptedLLM([as_reply(case["solution"])], name="oracle", model="reference-fix")

    code = run_benchmark(str(CASES), str(tmp_path), settings, llm_factory=oracle, log=lambda _m: None)
    assert code == 0
    result = json.loads(next(Path(tmp_path).glob("*.json")).read_text())
    assert result["summary"]["fixed"] == result["summary"]["total"] == 14
    assert (Path(tmp_path) / "latest.md").exists()
