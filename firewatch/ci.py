import json
import os
import re
import subprocess

from .agent import run_agent
from .github import GitHub, GitHubError
from .report import render_markdown

BRANCH_PREFIX = "firewatch/"


def summary_title(diagnosis, limit=72):
    text = " ".join((diagnosis or "").split())
    first = re.split(r"(?<=[.!?;])\s", text, maxsplit=1)[0].rstrip(".!?; ")
    if not first:
        return "repair failing tests"
    if len(first) > limit:
        cut = first[: limit - 1].rsplit(" ", 1)[0].rstrip(",:;")
        first = cut + "…"
    return first


def _git(repo_root, *args):
    return subprocess.run(["git", *args], cwd=repo_root, check=True, capture_output=True, text=True).stdout.strip()


def _set_output(name, value):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def _summary(markdown):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(markdown + "\n")


def load_event():
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path or not os.path.exists(path):
        raise GitHubError("GITHUB_EVENT_PATH is missing; CI mode must run inside GitHub Actions")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def run_ci(repo_root, test_command, llm, settings, log=print, open_pr=True):
    event = load_event()
    run = event.get("workflow_run") or {}
    if not run:
        log("Not a workflow_run event. Nothing to do.")
        return 0
    if run.get("conclusion") != "failure":
        log(f"Upstream run concluded '{run.get('conclusion')}'. Nothing to fix.")
        return 0

    head_branch = run.get("head_branch") or ""
    head_sha = run.get("head_sha") or ""
    if head_branch.startswith(BRANCH_PREFIX):
        log("Failure is on a Firewatch branch. Skipping to avoid a fix loop.")
        return 0

    repository = os.environ.get("GITHUB_REPOSITORY", "")
    head_repo = (run.get("head_repository") or {}).get("full_name", repository)
    if head_repo != repository:
        log(f"Run came from fork {head_repo}. Skipping: running untrusted code with a write token is unsafe.")
        return 0

    github = GitHub(os.environ.get("GITHUB_TOKEN", ""), repository, os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    run_id = run.get("id")
    run_url = run.get("html_url")
    log(f"Investigating failed run {run_id} on {head_branch}@{head_sha[:7]}")

    try:
        ci_log = github.failed_job_logs(run_id)
    except GitHubError as exc:
        log(f"Could not fetch logs: {exc}")
        ci_log = ""
    try:
        changed = github.commit_files(head_sha) if head_sha else []
    except GitHubError:
        changed = []

    result = run_agent(repo_root, test_command, llm, settings, ci_log=ci_log or None, changed_files=changed, log=log)
    _set_output("status", result.status)

    pulls = run.get("pull_requests") or github.pulls_for_commit(head_sha)
    pr_number = pulls[0]["number"] if pulls else None

    if result.fixed and open_pr:
        branch = f"{BRANCH_PREFIX}fix-{head_sha[:7]}-{run_id}"
        _git(repo_root, "config", "user.name", "firewatch[bot]")
        _git(repo_root, "config", "user.email", "firewatch-bot@users.noreply.github.com")
        _git(repo_root, "checkout", "-B", branch)
        _git(repo_root, "add", "--", *result.changed_files)
        title_hint = summary_title(result.diagnosis)
        _git(repo_root, "commit", "-m", f"fix: {title_hint}", "-m", "Automated fix by Firewatch. Verified by re-running the test suite.")
        _git(repo_root, "push", "origin", f"HEAD:refs/heads/{branch}", "--force")
        body = render_markdown(result, run_url, title="Firewatch fix")
        pr = github.create_pull(branch, head_branch, f"Firewatch: {title_hint}", body)
        log(f"Opened {pr.get('html_url')}")
        _set_output("pr_url", pr.get("html_url", ""))
        if pr_number:
            github.comment_on_issue(
                pr_number,
                f"CI failed on `{head_sha[:7]}`. Firewatch reproduced it, found a fix that passes the tests, "
                f"and opened {pr.get('html_url')} against `{head_branch}`.\n\n> {result.diagnosis}",
            )
        _summary(body)
        return 0

    body = render_markdown(result, run_url)
    _summary(body)
    if pr_number:
        github.comment_on_issue(pr_number, body)
    elif head_sha:
        github.comment_on_commit(head_sha, body)
    return 0 if result.status in ("fixed", "not_reproduced") else 1
