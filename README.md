# Firewatch

**An always-on agent that turns a red CI run into a verified fix, using open models.**

When your CI fails, Firewatch wakes up, reproduces the failure, finds the code that caused it, asks an open model for a minimal patch, and **re-runs your tests to prove the patch works** before anyone sees it. If the tests pass, you get a pull request with the root cause, the diff, and the attempt history. If they don't, you get a comment explaining what it found and what it tried, and your branch is left untouched.

Built for [Openfire](https://luma.com) by Alan AI · Python · MIT licensed

---

## The problem

Coding agents made writing code fast. Fixing a broken build is still slow: someone notices the red X, opens the logs, scrolls past hundreds of lines of setup noise, finds the assertion, opens three files, works out which one is wrong, patches it, pushes, and waits for CI again.

Most "AI fixes your CI" tools stop at a suggestion. A suggestion you still have to verify is a second job. Firewatch's rule is that **nothing reaches a human until the tests pass on the patched code**.

## How it works

```mermaid
flowchart LR
    A[CI run fails] --> B[Firewatch workflow wakes up]
    B --> C[Fetch failed job logs<br/>and changed files]
    C --> D[Reproduce: run tests<br/>on the failing commit]
    D --> E[Triage: strip noise,<br/>extract error + file refs]
    E --> F[Retrieve context:<br/>traceback files + modules<br/>imported by failing tests]
    F --> G[Open model proposes<br/>search/replace edits]
    G --> H[Apply edits<br/>tests are read-only]
    H --> I{Re-run tests}
    I -- pass --> J[Push firewatch/ branch<br/>open PR with report]
    I -- fewer failures --> K[Keep change] --> F
    I -- no progress --> L[Revert change] --> F
    F -. max attempts .-> M[Comment with diagnosis<br/>and what was tried]
```

1. **Trigger.** A `workflow_run` workflow fires when your `CI` workflow concludes with `failure`.
2. **Reproduce.** It checks out the exact failing commit and runs your test command. If the failure doesn't reproduce, it reports "likely flaky" with a diagnosis from the CI logs instead of guessing at a fix.
3. **Triage.** GitHub log timestamps and ANSI codes are stripped, the pytest failure section is extracted, and every `file:line` reference is mapped back to a path in your repo (runner paths like `/home/runner/work/...` are normalized).
4. **Retrieve.** Open models break down when you paste a whole repository into the prompt. Firewatch builds a ranked context: files in the traceback first, then the modules that the failing test **imports** (found by parsing the test's AST, following imports two levels deep), then files changed in the failing commit. Large files are windowed around the referenced lines.
5. **Fix.** The model returns JSON with a diagnosis and `search/replace` edits.
6. **Verify.** Edits are applied and the tests are re-run. Pass → done. Fewer failures → the change is kept and the loop continues from the new state. No progress → the change is reverted, and the failed diff plus the new test output go into the next prompt so the model doesn't repeat itself.
7. **Report.** A pull request into the failing branch (and a comment on the original PR), or a diagnosis comment if no verified fix was found.

## Design decisions

These are the choices that made the difference between a demo and something I'd actually install.

**Verify inside the runner, not by pushing and waiting.** The obvious design is push a fix branch → wait for CI → read the result → retry. Each loop costs minutes, and pull requests opened with `GITHUB_TOKEN` [don't trigger workflows](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/triggering-a-workflow#triggering-a-workflow-from-a-workflow) anyway. Firewatch runs the test command itself on the checked-out commit, so each attempt takes seconds, and the PR only exists once the fix is proven.

**Search/replace edits instead of unified diffs.** Smaller open models are bad at producing valid diff hunks (line numbers drift, context lines get paraphrased). Copying an exact block of existing code is much easier for them. The patcher is forgiving where it's safe to be: it accepts a match that differs only in trailing whitespace, and re-indents a block the model returned with the wrong indentation. It refuses where it isn't safe: if a block matches in two places, the edit is rejected and the model is told to include more context.

**Tests are read-only by default.** The easiest way for a model to "fix" a failing test is to change the assertion. Edits to test files are rejected and the rejection is fed back to the model. You can opt in with `FIREWATCH_ALLOW_TEST_EDITS=true` for repos where tests are genuinely wrong.

**Keep partial progress.** If a patch takes the failures from 3 to 1, throwing it away wastes the work. Changes that strictly reduce the failure count are kept, and the next attempt starts from there. Changes that don't help are reverted byte for byte (line endings included, so it's safe on Windows checkouts).

**Interchangeable providers with fallback.** Any OpenAI-compatible endpoint works: Ollama locally, or a hosted open-model provider in CI. `FIREWATCH_PROVIDERS=ollama,remote` tries them in order, so if the local model isn't running, it falls back to the hosted one. There are no SDK dependencies; the only runtime dependency is `python-dotenv`.

**Talk to Ollama natively.** Ollama's OpenAI-compatible endpoint runs with a small default context window and silently drops the start of long prompts, which is where the instructions are. Firewatch calls Ollama's native `/api/chat` instead, with an explicit `num_ctx` (16k by default) and JSON mode, so a 7B model gets the whole prompt and can only answer in parseable JSON.

**Safe by default in CI.**
- Runs from forks are skipped, because checking out untrusted code in a job that holds a write token is a known Actions attack.
- Failures on `firewatch/*` branches are ignored, so it can't loop on its own output.
- Only the files Firewatch changed are committed, never stray artifacts.
- Paths are validated so the model can't write outside the repository or into `.git`.

## Benchmark

A fix rate measured against nothing tells you nothing, so Firewatch ships with a benchmark of 14 seeded bugs in `bench/cases`. Each one is a small realistic module with a test suite, and each bug category is one I've seen break real CI:

| Category | Cases |
|---|---|
| Off-by-one | pagination start index, retry loop that stops one attempt short |
| Boundary condition | `>` vs `>=` on a discount threshold, weekday check that misses Saturday |
| None handling | name formatting with a missing middle name |
| Import error | helper renamed in one module, old name still imported in another |
| Shared state | mutable default argument, function that mutates its input |
| Arithmetic | floor division in a mean |
| Wrong key | config key renamed |
| Sort order | leaderboard sorted ascending, with a tie-break that `reverse=True` would break |
| Exception contract | bare `Exception` where callers expect `ValueError` (two locations) |
| Formatting | one decimal place instead of two |
| Cross-file contract | tax module returns percentages, checkout treats them as fractions; the test pins the tax module's contract, so the fix must go in the other file |

`firewatch bench --validate` checks that every case fails before and passes with its reference fix. The reference fixes live in `case.json`, which is never copied into the workspace the model sees.

### Results

<!-- Replace with the output of bench/results/latest.md after running the benchmark -->
Run `firewatch bench` with your model and paste `bench/results/latest.md` here. Each run also writes a timestamped JSON file with every diagnosis, diff and rejected edit.

## Quick start

### Run locally against any repo

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/firewatch
cd firewatch
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -e ".[dev]"
copy .env.example .env          # Windows  (cp on macOS / Linux)
```

Pull a coding model with [Ollama](https://ollama.com) (`ollama pull qwen2.5-coder:7b`), or fill in `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` for a hosted provider. Then:

```bash
firewatch doctor                                  # checks every configured provider answers
firewatch fix --repo path/to/repo --report fix.md # reproduce, fix, verify
firewatch bench                                   # run the benchmark
firewatch bench --only tax_rate_units             # run one case
```

`fix` restores your files if it can't find a passing fix. Use `--keep-partial` to keep the best attempt anyway.

### Add it to a GitHub repository

1. Add two repository secrets: `FIREWATCH_LLM_BASE_URL` (any OpenAI-compatible endpoint serving open models) and `FIREWATCH_LLM_API_KEY`.
2. Add a repository variable `FIREWATCH_LLM_MODEL` with the model name.
3. In **Settings → Actions → General → Workflow permissions**, enable **Allow GitHub Actions to create and approve pull requests**.
4. Add `.github/workflows/firewatch.yml`:

```yaml
name: Firewatch
on:
  workflow_run:
    workflows: [CI]
    types: [completed]
permissions:
  contents: write
  pull-requests: write
  actions: read
jobs:
  heal:
    if: >-
      github.event.workflow_run.conclusion == 'failure' &&
      github.event.workflow_run.head_repository.full_name == github.repository &&
      !startsWith(github.event.workflow_run.head_branch, 'firewatch/')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.workflow_run.head_sha }}
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - uses: YOUR_GITHUB_USERNAME/firewatch@main
        with:
          test-command: python -m pytest -q
          llm-base-url: ${{ secrets.FIREWATCH_LLM_BASE_URL }}
          llm-api-key: ${{ secrets.FIREWATCH_LLM_API_KEY }}
          llm-model: ${{ vars.FIREWATCH_LLM_MODEL }}
