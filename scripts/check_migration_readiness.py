"""Check repository-owned links and pre-transfer retirement invariants.

The repository slug in ``tinyland.repo.json`` is the authority for mutable
GitHub links.  This guard deliberately does not contain a future owner: a
transfer patch changes the authority once, then updates every inventoried
surface in the same commit.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SITE = "https://dsa-woodshed.space"
REPOSITORY_NAME = "dsa-study-packet"

REPOSITORY_LINK_RE = re.compile(
    rf"https://(?:github\.com|codespaces\.new)/"
    rf"(?P<owner>[A-Za-z0-9_.-]+)/{REPOSITORY_NAME}(?:\.git)?(?![A-Za-z0-9_.-])"
)
LEGACY_PAGES_RE = re.compile(
    rf"https?://(?:www\.)?[A-Za-z0-9_.-]+\.github\.io/{REPOSITORY_NAME}/?",
    re.IGNORECASE,
)

# Every tracked surface allowed to contain an owner-qualified repository link.
# Adding one elsewhere is a migration-sensitive change and must extend this
# inventory intentionally.
OWNER_LINK_INVENTORY = frozenset(
    {
        "CONTRIBUTING.md",
        "README.md",
        "docs/guide/getting-started.md",
        "docs/guide/local-practice.md",
        "docs/index.md",
        "mkdocs.yml",
    }
)

LEARNER_CODESPACES_SURFACES = (
    "README.md",
    "docs/guide/getting-started.md",
    "docs/index.md",
)
ACCEPTANCE_SURFACES = ("CONTRIBUTING.md",)
ACCEPTANCE_FORK_URL = (
    "https://codespaces.new/YOUR-USER/dsa-study-packet-contrib/tree/<disposable-branch>"
)
ISSUE_TEMPLATE_SURFACES = (
    ".github/ISSUE_TEMPLATE/bug.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/idea.yml",
)
INTENTIONAL_FIXTURE_SURFACES = frozenset({"tests/test_migration_readiness.py"})

PAGES_CONTINUITY_NOTICE = (
    "The packet's legacy GitHub Pages setting still serves only a noindex redirect "
    "to the production site during pre-transfer continuity"
)
PAGES_WORKFLOW_MARKERS = (
    "actions/configure-pages",
    "actions/deploy-pages",
    "actions/upload-pages-artifact",
    "environment: github-pages",
    "mkdocs gh-deploy",
    "pages: write",
    "gh-pages",
)


def _repository_slug(root: Path) -> str:
    metadata_path = root / "tinyland.repo.json"
    try:
        metadata = json.loads(metadata_path.read_text())
        slug = metadata["repo"]["github"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError(f"{metadata_path.name}: cannot read repo.github") from exc
    if not isinstance(slug, str) or slug.count("/") != 1:
        raise ValueError("tinyland.repo.json: repo.github must be owner/name")
    owner, name = slug.split("/", 1)
    if not owner or name != REPOSITORY_NAME:
        raise ValueError(
            "tinyland.repo.json: repo.github must name the dsa-study-packet repo"
        )
    return slug


def _tracked_text_files(root: Path) -> list[Path]:
    """Return tracked inputs; the caller decodes every nonbinary file."""
    ignored_parts = {
        ".git",
        ".venv",
        ".challenges",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".serena",
        "__pycache__",
        "bazel-bin",
        "bazel-out",
        "bazel-testlogs",
        "site",
    }
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.split("\0")
    except FileNotFoundError, subprocess.CalledProcessError:
        candidates = root.rglob("*")
    else:
        candidates = (root / relative for relative in tracked if relative)
    return sorted(
        path
        for path in candidates
        if path.is_file()
        and not any(part in ignored_parts for part in path.relative_to(root).parts)
        and path.relative_to(root).as_posix() not in INTENTIONAL_FIXTURE_SURFACES
    )


def check(root: Path) -> list[str]:
    """Return actionable failures for the packet migration-readiness contract."""
    failures: list[str] = []
    try:
        slug = _repository_slug(root)
    except ValueError as exc:
        return [str(exc)]

    expected_repo_url = f"https://github.com/{slug}"
    expected_codespaces = f"https://codespaces.new/{slug}"

    seen_owner_surfaces: set[str] = set()
    for path in _tracked_text_files(root):
        relative = path.relative_to(root).as_posix()
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        if "\x00" in text:
            continue

        if LEGACY_PAGES_RE.search(text):
            failures.append(
                f"{relative}: contains the retired packet Pages URL; use "
                f"{CANONICAL_SITE} instead"
            )

        links = list(REPOSITORY_LINK_RE.finditer(text))
        if not links:
            continue
        seen_owner_surfaces.add(relative)
        if relative not in OWNER_LINK_INVENTORY:
            failures.append(
                f"{relative}: owner-qualified repository link is missing from "
                "OWNER_LINK_INVENTORY"
            )
        for link in links:
            observed = link.group(0).removesuffix(".git")
            if observed not in {expected_repo_url, expected_codespaces}:
                failures.append(
                    f"{relative}: repository link owner disagrees with "
                    f"tinyland.repo.json ({observed})"
                )

    missing_inventory = sorted(OWNER_LINK_INVENTORY - seen_owner_surfaces)
    failures.extend(
        f"{relative}: inventoried owner-qualified repository link is missing"
        for relative in missing_inventory
    )

    for relative in LEARNER_CODESPACES_SURFACES:
        path = root / relative
        text = path.read_text() if path.is_file() else ""
        expected = f"{expected_codespaces}?quickstart=1"
        if expected not in text:
            failures.append(f"{relative}: missing learner Codespaces link {expected}")

    readme_path = root / "README.md"
    readme = readme_path.read_text() if readme_path.is_file() else ""
    badge = (
        "[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)]"
        f"({expected_codespaces}?quickstart=1)"
    )
    if badge not in readme:
        failures.append("README.md: missing owner-correct Codespaces badge target")

    for relative in ACCEPTANCE_SURFACES:
        path = root / relative
        text = path.read_text() if path.is_file() else ""
        branch_url = ACCEPTANCE_FORK_URL
        if branch_url not in text:
            failures.append(
                f"{relative}: missing personal-fork acceptance URL {branch_url}"
            )
        if "?quickstart=1" in text:
            failures.append(
                f"{relative}: acceptance instructions must not use quickstart/resume"
            )

    mkdocs_path = root / "mkdocs.yml"
    mkdocs = mkdocs_path.read_text() if mkdocs_path.is_file() else ""
    for expected in (
        f"site_url: {CANONICAL_SITE}/",
        f"repo_url: {expected_repo_url}",
        f"repo_name: {slug}",
        "edit_uri: edit/main/docs/",
        "- content.action.edit",
    ):
        if expected not in mkdocs:
            failures.append(f"mkdocs.yml: missing canonical metadata `{expected}`")

    release_path = root / ".github/workflows/release.yml"
    release = release_path.read_text() if release_path.is_file() else ""
    if 'gh release create "$GITHUB_REF_NAME"' not in release:
        failures.append(
            ".github/workflows/release.yml: missing repository-context release publish"
        )
    contribution_path = root / "CONTRIBUTING.md"
    contribution = contribution_path.read_text() if contribution_path.is_file() else ""
    release_url = f"{expected_repo_url}/releases"
    if release_url not in contribution:
        failures.append(
            f"CONTRIBUTING.md: missing release inventory link {release_url}"
        )

    source_truth_path = root / "docs/guide/source-of-truth.md"
    source_truth = source_truth_path.read_text() if source_truth_path.is_file() else ""
    if PAGES_CONTINUITY_NOTICE not in " ".join(source_truth.split()):
        failures.append(
            "docs/guide/source-of-truth.md: missing legacy Pages continuity notice"
        )
    workflows = root / ".github/workflows"
    for workflow_path in sorted((*workflows.glob("*.yml"), *workflows.glob("*.yaml"))):
        workflow = workflow_path.read_text()
        if any(marker in workflow for marker in PAGES_WORKFLOW_MARKERS):
            failures.append(
                f"{workflow_path.relative_to(root).as_posix()}: packet Pages "
                "deployment must remain absent before legacy setting retirement"
            )

    for relative in ISSUE_TEMPLATE_SURFACES:
        if not (root / relative).is_file():
            failures.append(f"{relative}: missing issue migration surface")

    return failures


def main() -> int:
    failures = check(ROOT)
    if failures:
        print("Migration readiness failed:")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print(
        "Migration readiness passed: owner links, Codespaces entrypoints, "
        "release path, canonical metadata, issue templates, and Pages retirement preparation agree."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
