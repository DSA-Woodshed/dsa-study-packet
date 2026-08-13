"""Tests for the exact-SHA, non-resuming Codespaces acceptance helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import codespaces_acceptance as acceptance  # type: ignore[import-not-found]

SHA = "a" * 40
REPOSITORY = "Jesssullivan/dsa-study-packet"


def _root(tmp_path: Path) -> Path:
    (tmp_path / "tinyland.repo.json").write_text(
        json.dumps({"repo": {"github": REPOSITORY}})
    )
    return tmp_path


def test_plan_resolves_remote_branch_and_emits_non_resuming_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    seen: list[list[str]] = []

    def capture(command: list[str], cwd: Path) -> str:
        seen.append(command)
        assert cwd == root
        return SHA

    monkeypatch.setattr(acceptance, "_capture", capture)

    lines = acceptance.plan(root, "codespaces-acceptance-transfer")

    assert seen == [
        [
            "gh",
            "api",
            "repos/Jesssullivan/dsa-study-packet/branches/"
            "codespaces-acceptance-transfer",
            "--jq",
            ".commit.sha",
        ]
    ]
    assert f"EXPECTED_SHA: {SHA}" in lines
    create = next(line for line in lines if line.startswith("CREATE_URL:"))
    assert create.endswith("/tree/codespaces-acceptance-transfer")
    assert "quickstart" not in create
    assert "COPILOT_SIGN_IN: NOT_TESTED" in lines
    assert "COPILOT_ENTITLEMENT: NOT_TESTED" in lines


def test_plan_rejects_a_non_disposable_branch(tmp_path: Path) -> None:
    with pytest.raises(acceptance.AcceptanceError, match="BRANCH: INVALID"):
        acceptance.plan(_root(tmp_path), "main")


def test_expected_sha_must_be_lowercase(tmp_path: Path) -> None:
    with pytest.raises(acceptance.AcceptanceError, match="EXPECTED_SHA: INVALID"):
        acceptance.verify(_root(tmp_path), "A" * 40, {})


def test_verify_checks_repo_and_sha_but_not_copilot_ui(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    outputs = {
        ("git", "rev-parse", "HEAD"): SHA,
        ("git", "remote", "get-url", "origin"): (
            "git@github.com:Jesssullivan/dsa-study-packet.git"
        ),
        ("git", "status", "--porcelain=v1", "--untracked-files=normal"): "",
        ("code", "--version"): "1.131.0\ncommit\narm64",
        ("code", "--list-extensions", "--show-versions"): (
            "github.copilot-chat@0.35.0\nms-python.python@2026.10.0"
        ),
    }
    monkeypatch.setattr(
        acceptance,
        "_capture",
        lambda command, _cwd: outputs[tuple(command)],
    )

    lines = acceptance.verify(
        root,
        SHA,
        {"CODESPACES": "true", "CODESPACE_NAME": "exact-head-proof"},
    )

    assert "REPOSITORY_CHECKOUT: PASS" in lines
    assert "CHECKOUT_SHA: " + SHA in lines
    assert "WORKTREE: CLEAN (ignored private state excluded)" in lines
    assert "REPOSITORY_WRITE_AUTH: NOT_TESTED" in lines
    assert "COPILOT_SIGN_IN: MANUAL_UI_REQUIRED" in lines
    assert "COPILOT_ENTITLEMENT: MANUAL_UI_REQUIRED" in lines
    assert "EXTENSION: github.copilot-chat@0.35.0" in lines


def test_verify_rejects_a_stale_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    monkeypatch.setattr(acceptance, "_capture", lambda _command, _cwd: "b" * 40)

    with pytest.raises(acceptance.AcceptanceError, match="delete this stale Codespace"):
        acceptance.verify(
            root,
            SHA,
            {"CODESPACES": "true", "CODESPACE_NAME": "stale"},
        )


def test_verify_rejects_tracked_lifecycle_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    outputs = {
        ("git", "rev-parse", "HEAD"): SHA,
        ("git", "status", "--porcelain=v1", "--untracked-files=normal"): (
            " M .devcontainer/devcontainer.json"
        ),
    }
    monkeypatch.setattr(
        acceptance,
        "_capture",
        lambda command, _cwd: outputs[tuple(command)],
    )

    with pytest.raises(acceptance.AcceptanceError, match="WORKTREE: DIRTY"):
        acceptance.verify(
            root,
            SHA,
            {"CODESPACES": "true", "CODESPACE_NAME": "mutated"},
        )


def test_verify_rejects_a_non_codespaces_environment(tmp_path: Path) -> None:
    with pytest.raises(acceptance.AcceptanceError, match="CODESPACES: NOT_DETECTED"):
        acceptance.verify(_root(tmp_path), SHA, {})


def test_verify_rejects_the_wrong_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    outputs = {
        ("git", "rev-parse", "HEAD"): SHA,
        ("git", "status", "--porcelain=v1", "--untracked-files=normal"): "",
        ("git", "remote", "get-url", "origin"): (
            "git@example.invalid:Elsewhere/dsa-study-packet.git"
        ),
    }
    monkeypatch.setattr(
        acceptance,
        "_capture",
        lambda command, _cwd: outputs[tuple(command)],
    )

    with pytest.raises(acceptance.AcceptanceError, match="EXPECTED_REPOSITORY"):
        acceptance.verify(
            root,
            SHA,
            {"CODESPACES": "true", "CODESPACE_NAME": "wrong-repo"},
        )


def test_verify_rejects_unexpected_untracked_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    outputs = {
        ("git", "rev-parse", "HEAD"): SHA,
        ("git", "status", "--porcelain=v1", "--untracked-files=normal"): (
            "?? conftest.py"
        ),
    }
    monkeypatch.setattr(
        acceptance,
        "_capture",
        lambda command, _cwd: outputs[tuple(command)],
    )

    with pytest.raises(acceptance.AcceptanceError, match="WORKTREE: DIRTY"):
        acceptance.verify(
            root,
            SHA,
            {"CODESPACES": "true", "CODESPACE_NAME": "untracked"},
        )
