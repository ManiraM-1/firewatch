import time
from dataclasses import dataclass, field
from pathlib import Path

from .context import build_context
from .fixer import build_messages, parse_proposal
from .llm import LLMError
from .patcher import Snapshot, apply_edits, unified_diff
from .triage import triage_log
from .verifier import run_tests


@dataclass
class Attempt:
    number: int
    diagnosis: str = ""
    confidence: str = ""
    files_changed: list = field(default_factory=list)
    edit_errors: list = field(default_factory=list)
    failed_before: int = 0
    failed_after: int = None
    passed: bool = False
    kept: bool = False
    diff: str = ""
    model_seconds: float = 0.0
    test_seconds: float = 0.0
    temperature: float = 0.0
    context_files: list = field(default_factory=list)
    new_failures: list = field(default_factory=list)


@dataclass
class RunResult:
    status: str
    diagnosis: str = ""
    attempts: list = field(default_factory=list)
    final_diff: str = ""
    baseline_failed: int = 0
    failure_excerpt: str = ""
    model: str = ""
    duration: float = 0.0
    message: str = ""
    changed_files: list = field(default_factory=list)

    @property
    def fixed(self):
        return self.status == "fixed"


def _quiet(_message):
    return None


def run_agent(
    repo_root,
    test_command,
    llm,
    settings,
    ci_log=None,
    changed_files=None,
    keep_partial=False,
    log=_quiet,
):
    started = time.monotonic()
    log(f"Reproducing the failure: {test_command}")
    baseline = run_tests(repo_root, test_command, settings.test_timeout)
    ci_triage = triage_log(ci_log, repo_root) if ci_log else None

    if baseline.passed:
        result = RunResult(
            status="not_reproduced" if ci_log else "no_failure",
            message="Tests pass locally, so there is nothing to fix here."
            if not ci_log
            else "The failure did not reproduce when re-running the tests. It may be flaky or environment-specific.",
            failure_excerpt=ci_triage.excerpt if ci_triage else "",
            model=llm.describe(),
            duration=time.monotonic() - started,
        )
        if ci_triage:
            result.diagnosis = _diagnose_only(repo_root, ci_triage, changed_files, llm, settings, log)
        return result

    triage = triage_log(baseline.output, repo_root)
    current_failed = baseline.failed_count
    current_failing = set(triage.failing_tests)
    log(f"Reproduced: {current_failed} failing. Located {len(triage.file_refs)} code references.")

    result = RunResult(
        status="not_fixed",
        baseline_failed=current_failed,
        failure_excerpt=triage.excerpt,
        model=llm.describe(),
    )
    session_originals = {}
    history = []

    for number in range(1, settings.max_attempts + 1):
        attempt = Attempt(number=number, failed_before=current_failed)
        context = build_context(repo_root, triage, changed_files, settings.context_char_budget)
        attempt.context_files = [f.path for f in context.files]
        log(f"Attempt {number}: context = {', '.join(attempt.context_files) or 'none'}")

        messages = build_messages(
            triage.excerpt,
            context.rendered,
            history,
            allow_test_edits=settings.allow_test_edits,
            ci_excerpt=ci_triage.excerpt if ci_triage else None,
        )
        temperatures = settings.retry_temperatures or [settings.temperature]
        attempt.temperature = temperatures[min(number - 1, len(temperatures) - 1)]
        try:
            raw, provider, seconds = llm.complete(messages, temperature=attempt.temperature)
        except LLMError as exc:
            result.status = "error"
            result.message = str(exc)
            log(f"Model call failed: {exc}")
            break
        attempt.model_seconds = seconds
        result.model = f"{provider.name}:{provider.model}"

        proposal = parse_proposal(raw)
        attempt.diagnosis = proposal.diagnosis
        attempt.confidence = proposal.confidence
        if proposal.diagnosis:
            log(f"Diagnosis: {proposal.diagnosis}")

        if not proposal.edits:
            attempt.edit_errors = [proposal.parse_error or "model returned no edits"]
            log(f"No usable edits: {attempt.edit_errors[0]}")
            result.attempts.append(attempt)
            history.append({"attempt": number, "diagnosis": proposal.diagnosis, "edit_errors": attempt.edit_errors})
            continue

        snapshot = Snapshot(repo_root)
        outcomes = apply_edits(repo_root, proposal.edits, snapshot, settings.allow_test_edits)
        for rel, data in snapshot.originals.items():
            session_originals.setdefault(rel, data)
        attempt.files_changed = sorted({o.file for o in outcomes if o.ok})
        attempt.edit_errors = [f"{o.file}: {o.reason}" for o in outcomes if not o.ok]
        for error in attempt.edit_errors:
            log(f"Edit rejected: {error}")

        if not attempt.files_changed:
            snapshot.restore()
            result.attempts.append(attempt)
            history.append({"attempt": number, "diagnosis": proposal.diagnosis, "edit_errors": attempt.edit_errors})
            continue

        attempt.diff = unified_diff(repo_root, snapshot.originals)
        log(f"Verifying patch to {', '.join(attempt.files_changed)}")
        run = run_tests(repo_root, test_command, settings.test_timeout)
        attempt.test_seconds = run.duration
        attempt.failed_after = 0 if run.passed else run.failed_count

        if run.passed:
            attempt.passed = True
            attempt.kept = True
            snapshot.commit()
            result.attempts.append(attempt)
            result.status = "fixed"
            result.diagnosis = proposal.diagnosis
            log(f"Tests pass after attempt {number}.")
            break

        after = triage_log(run.output, repo_root)
        improved, broken = judge_progress(current_failing, set(after.failing_tests), current_failed, run.failed_count)
        attempt.new_failures = sorted(broken)
        if not run.timed_out and improved:
            attempt.kept = True
            snapshot.commit()
            current_failed = run.failed_count
            current_failing = set(after.failing_tests)
            triage = after
            log(f"Partial progress: {attempt.failed_before} -> {run.failed_count} failing. Keeping the change.")
        elif broken:
            snapshot.restore()
            log(f"Broke tests that were passing ({', '.join(sorted(broken))}). Reverting this attempt.")
        else:
            snapshot.restore()
            log(f"Still failing ({run.failed_count}). Reverting this attempt.")

        result.attempts.append(attempt)
        history.append(
            {
                "attempt": number,
                "diagnosis": proposal.diagnosis,
                "edit_errors": attempt.edit_errors,
                "diff": attempt.diff,
                "kept": attempt.kept,
                "broke": attempt.new_failures,
                "result_excerpt": after.excerpt,
            }
        )

    if not result.diagnosis:
        result.diagnosis = next((a.diagnosis for a in reversed(result.attempts) if a.diagnosis), "")

    result.final_diff = unified_diff(repo_root, session_originals)
    result.changed_files = sorted(
        rel for rel in session_originals if _differs(repo_root, rel, session_originals[rel])
    )
    if not result.fixed and not keep_partial and session_originals:
        restore = Snapshot(repo_root)
        restore.originals = dict(session_originals)
        restore.restore()

    result.duration = time.monotonic() - started
    return result


def judge_progress(failing_before, failing_after, count_before, count_after):
    if failing_before and (failing_after or count_after == 0):
        broken = failing_after - failing_before
        if broken:
            return False, broken
        return failing_after < failing_before, set()
    return count_after < count_before, set()


def _differs(repo_root, rel, original):
    path = Path(repo_root) / rel
    current = path.read_bytes() if path.exists() else None
    return current != original


def _diagnose_only(repo_root, ci_triage, changed_files, llm, settings, log):
    context = build_context(repo_root, ci_triage, changed_files, settings.context_char_budget)
    messages = build_messages(ci_triage.excerpt, context.rendered, [], settings.allow_test_edits)
    try:
        raw, _provider, _seconds = llm.complete(messages)
    except LLMError as exc:
        log(f"Diagnosis call failed: {exc}")
        return ""
    return parse_proposal(raw).diagnosis
