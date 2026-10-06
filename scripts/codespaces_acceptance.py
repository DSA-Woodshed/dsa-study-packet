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
REPOSITORY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+")
CODE_VERSION_RE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?")
COMMAND_TIMEOUT_SECONDS = 30


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
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise AcceptanceError(
            f"COMMAND: MISSING ({command[0]})\nNEXT: install it on the machine "
            "running this acceptance step"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise AcceptanceError(
            f"COMMAND: TIMED_OUT ({command[0]}; {COMMAND_TIMEOUT_SECONDS}s)\n"
            "NEXT: check the command's connection or editor context, then rerun"
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or "no command output"
        raise AcceptanceError(
            f"COMMAND: FAILED ({' '.join(command)})\nOBSERVED: {detail}\n"
            "NEXT: fix authentication or the named ref, then rerun"
        ) from exc
    except OSError as exc:
        raise AcceptanceError(
            f"COMMAND: UNAVAILABLE ({command[0]}; errno={exc.errno})\n"
            "NEXT: check executable permissions and host command support, then rerun"
        ) from exc
    return result.stdout.strip()


def _editor_metadata(root: Path) -> list[str]:
    """Record optional CLI metadata without treating it as editor attachment."""
    try:
        version_lines = _capture(["code", "--version"], root).splitlines()
        if not version_lines or CODE_VERSION_RE.fullmatch(version_lines[0]) is None:
            return [
                "EDITOR_CLI: UNAVAILABLE",
                "EDITOR_CLI_REASON: version output did not identify VS Code",
            ]
        extensions = _capture(["code", "--list-extensions", "--show-versions"], root)
    except AcceptanceError as exc:
        return [
            "EDITOR_CLI: UNAVAILABLE",
            f"EDITOR_CLI_REASON: {str(exc).splitlines()[0]}",
        ]
    return [
        "EDITOR_CLI: METADATA_RECORDED",
        f"VS_CODE_VERSION: {version_lines[0]}",
        "EXTENSION_LIST: RECORDED",
        *[f"EXTENSION: {line}" for line in extensions.splitlines() if line],
    ]


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


def _valid_repository(value: str, label: str) -> str:
    if REPOSITORY_RE.fullmatch(value) is None:
        raise AcceptanceError(
            f"{label}: INVALID\nEXPECTED: GitHub owner/repository\n"
            "NEXT: select the personal contribution fork"
        )
    return value


def _repository_record(root: Path, slug: str) -> dict[str, object]:
    try:
        record = json.loads(_capture(["gh", "api", f"repos/{slug}"], root))
    except json.JSONDecodeError as exc:
        raise AcceptanceError("REPOSITORY_METADATA: INVALID_JSON") from exc
    if (
        not isinstance(record, dict)
        or type(record.get("id")) is not int
        or record["id"] <= 0
        or not isinstance(record.get("full_name"), str)
        or REPOSITORY_RE.fullmatch(record["full_name"]) is None
    ):
        raise AcceptanceError("REPOSITORY_METADATA: INVALID_IDENTITY")
    return record


def _true_fork(root: Path, source_slug: str) -> tuple[str, str]:
    """Prove the selected source is a real fork of the product's stable ID."""
    product_slug = _valid_repository(_repository_slug(root), "PRODUCT_REPOSITORY")
    source_slug = _valid_repository(source_slug, "SOURCE_REPOSITORY")
    product = _repository_record(root, product_slug)
    source = _repository_record(root, source_slug)
    parent = source.get("parent")
    if (
        source.get("fork") is not True
        or not isinstance(parent, dict)
        or parent.get("id") != product["id"]
        or str(parent.get("full_name", "")).casefold()
        != str(product["full_name"]).casefold()
        or str(source["full_name"]).casefold() != source_slug.casefold()
    ):
        raise AcceptanceError(
            "SOURCE_RELATION: NOT_PRODUCT_FORK\n"
            f"PRODUCT_REPOSITORY: {product['full_name']}\n"
            "NEXT: fork the canonical product instead of copying a repository"
        )
    return str(product["full_name"]), str(source["full_name"])


def plan(root: Path, branch: str, repository: str | None = None) -> list[str]:
    """Resolve a branch on the personal fork, without pushing to the product."""
    branch = _valid_disposable_branch(branch)
    source_slug = repository or _remote_slug(
        _capture(["git", "remote", "get-url", "origin"], root)
    )
    if source_slug is None:
        raise AcceptanceError(
            "SOURCE_REPOSITORY: UNRECOGNIZED\n"
            "NEXT: pass --repository owner/personal-fork or repair origin"
        )
    product_slug, source_slug = _true_fork(root, source_slug)
    encoded_branch = quote(branch, safe="")
    expected_sha = _valid_sha(
        _capture(
            [
                "gh",
                "api",
                f"repos/{source_slug}/branches/{encoded_branch}",
                "--jq",
                ".commit.sha",
            ],
            root,
        ),
        "EXPECTED_SHA",
    )
    create_url = f"https://codespaces.new/{source_slug}/tree/{encoded_branch}"
    return [
        f"PRODUCT_REPOSITORY: {product_slug}",
        f"SOURCE_REPOSITORY: {source_slug}",
        "SOURCE_RELATION: TRUE_PRODUCT_FORK",
        f"BRANCH: {branch}",
        f"EXPECTED_SHA: {expected_sha}",
        f"CREATE_URL: {create_url}",
        "REPOSITORY_API_AUTH: PASS",
        "HOSTED_ACCEPTANCE: NOT_TESTED",
        "FEEDBACK_PROVIDER: OPTIONAL_NOT_TESTED",
        "PROTECTED_CAPABILITY: OPTIONAL_NOT_TESTED",
        "NEXT: use CREATE_URL to create a new Codespace, then run "
        f"`just codespaces-acceptance-verify {expected_sha} {source_slug}` inside it",
    ]


def verify(
    root: Path, expected_sha: str, env: Mapping[str, str], repository: str
) -> list[str]:
    """Verify exact fork identity and SHA without selecting a feedback provider."""
    source_slug = _valid_repository(repository, "SOURCE_REPOSITORY")
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
    if observed_slug is None or observed_slug.casefold() != source_slug.casefold():
        raise AcceptanceError(
            f"ORIGIN_REPOSITORY: {observed_slug or 'UNRECOGNIZED'}\n"
            f"EXPECTED_REPOSITORY: {source_slug}\n"
            "NEXT: delete this Codespace and create it from the recorded repository URL"
        )

    product_slug, source_slug = _true_fork(root, source_slug)

    return [
        f"PRODUCT_REPOSITORY: {product_slug}",
        f"SOURCE_REPOSITORY: {source_slug}",
        "SOURCE_RELATION: TRUE_PRODUCT_FORK",
        f"CODESPACE_NAME: {codespace_name}",
        f"EXPECTED_SHA: {expected_sha}",
        f"CHECKOUT_SHA: {checkout_sha}",
        "WORKTREE: CLEAN (ignored private state excluded)",
        "REPOSITORY_CHECKOUT: PASS",
        *_editor_metadata(root),
        "NATIVE_EDITOR_ACCEPTANCE: NOT_TESTED",
        "REPOSITORY_WRITE_AUTH: NOT_TESTED",
        "HOSTED_PRACTICE_ACCEPTANCE: NOT_TESTED",
        "FEEDBACK_PROVIDER: OPTIONAL_NOT_TESTED",
        "PROTECTED_CAPABILITY: OPTIONAL_NOT_TESTED",
        "NEXT: attach the supported editor and verify the candidate files open; "
        "run the source-native practice and persistence acceptance; "
        "optional feedback and protected capabilities require their own selected "
        "evidence. Remove the disposable Codespace when done.",
    ]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--branch", required=True)
    plan_parser.add_argument("--repository", help="Personal fork; defaults to origin")
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--expected-sha", required=True)
    verify_parser.add_argument(
        "--repository", required=True, help="SOURCE_REPOSITORY from the plan"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        lines = (
            plan(ROOT, args.branch, args.repository)
            if args.command == "plan"
            else verify(ROOT, args.expected_sha, os.environ, args.repository)
        )
    except AcceptanceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
