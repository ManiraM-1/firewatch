import io
import json
import urllib.error
import urllib.request
import zipfile

API = "https://api.github.com"


class GitHubError(Exception):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHub:
    def __init__(self, token, repository, api_url=API):
        if not token or not repository:
            raise GitHubError("GITHUB_TOKEN and GITHUB_REPOSITORY are required in CI mode")
        self.token = token
        self.repository = repository
        self.api_url = api_url.rstrip("/")

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "firewatch",
        }

    def request(self, method, path, body=None):
        url = path if path.startswith("http") else f"{self.api_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = self._headers()
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise GitHubError(f"{method} {path} -> HTTP {exc.code}: {detail}") from exc
        return json.loads(raw.decode("utf-8")) if raw else {}

    def _download(self, path):
        opener = urllib.request.build_opener(_NoRedirect)
        req = urllib.request.Request(f"{self.api_url}{path}", headers=self._headers())
        try:
            with opener.open(req, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308):
                location = exc.headers.get("Location")
                with urllib.request.urlopen(location, timeout=120) as response:
                    return response.read()
            raise GitHubError(f"GET {path} -> HTTP {exc.code}") from exc

    def failed_job_logs(self, run_id, max_chars=60000):
        jobs = self.request("GET", f"/repos/{self.repository}/actions/runs/{run_id}/jobs?per_page=100")
        chunks = []
        for job in jobs.get("jobs", []):
            if job.get("conclusion") not in ("failure", "timed_out"):
                continue
            failed_steps = [s["name"] for s in job.get("steps", []) if s.get("conclusion") == "failure"]
            try:
                text = self._download(f"/repos/{self.repository}/actions/jobs/{job['id']}/logs").decode(
                    "utf-8", errors="replace"
                )
            except GitHubError:
                text = self._run_logs_for_job(run_id, job.get("name", ""))
            header = f"=== job: {job.get('name')} | failed steps: {', '.join(failed_steps) or 'unknown'} ==="
            chunks.append(header + "\n" + text[-max_chars:])
        return "\n\n".join(chunks)

    def _run_logs_for_job(self, run_id, job_name):
        try:
            blob = self._download(f"/repos/{self.repository}/actions/runs/{run_id}/logs")
        except GitHubError:
            return ""
        texts = []
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            for name in archive.namelist():
                if job_name and job_name in name:
                    texts.append(archive.read(name).decode("utf-8", errors="replace"))
        return "\n".join(texts)

    def commit_files(self, sha):
        data = self.request("GET", f"/repos/{self.repository}/commits/{sha}")
        return [f["filename"] for f in data.get("files", []) if f.get("status") != "removed"]

    def pulls_for_commit(self, sha):
        try:
            return self.request("GET", f"/repos/{self.repository}/commits/{sha}/pulls")
        except GitHubError:
            return []

    def create_pull(self, head, base, title, body):
        return self.request(
            "POST",
            f"/repos/{self.repository}/pulls",
            {"head": head, "base": base, "title": title, "body": body, "maintainer_can_modify": True},
        )

    def comment_on_issue(self, number, body):
        return self.request("POST", f"/repos/{self.repository}/issues/{number}/comments", {"body": body})

    def comment_on_commit(self, sha, body):
        return self.request("POST", f"/repos/{self.repository}/commits/{sha}/comments", {"body": body})