```

`workflows: [CI]` must match the `name:` of your test workflow. A complete example repository is in [`examples/demo-shop`](examples/demo-shop).

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `FIREWATCH_PROVIDERS` | `ollama,remote` | Providers to try, in order |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | `http://localhost:11434/v1` / `qwen2.5-coder:7b` | Local model |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | none | Any OpenAI-compatible hosted provider |
| `FIREWATCH_MAX_ATTEMPTS` | `3` | Fix attempts before giving up |
| `FIREWATCH_ALLOW_TEST_EDITS` | `false` | Allow the model to edit test files |
| `FIREWATCH_CONTEXT_CHARS` | `24000` | Character budget for retrieved source files |
| `FIREWATCH_TEST_TIMEOUT` | `600` | Seconds before a test run is killed |

## Project layout

```
firewatch/
  triage.py     log cleaning, error extraction, file:line references, pytest summary parsing
  context.py    retrieval: traceback files, AST-based import following, windowing, budget
  fixer.py      prompt construction with attempt history, tolerant JSON parsing
  patcher.py    safe search/replace with whitespace and indentation recovery, snapshots
  verifier.py   runs the test command and counts failures
  agent.py      the reproduce → retrieve → fix → verify loop
  ci.py         GitHub Actions mode: event guards, branch, commit, PR, comments
  github.py     minimal GitHub REST client (standard library only)
  bench.py      benchmark runner and report
tests/          unit and end-to-end tests, including a real git push to a local remote
bench/cases/    14 seeded-bug cases
examples/       demo repository with CI and Firewatch workflows
```

The test suite runs the whole agent loop end to end with a scripted model, including: a wrong first attempt being reverted, partial progress being kept, a model trying to edit a test being refused, unparseable replies, and the CI flow pushing a real branch to a local bare git remote.

## Limitations

- The benchmark is Python and pytest only. Triage already resolves `file:line` references from Java, Go, JS and Ruby output (including bare filenames like `Cart.java:42` from JVM stack traces), but import-following retrieval is Python only.
- Bugs that need a design decision, not a code fix, are out of scope. Firewatch reports a diagnosis and stops.
- The fix is verified against your test suite, so it's only as good as your tests. That's why the PR is a PR and not a direct push.

## Built with Alan

<!-- Fill this in with how you actually used Alan during the build: which parts, which models, what worked, what you reported. -->

## License

MIT
