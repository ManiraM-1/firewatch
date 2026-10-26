import json
import subprocess

from conftest import as_reply

import firewatch.ci as ci
from firewatch.llm import ScriptedLLM


class FakeGitHub:
    instances = []

    def __init__(self, token, repository, api_url=None):
        self.repository = repository
        self.pulls = []
        self.issue_comments = []
        self.commit_comments = []
        FakeGitHub.instances.append(self)

    def failed_job_logs(self, run_id):
        return "FAILED tests/test_pagination.py::test_first_page - assert [10, 11] == [0, 1]\n1 failed in 0.1s"

    def commit_files(self, sha):
        return ["pagination.py"]

    def pulls_for_commit(self, sha):
        return [{"number": 7}]

    def create_pull(self, head, base, title, body):
        self.pulls.append({"head": head, "base": base, "title": title, "body": body})
        return {"html_url": f"https://github.com/{self.repository}/pull/8"}

    def comment_on_issue(self, number, body):
        self.issue_comments.append((number, body))

    def comment_on_commit(self, sha, body):
        self.commit_comments.append((sha, body))


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def setup_repo(tmp_path, case_repo):
    repo, solution = case_repo("pagination_off_by_one")
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "dev@example.com")
    git(repo, "config", "user.name", "dev")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "add pagination")
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "main")
    return repo, solution, remote, git(repo, "rev-parse", "HEAD")


def write_event(tmp_path, monkeypatch, sha, branch="main", conclusion="failure", head_repo="me/shop"):
    event = {
        "workflow_run": {
            "id": 42,
            "conclusion": conclusion,
            "head_branch": branch,
            "head_sha": sha,
            "html_url": "https://github.com/me/shop/actions/runs/42",
            "head_repository": {"full_name": head_repo},
            "pull_requests": [],
        }
    }
    path = tmp_path / "event.json"
    path.write_text(json.dumps(event))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(path))
    monkeypatch.setenv("GITHUB_REPOSITORY", "me/shop")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out.txt"))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    monkeypatch.setattr(ci, "GitHub", FakeGitHub)
    FakeGitHub.instances.clear()


def test_ci_pushes_verified_fix_and_opens_pr(tmp_path, monkeypatch, case_repo, settings):
    repo, solution, remote, sha = setup_repo(tmp_path, case_repo)
    write_event(tmp_path, monkeypatch, sha)
    code = ci.run_ci(str(repo), "python -m pytest -q -p no:cacheprovider", ScriptedLLM([as_reply(solution, "start index off by one page")]), settings, log=lambda _m: None)
    assert code == 0
    gh = FakeGitHub.instances[0]
    assert gh.pulls[0]["base"] == "main"
    assert gh.pulls[0]["head"] == f"firewatch/fix-{sha[:7]}-42"
    assert "start index off by one page" in gh.pulls[0]["body"]
    assert gh.issue_comments and gh.issue_comments[0][0] == 7
    pushed = git(remote, "show", f"firewatch/fix-{sha[:7]}-42:pagination.py")
    assert "(page - 1) * size" in pushed
    changed = git(remote, "diff", "--name-only", "main", f"firewatch/fix-{sha[:7]}-42")
    assert changed == "pagination.py"
    assert "status=fixed" in (tmp_path / "out.txt").read_text()


def test_ci_comments_when_it_cannot_fix(tmp_path, monkeypatch, case_repo, settings):
    repo, _, _, sha = setup_repo(tmp_path, case_repo)
    write_event(tmp_path, monkeypatch, sha)
    llm = ScriptedLLM(["no idea"] * 3)
    code = ci.run_ci(str(repo), "python -m pytest -q -p no:cacheprovider", llm, settings, log=lambda _m: None)
    gh = FakeGitHub.instances[0]
    assert code == 1
    assert not gh.pulls
    assert "Could not produce a passing fix" in gh.issue_comments[0][1]


def test_ci_skips_its_own_branches_and_forks(tmp_path, monkeypatch, case_repo, settings):
    repo, _, _, sha = setup_repo(tmp_path, case_repo)
    write_event(tmp_path, monkeypatch, sha, branch="firewatch/fix-abc-1")
    assert ci.run_ci(str(repo), "x", ScriptedLLM([]), settings, log=lambda _m: None) == 0
    write_event(tmp_path, monkeypatch, sha, head_repo="stranger/shop")
    assert ci.run_ci(str(repo), "x", ScriptedLLM([]), settings, log=lambda _m: None) == 0
    write_event(tmp_path, monkeypatch, sha, conclusion="success")
    assert ci.run_ci(str(repo), "x", ScriptedLLM([]), settings, log=lambda _m: None) == 0
    assert not any(i.pulls for i in FakeGitHub.instances)


def test_pr_title_keeps_dotted_names_and_stops_at_the_sentence():
    assert ci.summary_title("Cart.tax multiplies by the GST percentage instead of a fraction. Divide by 100.") == (
        "Cart.tax multiplies by the GST percentage instead of a fraction"
    )
    assert ci.summary_title("") == "repair failing tests"
    long = "The retry loop " + "keeps going " * 20
    title = ci.summary_title(long)
    assert len(title) <= 72 and title.endswith("…") and "  " not in title
