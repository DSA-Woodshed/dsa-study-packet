"""Tests for the product and onboarding clarity guard."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_clarity import (  # type: ignore[import-not-found]
    DESCRIPTION_MAX_CHARS,
    DESCRIPTION_SURFACES,
    EM_DASH,
    SURFACE_BUDGETS,
    UNRESOLVED_STRINGS,
    check,
    main,
)


def make_valid_surfaces(root: Path) -> None:
    """Create the complete guarded surface set with compact valid content."""
    for relative in SURFACE_BUDGETS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Compact instructions.\n")

    for relative in DESCRIPTION_SURFACES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n"
            "title: Practice surface\n"
            "description: Calm editor practice with comments, code, and tests.\n"
            "---\n\n"
            "Compact instructions.\n"
        )


def test_valid_surfaces_pass(tmp_path: Path) -> None:
    make_valid_surfaces(tmp_path)

    assert check(tmp_path) == []


def test_missing_surface_is_actionable(tmp_path: Path) -> None:
    make_valid_surfaces(tmp_path)
    missing = next(iter(SURFACE_BUDGETS))
    (tmp_path / missing).unlink()

    assert check(tmp_path) == [f"{missing}: missing clarity-guarded surface"]


def test_word_budget_reports_required_cut(tmp_path: Path) -> None:
    make_valid_surfaces(tmp_path)
    relative = "TRACK-CONTRACT.md"
    budget = SURFACE_BUDGETS[relative]
    (tmp_path / relative).write_text("word " * (budget + 3))

    assert check(tmp_path) == [
        f"{relative}: {budget + 3} words exceeds the {budget}-word budget; "
        "cut at least 3 word(s)"
    ]


def test_actual_em_dash_is_rejected(tmp_path: Path) -> None:
    make_valid_surfaces(tmp_path)
    relative = "WELCOME.md"
    (tmp_path / relative).write_text(f"Start here {EM_DASH} then practice.\n")

    failures = check(tmp_path)

    assert len(failures) == 1
    assert failures[0].startswith(f"{relative}: contains 1 U+2014 em dash")


@pytest.mark.parametrize("unresolved", tuple(UNRESOLVED_STRINGS))
def test_unresolved_instruction_is_rejected(tmp_path: Path, unresolved: str) -> None:
    make_valid_surfaces(tmp_path)
    relative = "WELCOME.md"
    (tmp_path / relative).write_text(f"Run {unresolved} now.\n")

    failures = check(tmp_path)

    assert len(failures) == 1
    assert f'contains unresolved instruction "{unresolved}"' in failures[0]


def test_public_surface_requires_frontmatter_description(tmp_path: Path) -> None:
    make_valid_surfaces(tmp_path)
    relative = DESCRIPTION_SURFACES[0]
    (tmp_path / relative).write_text(
        "---\ntitle: Practice surface\n---\n\nCompact instructions.\n"
    )

    assert check(tmp_path) == [
        f"{relative}: add a concise frontmatter description for cards and metadata"
    ]


def test_public_surface_description_has_length_limit(tmp_path: Path) -> None:
    make_valid_surfaces(tmp_path)
    relative = DESCRIPTION_SURFACES[0]
    description = "x" * (DESCRIPTION_MAX_CHARS + 1)
    (tmp_path / relative).write_text(
        f"---\ntitle: Practice surface\ndescription: {description}\n"
        "---\n\nCompact instructions.\n"
    )

    assert check(tmp_path) == [
        f"{relative}: frontmatter description is {len(description)} characters; "
        f"keep it at or below {DESCRIPTION_MAX_CHARS}"
    ]


def test_main_accepts_optional_root_and_reports_failures(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    make_valid_surfaces(tmp_path)
    (tmp_path / "README.md").write_text(f"Avoid {EM_DASH} here.\n")

    assert main([str(tmp_path)]) == 1
    output = capsys.readouterr().out
    assert "Clarity guard failed:" in output
    assert "README.md: contains 1 U+2014 em dash" in output
