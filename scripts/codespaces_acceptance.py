"""Plan and verify a genuinely new, exact-SHA Codespaces acceptance run."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
SHA_RE = re.compile(r"[0-9a-f]{40}")
DISPOSABLE_BRANCH_RE = re.compile(r"codespaces-acceptance-[A-Za-z0-9._-]+")


class AcceptanceError(RuntimeError):
    """One failed acceptance invariant with a safe next step."""


def _repository_slug(root: Path) -> str:
    try:
        metadata = json.loads((root / "tinyland.repo.json").read_text())
        slug = metadata["repo"]["github"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise AcceptanceError(
            "REPOSITORY: UNKNOWN\nNEXT: repair tinyland.repo.json repo.github"
        ) from exc
    if not isinstance(slug, str) or slug.count("/") != 1:
        raise AcceptanceError(
            "REPOSITORY: INVALID\nNEXT: set tinyland.repo.json repo.github to owner/name"
        )
    return slug


def _capture(command: Sequence[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise AcceptanceError(
            f"COMMAND: MISSING ({command[0]})\nNEXT: install it on the machine "
            "running this acceptance step"
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or "no command output"
        raise AcceptanceError(
            f"COMMAND: FAILED ({' '.join(command)})\nOBSERVED: {detail}\n"
            "NEXT: fix authentication or the named ref, then rerun"
        ) from exc
    return result.stdout.strip()


def _valid_sha(value: str, label: str) -> str:
    normalized = value.strip()
    if SHA_RE.fullmatch(normalized) is None:
        raise AcceptanceError(
            f"{label}: INVALID ({value})\nEXPECTED: 40 lowercase hexadecimal characters\n"
            "NEXT: resolve and record the exact remote commit SHA"
        )
    return normalized


def _valid_disposable_branch(value: str) -> str:
    if DISPOSABLE_BRANCH_RE.fullmatch(value) is None:
        raise AcceptanceError(
            f"BRANCH: INVALID ({value})\n"
            "EXPECTED: codespaces-acceptance-<unique-suffix>\n"
            "NEXT: push a disposable branch with that prefix at the commit under test"
        )
    return value


def _remote_slug(remote: str) -> str | None:
    patterns = (
        re.compile(r"https://github\.com/(?P<slug>[^/]+/[^/]+?)(?:\.git)?/?$"),
        re.compile(r"git@github\.com:(?P<slug>[^/]+/[^/]+?)(?:\.git)?$"),
        re.compile(r"ssh://git@github\.com/(?P<slug>[^/]+/[^/]+?)(?:\.git)?/?$"),
    )
    for pattern in patterns:
        match = pattern.fullmatch(remote.strip())
        if match is not None:
            return match.group("slug")
    return None


def plan(root: Path, branch: str) -> list[str]:
    """Resolve a disposable remote branch and return exact creation evidence."""
    slug = _repository_slug(root)
    branch = _valid_disposable_branch(branch)
    encoded_branch = quote(branch, safe="")
    expected_sha = _valid_sha(
        _capture(
            [
                "gh",
                "api",
                f"repos/{slug}/branches/{encoded_branch}",
                "--jq",
                ".commit.sha",
            ],
            root,
        ),
        "EXPECTED_SHA",
    )
    create_url = f"https://codespaces.new/{slug}/tree/{encoded_branch}"
    return [
        f"REPOSITORY: {slug}",
        f"BRANCH: {branch}",
        f"EXPECTED_SHA: {expected_sha}",
        f"CREATE_URL: {create_url}",
        "REPOSITORY_API_AUTH: PASS",
        "COPILOT_SIGN_IN: NOT_TESTED",
        "COPILOT_ENTITLEMENT: NOT_TESTED",
        "NEXT: use CREATE_URL to create a new Codespace, then run "
        f"`just codespaces-acceptance-verify {expected_sha}` inside it",
    ]


def verify(root: Path, expected_sha: str, env: Mapping[str, str]) -> list[str]:
    """Verify checkout identity without claiming Copilot UI account state."""
    slug = _repository_slug(root)
    expected_sha = _valid_sha(expected_sha, "EXPECTED_SHA")
    if env.get("CODESPACES", "").lower() != "true":
        raise AcceptanceError(
            "CODESPACES: NOT_DETECTED\nEXPECTED: CODESPACES=true\n"
            "NEXT: run this command in the newly created Codespace terminal"
        )
    codespace_name = env.get("CODESPACE_NAME", "").strip()
    if not codespace_name:
        raise AcceptanceError(
            "CODESPACE_NAME: MISSING\nEXPECTED: a named disposable Codespace\n"
            "NEXT: rerun inside the newly created Codespace terminal"
        )

    checkout_sha = _valid_sha(
        _capture(["git", "rev-parse", "HEAD"], root), "CHECKOUT_SHA"
    )
    if checkout_sha != expected_sha:
        raise AcceptanceError(
            f"CHECKOUT_SHA: {checkout_sha}\nEXPECTED_SHA: {expected_sha}\n"
            "NEXT: delete this stale Codespace and create a new one from the recorded branch URL"
        )

    tracked_status = _capture(
        ["git", "status", "--porcelain=v1", "--untracked-files=normal"], root
    )
    if tracked_status:
        raise AcceptanceError(
            "WORKTREE: DIRTY\n"
            f"OBSERVED: {tracked_status}\n"
            "NEXT: create a new Codespace from the recorded branch URL; "
            "do not use a lifecycle-mutated checkout as exact-head evidence"
        )

    remote = _capture(["git", "remote", "get-url", "origin"], root)
    observed_slug = _remote_slug(remote)
    if observed_slug != slug:
        raise AcceptanceError(
            f"ORIGIN_REPOSITORY: {observed_slug or 'UNRECOGNIZED'}\n"
            f"EXPECTED_REPOSITORY: {slug}\n"
            "NEXT: delete this Codespace and create it from the recorded repository URL"
        )

    code_version = _capture(["code", "--version"], root).splitlines()[0]
    extensions = _capture(["code", "--list-extensions", "--show-versions"], root)
    return [
        f"REPOSITORY: {slug}",
        f"CODESPACE_NAME: {codespace_name}",
        f"EXPECTED_SHA: {expected_sha}",
        f"CHECKOUT_SHA: {checkout_sha}",
        "WORKTREE: CLEAN (ignored private state excluded)",
        "REPOSITORY_CHECKOUT: PASS",
        f"VS_CODE_VERSION: {code_version}",
        "EXTENSION_LIST: RECORDED",
        *[f"EXTENSION: {line}" for line in extensions.splitlines() if line],
        "REPOSITORY_WRITE_AUTH: NOT_TESTED",
        "COPILOT_SIGN_IN: MANUAL_UI_REQUIRED",
        "COPILOT_ENTITLEMENT: MANUAL_UI_REQUIRED",
        "NEXT: confirm Copilot sign-in and entitlement in the editor UI, then run "
        "the source-native practice acceptance and remove the disposable Codespace",
    ]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--branch", required=True)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--expected-sha", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        lines = (
            plan(ROOT, args.branch)
            if args.command == "plan"
            else verify(ROOT, args.expected_sha, os.environ)
        )
    except AcceptanceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
