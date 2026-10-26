import os
import subprocess
import sys
import time
from dataclasses import dataclass

from .triage import clean_log, summary_counts


@dataclass
class TestRun:
    passed: bool
    exit_code: int
    output: str
    failed_count: int
    duration: float
    timed_out: bool = False


def run_tests(repo_root, command, timeout=600):
    env = dict(os.environ)
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    env["PY_COLORS"] = "0"
    env["FORCE_COLOR"] = "0"
    if command.startswith("python ") and sys.executable:
        command = f'"{sys.executable}" ' + command[len("python ") :]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=repo_root,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        output = ((exc.stdout or "") if isinstance(exc.stdout, str) else "") + "\n[firewatch] test command timed out"
        return TestRun(False, -1, clean_log(output), 1, time.monotonic() - started, timed_out=True)

    output = clean_log((completed.stdout or "") + "\n" + (completed.stderr or ""))
    counts = summary_counts(output)
    failed = counts.get("failed", 0) + counts.get("error", 0)
    passed = completed.returncode == 0
    if not passed and failed == 0:
        failed = 1
    return TestRun(passed, completed.returncode, output, failed, time.monotonic() - started)
