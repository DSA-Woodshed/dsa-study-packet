"""Tests for owner-link inventory and packet Pages retirement preparation."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_migration_readiness import (  # type: ignore[import-not-found]
    ACCEPTANCE_SURFACES,
    ISSUE_TEMPLATE_SURFACES,
    LEARNER_CODESPACES_SURFACES,
    OWNER_LINK_INVENTORY,
    check,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _mirror_contract(dst: Path) -> None:
    relatives = {
        *OWNER_LINK_INVENTORY,
        *ACCEPTANCE_SURFACES,
        *ISSUE_TEMPLATE_SURFACES,
        *LEARNER_CODESPACES_SURFACES,
        ".github/workflows/release.yml",
        "docs/guide/source-of-truth.md",
        "tinyland.repo.json",
    }
    for relative in relatives:
        source = REPO_ROOT / relative
        target = dst / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def test_real_repository_is_migration_ready() -> None:
    assert check(REPO_ROOT) == []


def test_owner_disagreement_is_caught(tmp_path: Path) -> None:
    _mirror_contract(tmp_path)
    readme = tmp_path / "README.md"
    slug = json.loads((tmp_path / "tinyland.repo.json").read_text())["repo"]["github"]
    readme.write_text(readme.read_text().replace(slug, "WrongOwner/dsa-study-packet"))

    failures = check(tmp_path)

    assert any("repository link owner disagrees" in failure for failure in failures)


def test_authority_and_owner_links_change_together(tmp_path: Path) -> None:
    _mirror_contract(tmp_path)
    slug = json.loads((tmp_path / "tinyland.repo.json").read_text())["repo"]["github"]
    for relative in {*OWNER_LINK_INVENTORY, "tinyland.repo.json"}:
        path = tmp_path / relative
        path.write_text(path.read_text().replace(slug, "NewAuthority/dsa-study-packet"))

    assert check(tmp_path) == []


def test_new_owner_link_requires_inventory_entry(tmp_path: Path) -> None:
    _mirror_contract(tmp_path)
    extra = tmp_path / "docs/extra.md"
    extra.parent.mkdir(parents=True, exist_ok=True)
    extra.write_text("https://github.com/Jesssullivan/dsa-study-packet/issues")

    assert (
        "docs/extra.md: owner-qualified repository link is missing from "
        "OWNER_LINK_INVENTORY"
    ) in check(tmp_path)


def test_owner_link_in_non_whitelisted_extension_is_scanned(tmp_path: Path) -> None:
    _mirror_contract(tmp_path)
    extra = tmp_path / "BUILD.bazel"
    extra.write_text("# https://github.com/Jesssullivan/dsa-study-packet/issues\n")

    assert (
        "BUILD.bazel: owner-qualified repository link is missing from "
        "OWNER_LINK_INVENTORY"
    ) in check(tmp_path)


def test_gitignored_local_state_cannot_affect_inventory(tmp_path: Path) -> None:
    _mirror_contract(tmp_path)
    local = tmp_path / ".serena/private.md"
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text("https://github.com/Elsewhere/dsa-study-packet")

    assert check(tmp_path) == []


def test_retired_pages_url_is_caught(tmp_path: Path) -> None:
    _mirror_contract(tmp_path)
    extra = tmp_path / "docs/extra.md"
    extra.parent.mkdir(parents=True, exist_ok=True)
    extra.write_text("https://jesssullivan.github.io/dsa-study-packet/")

    assert any(
        "contains the retired packet Pages URL" in item for item in check(tmp_path)
    )


def test_acceptance_quickstart_is_caught(tmp_path: Path) -> None:
    _mirror_contract(tmp_path)
    acceptance = tmp_path / "CONTRIBUTING.md"
    acceptance.write_text(acceptance.read_text() + "\n?quickstart=1\n")

    assert (
        "CONTRIBUTING.md: acceptance instructions must not use quickstart/resume"
    ) in check(tmp_path)


def test_pages_workflow_is_caught(tmp_path: Path) -> None:
    _mirror_contract(tmp_path)
    pages = tmp_path / ".github/workflows/docs.yml"
    pages.write_text("steps:\n  - uses: actions/deploy-pages@v4\n")

    assert (
        ".github/workflows/docs.yml: packet Pages deployment must remain absent "
        "before legacy setting retirement"
    ) in check(tmp_path)


def test_raw_gh_pages_push_is_caught(tmp_path: Path) -> None:
    _mirror_contract(tmp_path)
    pages = tmp_path / ".github/workflows/legacy-pages.yml"
    pages.write_text("steps:\n  - run: git push origin HEAD:gh-pages\n")

    assert (
        ".github/workflows/legacy-pages.yml: packet Pages deployment must remain "
        "absent before legacy setting retirement"
    ) in check(tmp_path)


def test_missing_canonical_edit_path_is_caught(tmp_path: Path) -> None:
    _mirror_contract(tmp_path)
    mkdocs = tmp_path / "mkdocs.yml"
    mkdocs.write_text(mkdocs.read_text().replace("edit_uri: edit/main/docs/\n", ""))

    assert (
        "mkdocs.yml: missing canonical metadata `edit_uri: edit/main/docs/`"
    ) in check(tmp_path)


def test_true_contribution_fork_url_is_not_a_product_owner_link(tmp_path: Path) -> None:
    _mirror_contract(tmp_path)
    path = tmp_path / "CONTRIBUTING.md"
    path.write_text(
        path.read_text()
        + "\nhttps://github.com/Contributor/dsa-study-packet-contrib.git\n"
    )
    assert check(tmp_path) == []


def test_org_product_branch_is_not_a_personal_fork_acceptance_source(
    tmp_path: Path,
) -> None:
    _mirror_contract(tmp_path)
    path = tmp_path / "CONTRIBUTING.md"
    text = path.read_text().replace(
        "https://codespaces.new/YOUR-USER/dsa-study-packet-contrib/tree/<disposable-branch>",
        "https://codespaces.new/Jesssullivan/dsa-study-packet/tree/<disposable-branch>",
    )
    path.write_text(text)
    assert any(
        "missing personal-fork acceptance URL" in item for item in check(tmp_path)
    )
