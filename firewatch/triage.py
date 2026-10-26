import re
from dataclasses import dataclass, field
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
GH_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z ?", re.MULTILINE)

PY_TRACEBACK_FRAME = re.compile(r'File "([^"]+)", line (\d+)')
PYTEST_LOCATION = re.compile(r"^([\w./\\-]+\.py):(\d+):", re.MULTILINE)
GENERIC_LOCATION = re.compile(r"([\w./\\-]+\.(?:py|java|kt|js|ts|go|rb)):(\d+)")
PYTEST_FAILED = re.compile(r"^(?:FAILED|ERROR) ([\w./\\-]+\.py)(?:::([\w\[\]\-.:]+))?", re.MULTILINE)
SIGNAL_LINE = re.compile(
    r"(Error|Exception|Traceback|FAILED|FAIL:|AssertionError|assert |E   |error:|panic:|Caused by"
    r"|\[ERROR\]|<<< (?:FAILURE|ERROR)!)"
)


@dataclass
class FileRef:
    path: str
    line: int


@dataclass
class Triage:
    excerpt: str
    file_refs: list = field(default_factory=list)
    failing_tests: list = field(default_factory=list)
    failed_count: int = 0


def clean_log(text):
    text = ANSI.sub("", text or "")
    text = GH_TIMESTAMP.sub("", text)
    return text.replace("\r\n", "\n")


def _pytest_excerpt(text):
    start = text.find("= FAILURES =")
    if start == -1:
        start = text.find("= ERRORS =")
    if start == -1:
        return None
    line_start = text.rfind("\n", 0, start) + 1
    return text[line_start:].strip()


def _signal_excerpt(text, context=6, max_lines=160):
    lines = text.split("\n")
    keep = set()
    for index, line in enumerate(lines):
        if SIGNAL_LINE.search(line):
            for j in range(max(0, index - context), min(len(lines), index + context + 1)):
                keep.add(j)
    if not keep:
        return "\n".join(lines[-max_lines:])
    picked = []
    previous = None
    for index in sorted(keep):
        if previous is not None and index != previous + 1:
            picked.append("...")
        picked.append(lines[index])
        previous = index
    return "\n".join(picked[-max_lines:])


def _cap(text, max_chars):
    if len(text) <= max_chars:
        return text
    head = max_chars // 3
    return text[:head] + "\n...[truncated]...\n" + text[-(max_chars - head):]


def normalize_path(raw, repo_root):
    repo_root = Path(repo_root).resolve()
    candidate = raw.replace("\\", "/")
    path = Path(candidate)
    if re.match(r"^[A-Za-z]:/", candidate) and not path.is_absolute():
        return None if not _looks_like_ci_checkout(candidate) else _from_checkout(candidate, repo_root)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(repo_root).as_posix()
        except ValueError:
            if not _looks_like_ci_checkout(candidate):
                return None
    if (repo_root / candidate).is_file():
        return Path(candidate).as_posix()
    parts = Path(candidate).parts
    for i in range(1, len(parts)):
        suffix = Path(*parts[i:])
        if (repo_root / suffix).is_file():
            return suffix.as_posix()
    return _unique_by_name(Path(candidate).name, repo_root)


def _from_checkout(candidate, repo_root):
    parts = Path(candidate).parts
    for i in range(1, len(parts)):
        suffix = Path(*parts[i:])
        if (repo_root / suffix).is_file():
            return suffix.as_posix()
    return None


def _looks_like_ci_checkout(path):
    lowered = path.lower()
    return any(marker in lowered for marker in ("/home/runner/work/", "/github/workspace/", "/builds/", "d:/a/", "/__w/"))


IGNORED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "target", "build", "dist", ".gradle"}
_name_index_cache = {}


def _unique_by_name(name, repo_root):
    if not name or "." not in name:
        return None
    key = str(repo_root)
    index = _name_index_cache.get(key)
    if index is None:
        index = {}
        for path in repo_root.rglob("*"):
            if path.is_file() and not any(part in IGNORED_DIRS for part in path.relative_to(repo_root).parts):
                index.setdefault(path.name, []).append(path.relative_to(repo_root).as_posix())
        _name_index_cache[key] = index
    matches = index.get(name, [])
    return matches[0] if len(matches) == 1 else None


def _is_vendor(path):
    lowered = path.replace("\\", "/").lower()
    return any(
        marker in lowered
        for marker in ("site-packages", "dist-packages", "/lib/python", "_pytest", "pluggy", "<frozen")
    )


def triage_log(log_text, repo_root, max_chars=12000):
    text = clean_log(log_text)
    excerpt = _pytest_excerpt(text) or _signal_excerpt(text)
    excerpt = _cap(excerpt, max_chars)

    refs = []
    seen = set()
    for pattern in (PY_TRACEBACK_FRAME, PYTEST_LOCATION, GENERIC_LOCATION):
        for match in pattern.finditer(text):
            raw, line = match.group(1), int(match.group(2))
            if _is_vendor(raw):
                continue
            rel = normalize_path(raw, repo_root)
            if rel and (rel, line) not in seen:
                seen.add((rel, line))
                refs.append(FileRef(rel, line))

    failing = []
    for match in PYTEST_FAILED.finditer(text):
        rel = normalize_path(match.group(1), repo_root) or match.group(1)
        test_id = f"{rel}::{match.group(2)}" if match.group(2) else rel
        if test_id not in failing:
            failing.append(test_id)

    counts = summary_counts(text)
    failed_count = counts.get("failed", 0) + counts.get("error", 0) if counts else len(failing)

    return Triage(excerpt=excerpt, file_refs=refs, failing_tests=failing, failed_count=failed_count)


SUMMARY_LINE = re.compile(
    r"^(?:=+ )?((?:\d+ \w+(?:, )?)+|no tests ran)(?: in [\d.]+s)(?: \([^)]*\))?(?: =+)?\s*$", re.MULTILINE
)
SUMMARY_PART = re.compile(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed|warnings?)")
MAVEN_SUMMARY = re.compile(r"Tests run: (\d+), Failures: (\d+), Errors: (\d+)(?:, Skipped: (\d+))?")


def summary_counts(text):
    cleaned = clean_log(text)
    matches = SUMMARY_LINE.findall(cleaned)
    if not matches:
        maven = MAVEN_SUMMARY.findall(cleaned)
        if not maven:
            return {}
        run, failures, errors, skipped = (int(part or 0) for part in maven[-1])
        return {
            "passed": max(0, run - failures - errors - skipped),
            "failed": failures,
            "error": errors,
            "skipped": skipped,
        }
    counts = {}
    for number, kind in SUMMARY_PART.findall(matches[-1]):
        key = "error" if kind.startswith("error") else kind.rstrip("s") if kind.startswith("warning") else kind
        counts[key] = counts.get(key, 0) + int(number)
    return counts
