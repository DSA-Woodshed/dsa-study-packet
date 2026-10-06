"""Tests for the extended rep-log line convention validator."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import rep_schema  # type: ignore[import-not-found]  # noqa: E402


def test_valid_extended_line_parses_all_fields() -> None:
    rep = rep_schema.parse_rep_line(
        "talk two_pointers/two_sum C1 L2 A1 R2 P2 h1 use a hash map earlier"
    )
    assert rep.mode == "talk"
    assert rep.topic == "two_pointers"
    assert rep.problem == "two_sum"
    assert rep.scores == {"C": 1, "L": 2, "A": 1, "R": 2, "P": 2}
    assert rep.hint_level == 1
    assert rep.fix == "use a hash map earlier"
    assert rep.is_legacy is False


def test_valid_legacy_line_without_mode_or_hint() -> None:
    rep = rep_schema.parse_rep_line(
        "two_pointers/two_sum C1 L2 A1 R2 P2 use a hash map earlier"
    )
    assert rep.mode is None
    assert rep.hint_level is None
    assert rep.is_legacy is True


def test_legacy_line_with_mode_but_no_hint() -> None:
    rep = rep_schema.parse_rep_line(
        "mock two_pointers/two_sum C1 L2 A1 R2 P2 use a hash map earlier"
    )
    assert rep.mode == "mock"
    assert rep.hint_level is None
    assert rep.is_legacy is True


def test_legacy_line_with_hint_but_no_mode() -> None:
    rep = rep_schema.parse_rep_line(
        "two_pointers/two_sum C1 L2 A1 R2 P2 h3 use a hash map earlier"
    )
    assert rep.mode is None
    assert rep.hint_level == 3
    assert rep.is_legacy is True


@pytest.mark.parametrize(
    "mode", ["comment", "comments", "reacto", "clarp", "umpire", "talk", "cold", "mock"]
)
def test_compact_line_accepts_one_free_text_fix_without_inventing_scores(
    mode: str,
) -> None:
    rep = rep_schema.parse_rep_line(
        f"{mode} arrays/two_sum fix: C1 is a note, not a score token"
    )
    assert rep.mode == mode
    assert rep.scores == {}
    assert rep.fix == "fix: C1 is a note, not a score token"
    assert rep.is_compact is True
    assert rep.is_legacy is False


def test_compact_line_requires_an_explicit_mode() -> None:
    with pytest.raises(rep_schema.RepLineError, match="explicit practice mode"):
        rep_schema.parse_rep_line("arrays/two_sum fix: trace the edge")


def test_score_out_of_range_is_rejected() -> None:
    with pytest.raises(rep_schema.RepLineError):
        rep_schema.parse_rep_line(
            "talk two_pointers/two_sum C3 L2 A1 R2 P2 h1 use a hash map earlier"
        )


def test_hint_out_of_range_is_rejected() -> None:
    with pytest.raises(rep_schema.RepLineError):
        rep_schema.parse_rep_line(
            "talk two_pointers/two_sum C1 L2 A1 R2 P2 h9 use a hash map earlier"
        )


def test_missing_problem_slug_is_rejected() -> None:
    with pytest.raises(rep_schema.RepLineError):
        rep_schema.parse_rep_line("talk two_pointers C1 L2 A1 R2 P2 h1 fix it")


def test_missing_fix_text_is_rejected() -> None:
    with pytest.raises(rep_schema.RepLineError):
        rep_schema.parse_rep_line("talk two_pointers/two_sum C1 L2 A1 R2 P2 h1")


def test_strict_mode_returns_nonzero_on_invalid_line() -> None:
    assert rep_schema._run(["--strict", "not a valid line"]) == 1


def test_default_mode_returns_zero_on_invalid_line() -> None:
    assert rep_schema._run(["not a valid line"]) == 0


def test_default_mode_returns_zero_on_valid_line() -> None:
    assert (
        rep_schema._run(
            ["talk two_pointers/two_sum C1 L2 A1 R2 P2 h1 use a hash map earlier"]
        )
        == 0
    )


def test_missing_reps_log_is_silently_skipped(tmp_path: Path) -> None:
    missing = tmp_path / "reps.md"
    assert rep_schema._run([], reps_log=missing) == 0


def test_reps_log_strips_date_prefix_before_validating(tmp_path: Path) -> None:
    log = tmp_path / "reps.md"
    log.write_text(
        "- 2026-07-06 talk two_pointers/two_sum C1 L2 A1 R2 P2 h1 "
        "use a hash map earlier\n"
    )
    assert rep_schema._run([], reps_log=log) == 0
    assert rep_schema._run(["--strict"], reps_log=log) == 0


def test_reps_log_strict_flags_invalid_entries(tmp_path: Path) -> None:
    log = tmp_path / "reps.md"
    log.write_text("- 2026-07-06 not a valid rep line\n")
    assert rep_schema._run([], reps_log=log) == 0
    assert rep_schema._run(["--strict"], reps_log=log) == 1
