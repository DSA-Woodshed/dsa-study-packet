"""Tests for the dependency-light practice toolchain preflight."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import doctor  # type: ignore[import-not-found]


def test_git_is_a_required_core_tool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CODESPACES", raising=False)
    monkeypatch.setattr(
        doctor.shutil,
        "which",
        lambda name: f"/tools/{name}" if name in {"uv", "just"} else None,
    )
    monkeypatch.setattr(doctor, "pytest_interpreter", lambda: None)

    assert doctor.main() == 1

    captured = capsys.readouterr()
    assert "git        --   loads immutable practice source" in captured.out
    assert "venv: missing; run 'uv sync --extra dev' first" in captured.out
    assert captured.err == "MISSING core tools: git\n"


def test_codespaces_readiness_does_not_require_an_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CODESPACES", "true")
    monkeypatch.setattr(
        doctor.shutil,
        "which",
        lambda name: f"/tools/{name}" if name in {"uv", "just", "git"} else None,
    )
    monkeypatch.setattr(
        doctor,
        "pytest_interpreter",
        lambda: Path(".venv/bin/python"),
    )

    assert doctor.main() == 0

    captured = capsys.readouterr()
    assert "codespace  ok   Codespaces environment detected" in captured.out
    assert (
        "Feedback: optional; choose tools on your personal contribution fork"
        in captured.out
    )
    assert "copilot" not in captured.out
    assert "pytest: ok; import succeeds with .venv/bin/python" in captured.out
    assert (
        "Start with 'just session' or 'just practice-start comments'." in captured.out
    )
    assert captured.err == ""
