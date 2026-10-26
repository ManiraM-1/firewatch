import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "venv", "env", "node_modules", "__pycache__", ".pytest_cache", "build", "dist", ".tox"}
TEST_FILE = re.compile(r"(^|/)(test_[^/]*\.py|[^/]*_test\.py|conftest\.py)$|(^|/)tests?/")


def is_test_path(path):
    return bool(TEST_FILE.search(path.replace("\\", "/")))


@dataclass
class ContextFile:
    path: str
    reason: str
    score: float
    lines: list = field(default_factory=list)


@dataclass
class Context:
    files: list
    rendered: str
    dropped: list = field(default_factory=list)


def _read(repo_root, rel):
    try:
        return (Path(repo_root) / rel).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _module_candidates(module, repo_root, from_file=None, level=0):
    root = Path(repo_root)
    parts = module.split(".") if module else []
    bases = []
    if level and from_file:
        base = (root / from_file).parent
        for _ in range(level - 1):
            base = base.parent
        bases.append(base)
    else:
        bases.extend([root, root / "src"])
        if from_file:
            bases.append((root / from_file).parent)
    found = []
    for base in bases:
        target = base.joinpath(*parts) if parts else base
        for candidate in (target.with_suffix(".py"), target / "__init__.py"):
            if candidate.is_file():
                try:
                    found.append(candidate.resolve().relative_to(root.resolve()).as_posix())
                except ValueError:
                    continue
    return found


def local_imports(rel, repo_root):
    source = _read(repo_root, rel)
    if source is None or not rel.endswith(".py"):
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.extend(_module_candidates(alias.name, repo_root, rel))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            found.extend(_module_candidates(module, repo_root, rel, node.level))
            for alias in node.names:
                sub = f"{module}.{alias.name}" if module else alias.name
                found.extend(_module_candidates(sub, repo_root, rel, node.level))
    unique = []
    for path in found:
        if path != rel and path not in unique:
            unique.append(path)
    return unique


def _window(text, focus_lines, radius=60, max_full_lines=400):
    lines = text.split("\n")
    if len(lines) <= max_full_lines or not focus_lines:
        return text, False
    keep = set()
    for line in focus_lines:
        for i in range(max(0, line - 1 - radius), min(len(lines), line + radius)):
            keep.add(i)
    chunks = []
    previous = None
    for i in sorted(keep):
        if previous is not None and i != previous + 1:
            chunks.append("    ...")
        chunks.append(lines[i])
        previous = i
    return "\n".join(chunks), True


def build_context(repo_root, triage, changed_files=None, char_budget=24000):
    candidates = {}

    def add(path, reason, score, line=None):
        if not path or not (Path(repo_root) / path).is_file():
            return
        if any(part in SKIP_DIRS for part in Path(path).parts):
            return
        entry = candidates.get(path)
        if entry is None:
            entry = ContextFile(path=path, reason=reason, score=score)
            candidates[path] = entry
        elif score > entry.score:
            entry.score = score
            entry.reason = reason
        if line:
            entry.lines.append(line)

    for ref in triage.file_refs:
        add(ref.path, "in traceback", 10 if not is_test_path(ref.path) else 7, ref.line)

    failing_files = []
    for test_id in triage.failing_tests:
        test_file = test_id.split("::")[0]
        failing_files.append(test_file)
        add(test_file, "failing test", 6)

    for ref in triage.file_refs:
        if is_test_path(ref.path) and ref.path not in failing_files:
            failing_files.append(ref.path)

    for test_file in failing_files:
        for imported in local_imports(test_file, repo_root):
            add(imported, f"imported by {test_file}", 8)
            for second in local_imports(imported, repo_root):
                add(second, f"imported by {imported}", 5)

    for path in changed_files or []:
        add(path, "changed in the failing commit", 9)

    ranked = sorted(candidates.values(), key=lambda c: (-c.score, c.path))
    rendered_parts = []
    used = 0
    included = []
    dropped = []
    for item in ranked:
        text = _read(repo_root, item.path)
        if text is None:
            continue
        body, windowed = _window(text, item.lines)
        note = " (excerpt)" if windowed else ""
        block = f"### {item.path}{note}  [{item.reason}]\n```\n{body}\n```\n"
        if used + len(block) > char_budget and included:
            dropped.append(item.path)
            continue
        rendered_parts.append(block)
        used += len(block)
        included.append(item)

    return Context(files=included, rendered="\n".join(rendered_parts), dropped=dropped)
