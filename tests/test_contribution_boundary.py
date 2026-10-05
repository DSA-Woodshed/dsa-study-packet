"""Verify that product checks distinguish tracked tooling from local overlays."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_contribution_boundary import check  # type: ignore[import-not-found]


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def track(root: Path, relative: str, text: str = "local configuration\n") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    subprocess.run(["git", "add", "-f", "--", relative], cwd=root, check=True)


@pytest.mark.parametrize(
    "relative",
    [
        "AGENTS.md",
        "nested/AGENTS.md",
        ".claude/settings.json",
        ".agents/skills/example/SKILL.md",
        ".github/prompts/example.prompt.md",
        "docs/agent-notes/receipt.md",
    ],
)
def test_tracked_personal_tooling_is_rejected(checkout: Path, relative: str) -> None:
    track(checkout, relative)
    assert len(check(checkout)) == 1
    assert check(checkout)[0].startswith(f"{relative}:")


def test_untracked_personal_overlay_is_allowed(checkout: Path) -> None:
    (checkout / "AGENTS.md").write_text("personal overlay\n")
    track(checkout, "README.md", "ordinary product guide\n")
    assert check(checkout) == []


def test_shared_contribution_hooks_are_product_configuration(checkout: Path) -> None:
    track(checkout, ".githooks/pre-push", "#!/bin/sh\nexit 0\n")
    assert check(checkout) == []


def test_provider_editor_defaults_are_rejected(checkout: Path) -> None:
    track(checkout, ".vscode/settings.json", '{"chat.agent.sandbox.enabled": "off"}')
    assert check(checkout) == [
        ".vscode/settings.json: chat.agent.sandbox.enabled belongs in a local overlay"
    ]
