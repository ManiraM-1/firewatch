import json
import re
from dataclasses import dataclass, field

SYSTEM_PROMPT = """You are Firewatch, an agent that repairs failing CI builds.

You receive the failing test output and the most relevant source files.
Find the root cause and return the smallest code change that makes the failing tests pass
without breaking the intended behaviour.

Rules:
1. Fix the code under test. {test_rule}
2. Never weaken, skip, or delete tests and never special-case test inputs.
3. Each edit replaces one exact block. The "search" text must be copied character for character
   from the file shown, including indentation, and must be long enough to appear only once.
4. Keep edits minimal. Do not reformat or rewrite unrelated code.
5. If several files are wrong, return one edit per location.

Respond with a single JSON object inside a ```json code block and nothing else:
```json
{{
  "diagnosis": "one or two sentences: what is broken and why the test fails",
  "root_cause_file": "path/to/file.py",
  "confidence": "high | medium | low",
  "edits": [
    {{"file": "path/to/file.py", "search": "exact existing lines", "replace": "corrected lines"}}
  ]
}}
```"""

TEST_RULE_LOCKED = "Test files are read-only; edits to them will be rejected."
TEST_RULE_OPEN = "Only edit a test file if the test itself is clearly wrong, and say so in the diagnosis."


@dataclass
class FixProposal:
    diagnosis: str
    root_cause_file: str = ""
    confidence: str = ""
    edits: list = field(default_factory=list)
    raw: str = ""
    parse_error: str = ""


def build_messages(failure_excerpt, context_text, history, allow_test_edits=False, ci_excerpt=None):
    system = SYSTEM_PROMPT.format(test_rule=TEST_RULE_OPEN if allow_test_edits else TEST_RULE_LOCKED)
    parts = ["## Failing test output", "```", failure_excerpt.strip(), "```"]
    if ci_excerpt and ci_excerpt.strip() and ci_excerpt.strip() != failure_excerpt.strip():
        parts += ["## Original CI log excerpt", "```", ci_excerpt.strip()[:4000], "```"]
    parts += ["## Relevant files", context_text.strip() or "(no files could be located)"]
    if history:
        parts.append("## Previous attempts (all failed; do not repeat them)")
        parts.append(
            "Each attempt below did not make the tests pass, so its diagnosis is probably wrong or incomplete. "
            "Before proposing edits, re-read the failing assertions: compare the expected value with the actual "
            "value and work out which line of code produces the actual value. Consider a different root cause "
            "from the ones already tried."
        )
        seen = set()
        for item in history:
            parts.append(f"### Attempt {item['attempt']}")
            if item.get("diagnosis"):
                parts.append(f"Diagnosis: {item['diagnosis']}")
                key = item["diagnosis"].strip().lower()
                if key in seen:
                    parts.append("This diagnosis was already tried and failed. Do not use it again.")
                seen.add(key)
            if item.get("edit_errors"):
                parts.append("Edits that could not be applied:\n" + "\n".join(f"- {e}" for e in item["edit_errors"]))
            if item.get("diff"):
                parts += ["Change tried:", "```diff", item["diff"].strip()[:3000], "```"]
            if item.get("kept"):
                parts.append("This change reduced the failures and has been kept in the files above.")
            if item.get("broke"):
                parts.append(
                    "This change broke tests that were passing before, so it was reverted: "
                    + ", ".join(item["broke"])
                    + ". Those tests define behaviour that must be preserved."
                )
            if item.get("result_excerpt"):
                parts += ["Test output after that change:", "```", item["result_excerpt"].strip()[:3000], "```"]
    parts.append("Return the JSON object now.")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(parts)},
    ]


def _extract_json_text(raw):
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fenced:
        return max(fenced, key=len)
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        return raw[start : end + 1]
    return None


def _strip_think(raw):
    return re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()


def parse_proposal(raw):
    cleaned = _strip_think(raw or "")
    blob = _extract_json_text(cleaned)
    if blob is None:
        return FixProposal(diagnosis="", raw=raw, parse_error="no JSON object found in the model response")
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        try:
            data = json.loads(re.sub(r",\s*([}\]])", r"\1", blob))
        except json.JSONDecodeError as exc:
            return FixProposal(diagnosis="", raw=raw, parse_error=f"invalid JSON: {exc}")
    if not isinstance(data, dict):
        return FixProposal(diagnosis="", raw=raw, parse_error="JSON is not an object")
    edits = data.get("edits") or []
    clean = []
    for edit in edits if isinstance(edits, list) else []:
        if isinstance(edit, dict) and edit.get("file") is not None:
            clean.append(
                {
                    "file": str(edit.get("file", "")),
                    "search": str(edit.get("search", "")),
                    "replace": str(edit.get("replace", "")),
                }
            )
    return FixProposal(
        diagnosis=str(data.get("diagnosis", "")).strip(),
        root_cause_file=str(data.get("root_cause_file", "")).strip(),
        confidence=str(data.get("confidence", "")).strip(),
        edits=clean,
        raw=raw,
        parse_error="" if clean else "no edits in the response",
    )
