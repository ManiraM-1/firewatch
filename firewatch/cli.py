import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from pathlib import Path

from .agent import run_agent
from .config import load_settings
from .llm import LLMClient, LLMError
from .report import render_markdown

DEFAULT_TEST = "python -m pytest -q"


def _log(message):
    stamp = time.strftime("%H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)


def _client(settings):
    return LLMClient(settings.providers, settings.temperature, settings.request_timeout)


def cmd_fix(args):
    settings = load_settings(args.env)
    if args.max_attempts:
        settings.max_attempts = args.max_attempts
    llm = _client(settings)
    repo = str(Path(args.repo).resolve())
    _log(f"Firewatch on {repo} using {llm.describe()}")
    result = run_agent(repo, args.test, llm, settings, keep_partial=args.keep_partial, log=_log)

    markdown = render_markdown(result)
    if args.report:
        Path(args.report).write_text(markdown, encoding="utf-8")
        _log(f"Report written to {args.report}")
    if args.json:
        Path(args.json).write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")

    print()
    print(f"Status: {result.status}")
    if result.diagnosis:
        print(f"Root cause: {result.diagnosis}")
    if result.fixed:
        print(f"Fixed in {len(result.attempts)} attempt(s), {result.duration:.0f}s. Changed: {', '.join(result.changed_files)}")
        print()
        print(result.final_diff)
    elif result.message:
        print(result.message)
    return 0 if result.status in ("fixed", "no_failure") else 1


def cmd_ci(args):
    from .ci import run_ci

    settings = load_settings(args.env)
    if args.max_attempts:
        settings.max_attempts = args.max_attempts
    return run_ci(str(Path(args.repo).resolve()), args.test, _client(settings), settings, log=_log, open_pr=not args.no_pr)


def cmd_doctor(args):
    settings = load_settings(args.env)
    if not settings.providers:
        print("No providers configured. Copy .env.example to .env and fill it in.")
        return 1
    healthy = 0
    for provider in settings.providers:
        url = provider.base_url.rstrip("/") + "/models"
        headers = {"Authorization": f"Bearer {provider.api_key}"} if provider.api_key else {}
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
            names = [m.get("id") for m in data.get("data", [])]
            listed = provider.model in names if names else None
            note = "model found" if listed else ("model NOT in list" if listed is False else "model list empty")
            print(f"[ok]   {provider.name}: {provider.base_url} reachable, {note} ({provider.model})")
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            print(f"[fail] {provider.name}: {provider.base_url} -> {exc}")
            continue
        try:
            client = LLMClient([provider], 0, settings.request_timeout)
            reply, _, seconds = client.complete([{"role": "user", "content": "Reply with the single word: ready"}])
            print(f"       chat ok in {seconds:.1f}s: {reply.strip()[:60]!r}")
            healthy += 1
        except LLMError as exc:
            print(f"       chat failed: {exc}")
    return 0 if healthy else 1


def cmd_bench(args):
    from .bench import run_benchmark

    settings = load_settings(args.env)
    if args.max_attempts:
        settings.max_attempts = args.max_attempts
    return run_benchmark(
        cases_dir=args.cases,
        out_dir=args.out,
        settings=settings,
        only=args.only,
        validate=args.validate,
        log=_log,
    )


def build_parser():
    parser = argparse.ArgumentParser(prog="firewatch", description="Reproduce, fix and verify failing tests with open models.")
    parser.add_argument("--env", default=".env", help="path to the .env file")
    sub = parser.add_subparsers(dest="command", required=True)

    fix = sub.add_parser("fix", help="fix failing tests in a local repository")
    fix.add_argument("--repo", default=".")
    fix.add_argument("--test", default=DEFAULT_TEST)
    fix.add_argument("--max-attempts", type=int)
    fix.add_argument("--keep-partial", action="store_true", help="keep changes even if tests still fail")
    fix.add_argument("--report", help="write a markdown report to this path")
    fix.add_argument("--json", help="write the raw result as JSON")
    fix.set_defaults(func=cmd_fix)

    ci = sub.add_parser("ci", help="run inside GitHub Actions on a failed workflow_run")
    ci.add_argument("--repo", default=".")
    ci.add_argument("--test", default=DEFAULT_TEST)
    ci.add_argument("--max-attempts", type=int)
    ci.add_argument("--no-pr", action="store_true", help="only comment, never open a pull request")
    ci.set_defaults(func=cmd_ci)

    doctor = sub.add_parser("doctor", help="check that the configured model providers respond")
    doctor.set_defaults(func=cmd_doctor)

    bench = sub.add_parser("bench", help="run the seeded-bug benchmark")
    bench.add_argument("--cases", default="bench/cases")
    bench.add_argument("--out", default="bench/results")
    bench.add_argument("--only", nargs="*", help="run only these case names")
    bench.add_argument("--max-attempts", type=int)
    bench.add_argument("--validate", action="store_true", help="check every case fails before and passes with its reference fix")
    bench.set_defaults(func=cmd_bench)
    return parser


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except LLMError as exc:
        print(f"Model error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
