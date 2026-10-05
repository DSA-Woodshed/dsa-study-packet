"""Security checks for user-controlled arguments in practice recipes."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _captured_uv_args(tmp_path: Path, *recipe_args: str) -> list[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_uv = bin_dir / "uv"
    fake_uv.write_text(
        "#!/usr/bin/env python3\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\n"
    )
    fake_uv.chmod(0o755)
    env = os.environ | {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    proc = subprocess.run(
        ["just", *recipe_args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return cast("list[str]", json.loads(proc.stdout.splitlines()[-1]))


@pytest.mark.parametrize(
    ("recipe_args", "expected_tail"),
    [
        (
            ("catalog", "anagram, 2 sum and prime"),
            ["scripts/catalog.py", "anagram, 2 sum and prime"],
        ),
        (("practice-start", "comments"), ["start", "comments"]),
        (
            ("practice-start", "comments", "arrays; echo bad", "two_sum"),
            ["start", "comments", "arrays; echo bad", "two_sum"],
        ),
        (("practice-present", "arrays", "two_sum"), ["present", "arrays", "two_sum"]),
        (("practice-reference",), ["reference"]),
        (
            ("practice-reference", "arrays", "two_sum; echo bad"),
            ["reference", "arrays", "two_sum; echo bad"],
        ),
        (
            ("study-spaced", "3; echo bad"),
            ["scripts/study_schedule.py", "3; echo bad"],
        ),
        (
            ("practice-day", "12; echo bad"),
            ["scripts/practice_day.py", "12; echo bad"],
        ),
        (
            ("challenge-done", "arrays; echo bad", "two_sum"),
            ["complete", "arrays; echo bad", "two_sum"],
        ),
        (
            ("rep", "talk arrays/two_sum C2 L2 A2 R2 P2 h0 fix; echo bad"),
            ["log", "talk arrays/two_sum C2 L2 A2 R2 P2 h0 fix; echo bad"],
        ),
        (
            (
                "rep-finish",
                "arrays",
                "two_sum",
                "talk arrays/two_sum C2 L2 A2 R2 P2 h0 fix; echo bad",
            ),
            [
                "finish-non-editor",
                "arrays",
                "two_sum",
                "talk arrays/two_sum C2 L2 A2 R2 P2 h0 fix; echo bad",
            ],
        ),
    ],
)
def test_practice_arguments_reach_python_as_single_values(
    tmp_path: Path, recipe_args: tuple[str, ...], expected_tail: list[str]
) -> None:
    captured = _captured_uv_args(tmp_path, *recipe_args)

    assert captured[-len(expected_tail) :] == expected_tail


def test_authority_surfaces_use_one_non_editor_closeout() -> None:
    authority_paths = (
        "TRACK-CONTRACT.md",
        "docs/guide/getting-started.md",
        "docs/guide/interview-practice-evidence.md",
        "docs/guide/source-of-truth.md",
        "reference-sheets/10-whiteboard-performance-protocol.md",
    )
    combined = "\n".join((ROOT / path).read_text() for path in authority_paths)

    assert "just rep-finish" in combined
    assert 'just rep "' not in combined
    assert "just challenge-done" not in combined


def test_editor_start_cannot_execute_shell_substitution(tmp_path: Path) -> None:
    sentinel = tmp_path / "executed"
    malicious_topic = f"$(touch {sentinel})"

    captured = _captured_uv_args(
        tmp_path, "practice-start", "comments", malicious_topic, "two_sum"
    )

    assert captured[-2:] == [malicious_topic, "two_sum"]
    assert not sentinel.exists()


def test_one_natural_name_returns_catalog_guidance_without_running_python(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    invoked = tmp_path / "uv-was-invoked"
    fake_uv = bin_dir / "uv"
    fake_uv.write_text(f"#!/bin/sh\ntouch {invoked}\n")
    fake_uv.chmod(0o755)
    env = os.environ | {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}

    proc = subprocess.run(
        ["just", "practice-start", "comments", "prime"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 2
    assert "provide both topic and problem" in proc.stdout
    assert 'NEXT: just catalog "prime"' in proc.stdout
    assert not invoked.exists()


def test_legacy_mutation_and_save_polling_recipes_are_absent() -> None:
    proc = subprocess.run(
        ["just", "--summary"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    recipes = proc.stdout.split()
    assert "challenge" not in recipes
    assert "solution" not in recipes
    assert "challenge-reset" not in recipes
    assert "wait" not in recipes
    assert "challenge-done" in recipes
    assert not (ROOT / "scripts/wait_for_save.py").exists()
