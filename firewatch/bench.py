import json
import re
import shutil
import statistics
import tempfile
import time
from pathlib import Path

from .agent import run_agent
from .llm import LLMClient
from .patcher import Snapshot, apply_edits
from .verifier import run_tests

TEST_COMMAND = "python -m pytest -q -p no:cacheprovider"
MAVEN_TEST_COMMAND = "mvn -q -B test"


def _test_command(case_dir, meta):
    if meta.get("test_command"):
        return meta["test_command"]
    if (case_dir / "pom.xml").is_file():
        return MAVEN_TEST_COMMAND
    return TEST_COMMAND


def load_cases(cases_dirs, only=None):
    if isinstance(cases_dirs, (str, Path)):
        cases_dirs = [cases_dirs]
    cases = []
    for cases_dir in cases_dirs:
        root = Path(cases_dir)
        if not root.is_dir():
            continue
        for case_dir in sorted(root.iterdir()):
            meta_path = case_dir / "case.json"
            if not case_dir.is_dir() or not meta_path.exists():
                continue
            if only and case_dir.name not in only:
                continue
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["name"] = case_dir.name
            meta["path"] = case_dir
            meta["test_command"] = _test_command(case_dir, meta)
            cases.append(meta)
    return cases


def missing_tool(case):
    tool = case["test_command"].split()[0]
    if tool in ("python", "python3"):
        return None
    return None if shutil.which(tool) else tool


def _workspace(case):
    target = Path(tempfile.mkdtemp(prefix=f"fw-{case['name']}-"))
    shutil.copytree(
        case["path"], target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("case.json", "__pycache__", "target")
    )
    return target


def validate_case(case):
    work = _workspace(case)
    try:
        before = run_tests(str(work), case["test_command"], 600)
        snapshot = Snapshot(work)
        outcomes = apply_edits(str(work), case.get("solution", []), snapshot)
        applied = all(o.ok for o in outcomes)
        after = run_tests(str(work), case["test_command"], 600)
        problems = [o.reason for o in outcomes if not o.ok]
        if not after.passed:
            problems.append(after.output[-400:])
        return {
            "name": case["name"],
            "fails_before": not before.passed,
            "solution_applies": applied,
            "passes_after": after.passed,
            "ok": (not before.passed) and applied and after.passed,
            "detail": "; ".join(problems),
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _slug(text):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-")[:60] or "model"


def summarize(rows):
    total = len(rows)
    fixed = [r for r in rows if r["status"] == "fixed"]
    first = [r for r in fixed if r["attempts"] == 1]
    return {
        "total": total,
        "fixed": len(fixed),
        "fix_rate": round(len(fixed) / total, 3) if total else 0,
        "first_attempt": len(first),
        "mean_attempts_when_fixed": round(statistics.mean(r["attempts"] for r in fixed), 2) if fixed else None,
        "median_seconds": round(statistics.median(r["seconds"] for r in rows), 1) if rows else None,
    }


def render_table(model, summary, rows):
    lines = [
        f"## Benchmark: `{model}`",
        "",
        f"**Fixed {summary['fixed']}/{summary['total']}** "
        f"({summary['fix_rate'] * 100:.0f}%) · first-attempt fixes: {summary['first_attempt']} · "
        f"mean attempts when fixed: {summary['mean_attempts_when_fixed']} · median time: {summary['median_seconds']}s",
        "",
        "| Case | Category | Result | Attempts | Time | Root cause found by the model |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        mark = "fixed" if r["status"] == "fixed" else r["status"].replace("_", " ")
        diagnosis = (r["diagnosis"] or "").replace("|", "/").replace("\n", " ")[:140]
        lines.append(f"| {r['name']} | {r['category']} | {mark} | {r['attempts']} | {r['seconds']:.0f}s | {diagnosis} |")
    return "\n".join(lines) + "\n"


def run_benchmark(cases_dir, out_dir, settings, only=None, validate=False, log=print, llm_factory=None):
    cases = load_cases(cases_dir, only)
    if not cases:
        log(f"No cases found in {cases_dir}")
        return 1

    runnable = []
    for case in cases:
        tool = missing_tool(case)
        if tool:
            log(f"Skipping {case['name']}: '{tool}' is not on PATH")
        else:
            runnable.append(case)
    cases = runnable
    if not cases:
        log("No runnable cases.")
        return 1

    if validate:
        bad = 0
        for case in cases:
            report = validate_case(case)
            status = "ok " if report["ok"] else "BAD"
            if not report["ok"]:
                bad += 1
            log(f"{status} {case['name']}: fails_before={report['fails_before']} applies={report['solution_applies']} passes_after={report['passes_after']} {report['detail'][:200]}")
        log(f"{len(cases) - bad}/{len(cases)} cases valid")
        return 0 if bad == 0 else 1

    factory = llm_factory or (lambda _case: LLMClient(settings.providers, settings.temperature, settings.request_timeout))
    rows = []
    model_name = None
    for index, case in enumerate(cases, 1):
        llm = factory(case)
        model_name = model_name or llm.describe()
        work = _workspace(case)
        log(f"[{index}/{len(cases)}] {case['name']} ({case.get('category', '')})")
        started = time.monotonic()
        try:
            result = run_agent(str(work), case["test_command"], llm, settings, log=lambda m: log(f"    {m}"))
        finally:
            elapsed = time.monotonic() - started
        rows.append(
            {
                "name": case["name"],
                "title": case.get("title", ""),
                "category": case.get("category", ""),
                "language": "java" if case["test_command"] == MAVEN_TEST_COMMAND else "python",
                "status": result.status,
                "attempts": len(result.attempts),
                "seconds": round(elapsed, 1),
                "model_seconds": round(sum(a.model_seconds for a in result.attempts), 1),
                "diagnosis": result.diagnosis,
                "diff": result.final_diff,
                "edit_errors": [e for a in result.attempts for e in a.edit_errors],
                "model": result.model,
                "attempt_log": [
                    {
                        "number": a.number,
                        "temperature": a.temperature,
                        "diagnosis": a.diagnosis,
                        "files_changed": a.files_changed,
                        "failed_before": a.failed_before,
                        "failed_after": a.failed_after,
                        "kept": a.kept,
                        "new_failures": a.new_failures,
                        "diff": a.diff,
                        "edit_errors": a.edit_errors,
                    }
                    for a in result.attempts
                ],
            }
        )
        log(f"    -> {result.status} in {len(result.attempts)} attempt(s), {elapsed:.0f}s")
        shutil.rmtree(work, ignore_errors=True)
        if result.status == "error":
            log("Model unreachable; stopping the benchmark early.")
            break

    model_name = next((r["model"] for r in rows if r["model"]), model_name or "unknown")
    summary = summarize(rows)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    payload = {
        "model": model_name,
        "max_attempts": settings.max_attempts,
        "retry_temperatures": settings.retry_temperatures,
        "summary": summary,
        "cases": rows,
    }
    json_path = out / f"{stamp}-{_slug(model_name)}.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    table = render_table(model_name, summary, rows)
    (out / f"{stamp}-{_slug(model_name)}.md").write_text(table, encoding="utf-8")
    (out / "latest.md").write_text(table, encoding="utf-8")
    log(f"Fixed {summary['fixed']}/{summary['total']}. Results: {json_path}")
    return 0
