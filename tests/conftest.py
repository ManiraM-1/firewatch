import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from firewatch.config import Settings  # noqa: E402

CASES = ROOT / "bench" / "cases"


@pytest.fixture
def settings():
    return Settings(providers=[], max_attempts=3, test_timeout=120)


@pytest.fixture
def case_repo(tmp_path):
    def make(name):
        target = tmp_path / name
        shutil.copytree(CASES / name, target, ignore=shutil.ignore_patterns("case.json", "__pycache__"))
        solution = json.loads((CASES / name / "case.json").read_text(encoding="utf-8"))["solution"]
        return target, solution

    return make


def as_reply(edits, diagnosis="root cause found"):
    body = json.dumps({"diagnosis": diagnosis, "root_cause_file": edits[0]["file"] if edits else "", "confidence": "high", "edits": edits})
    return f"Here is the fix.\n```json\n{body}\n```"
