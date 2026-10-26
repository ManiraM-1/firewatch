import difflib
import re
from dataclasses import dataclass
from pathlib import Path

from .context import is_test_path
from .triage import normalize_path


@dataclass
class EditResult:
    file: str
    ok: bool
    reason: str = ""


class Snapshot:
    def __init__(self, repo_root):
        self.repo_root = Path(repo_root)
        self.originals = {}

    def remember(self, rel):
        if rel in self.originals:
            return
        path = self.repo_root / rel
        self.originals[rel] = path.read_bytes() if path.exists() else None

    def restore(self):
        for rel, data in self.originals.items():
            path = self.repo_root / rel
            if data is None:
                if path.exists():
                    path.unlink()
            else:
                path.write_bytes(data)
        self.originals = {}

    def commit(self):
        self.originals = {}


def _safe_path(repo_root, rel):
    root = Path(repo_root).resolve()
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    if ".git" in target.relative_to(root).parts:
        return None
    return target


def _is_absolute(rel):
    return rel.startswith("/") or bool(re.match(r"^[A-Za-z]:/", rel))


def _relative_to_repo(rel, repo_root):
    root = Path(repo_root).resolve()
    try:
        return Path(rel).resolve().relative_to(root).as_posix()
    except (ValueError, OSError):
        pass
    lowered_root = root.as_posix().lower().rstrip("/") + "/"
    if rel.lower().startswith(lowered_root):
        return rel[len(lowered_root):]
    return normalize_path(rel, repo_root)


def _find_rstrip_match(text, search):
    text_lines = text.split("\n")
    search_lines = search.strip("\n").split("\n")
    stripped_search = [line.rstrip() for line in search_lines]
    hits = []
    for i in range(len(text_lines) - len(search_lines) + 1):
        window = [line.rstrip() for line in text_lines[i : i + len(search_lines)]]
        if window == stripped_search:
            hits.append(i)
    return hits, text_lines, len(search_lines)


def _find_dedent_match(text, search):
    text_lines = text.split("\n")
    search_lines = search.strip("\n").split("\n")
    target = [line.strip() for line in search_lines]
    if not any(target):
        return [], text_lines, len(search_lines)
    hits = []
    for i in range(len(text_lines) - len(search_lines) + 1):
        window = [line.strip() for line in text_lines[i : i + len(search_lines)]]
        if window == target:
            hits.append(i)
    return hits, text_lines, len(search_lines)


def _reindent(replace, original_first_line, search_first_line):
    orig_indent = original_first_line[: len(original_first_line) - len(original_first_line.lstrip())]
    search_indent = search_first_line[: len(search_first_line) - len(search_first_line.lstrip())]
    out = []
    for line in replace.strip("\n").split("\n"):
        if line.startswith(search_indent):
            out.append(orig_indent + line[len(search_indent):])
        else:
            out.append(orig_indent + line.lstrip() if line.strip() else line)
    return out


def apply_edit(repo_root, edit, snapshot, allow_test_edits=False):
    rel = str(edit.get("file") or "").strip().replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    if rel and _is_absolute(rel):
        rel = _relative_to_repo(rel, repo_root)
        if rel is None:
            return EditResult(str(edit.get("file")), False, "path is outside the repository")
    elif rel and not (Path(repo_root) / rel).exists():
        resolved = normalize_path(rel, repo_root)
        if resolved:
            rel = resolved
    search = edit.get("search", "")
    replace = edit.get("replace", "")
    if not rel:
        return EditResult("?", False, "edit has no file")
    target = _safe_path(repo_root, rel)
    if target is None:
        return EditResult(rel, False, "path is outside the repository")
    if is_test_path(rel) and not allow_test_edits:
        return EditResult(rel, False, "editing tests is disabled; fix the code under test")

    if not target.exists():
        if search.strip():
            return EditResult(rel, False, "file does not exist")
        snapshot.remember(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(replace, encoding="utf-8")
        return EditResult(rel, True, "created file")

    raw = target.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")
    search_n = search.replace("\r\n", "\n")
    replace_n = replace.replace("\r\n", "\n")

    if not search_n.strip():
        return EditResult(rel, False, "search block is empty")

    count = text.count(search_n)
    if count == 1:
        new_text = text.replace(search_n, replace_n, 1)
        how = "exact match"
    elif count > 1:
        return EditResult(rel, False, f"search block matches {count} places; include more surrounding lines")
    else:
        hits, lines, size = _find_rstrip_match(text, search_n)
        how = "matched ignoring trailing whitespace"
        new_lines = None
        if len(hits) == 1:
            new_lines = lines[: hits[0]] + replace_n.strip("\n").split("\n") + lines[hits[0] + size :]
        elif not hits:
            hits, lines, size = _find_dedent_match(text, search_n)
            how = "matched ignoring indentation"
            if len(hits) == 1:
                first_search = next(line for line in search_n.strip("\n").split("\n"))
                body = _reindent(replace_n, lines[hits[0]], first_search)
                new_lines = lines[: hits[0]] + body + lines[hits[0] + size :]
        if new_lines is None:
            if len(hits) > 1:
                return EditResult(rel, False, f"search block matches {len(hits)} places; include more surrounding lines")
            return EditResult(rel, False, "search block not found in file; copy it exactly from the file")
        new_text = "\n".join(new_lines)

    if new_text == text:
        return EditResult(rel, False, "edit produces no change")

    snapshot.remember(rel)
    if crlf:
        new_text = new_text.replace("\n", "\r\n")
    target.write_bytes(new_text.encode("utf-8"))
    return EditResult(rel, True, how)


def apply_edits(repo_root, edits, snapshot, allow_test_edits=False):
    return [apply_edit(repo_root, edit, snapshot, allow_test_edits) for edit in edits]


def unified_diff(repo_root, originals):
    chunks = []
    for rel, before_bytes in sorted(originals.items()):
        after_path = Path(repo_root) / rel
        before = before_bytes.decode("utf-8").replace("\r\n", "\n") if before_bytes else ""
        after = after_path.read_text(encoding="utf-8").replace("\r\n", "\n") if after_path.exists() else ""
        if before == after:
            continue
        chunks.extend(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
            )
        )
    return "".join(chunks)
