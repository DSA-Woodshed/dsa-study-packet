"""Regression tests for generated editor-practice documentation."""

from __future__ import annotations

import runpy
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from types import FunctionType, ModuleType
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_generator(name: str) -> tuple[dict[str, str], dict[str, object]]:
    """Execute one MkDocs generator against an in-memory output module."""
    generated: dict[str, str] = {}

    @contextmanager
    def fake_open(path: str, mode: str) -> Iterator[StringIO]:
        assert mode == "w"
        output = StringIO()
        yield output
        generated[str(path)] = output.getvalue()

    fake_module = ModuleType("mkdocs_gen_files")
    fake_module.__dict__["open"] = fake_open
    previous = sys.modules.get("mkdocs_gen_files")
    sys.modules["mkdocs_gen_files"] = fake_module
    try:
        namespace = runpy.run_path(str(ROOT / "scripts" / f"{name}.py"))
    finally:
        if previous is None:
            del sys.modules["mkdocs_gen_files"]
        else:
            sys.modules["mkdocs_gen_files"] = previous
    return generated, cast("dict[str, object]", namespace)


def test_algorithm_page_points_to_the_isolated_editor_loop() -> None:
    _, namespace = load_generator("gen_algo_pages")
    render = cast("Callable[[str, str, str], str]", namespace["_gen_problem_page"])
    source = '''"""Two Sum.

Problem:
    Find a pair.

Complexity:
    Time: O(n)
    Space: O(n)
"""

def two_sum(values: list[int], target: int) -> tuple[int, int]:
    return (0, 1)
'''

    page = render("arrays", "two_sum", source)

    assert '=== "Try it"' in page
    assert "`just practice-start comments arrays two_sum`" in page
    assert "opens an isolated starter file and focused test tab" in page
    assert "just challenge" not in page
    assert "just study" not in page


def test_summary_preserves_the_reduced_public_information_architecture() -> None:
    _, namespace = load_generator("gen_algo_pages")
    render = cast(
        "Callable[[dict[str, list[tuple[str, dict[str, str]]]]], str]",
        namespace["_gen_summary"],
    )

    summary = render({"arrays": [("two_sum", {})]})
    top_level = [line for line in summary.splitlines() if line.startswith("* ")]

    assert top_level == [
        "* [Home](index.md)",
        "* Start Here",
        "* Practice",
        "* Library",
        "* Method",
        "* Project",
    ]
    assert "    * [Practice Problems](challenges/index.md)" in summary
    assert summary.count("[Practice Problems](challenges/index.md)") == 1
    assert "practice/index.md" not in summary
    assert "    * [Source of Truth](guide/source-of-truth.md)" in summary
    assert "            * [Two Sum](algorithms/arrays/two_sum.md)" in summary


def test_progress_reads_finish_output_and_renders_safe_next_steps(
    tmp_path: Path,
) -> None:
    generated, namespace = load_generator("gen_progress_page")
    progress_file = tmp_path / "progress.md"
    progress_file.write_text(
        "- [x] arrays/two_sum 2026-07-15\n- [x] ../private/notes 2026-07-15\n"
    )
    parse = cast("FunctionType", namespace["_parse_progress"])
    render = cast("FunctionType", namespace["main"])
    parse.__globals__["PROGRESS_FILE"] = progress_file
    parse.__globals__["CORE_42"] = {"arrays": ["two_sum", "three_sum"]}

    parsed = cast("dict[str, str]", parse())
    assert parsed == {"arrays/two_sum": "2026-07-15"}

    generated.clear()
    render()
    page = generated["challenges/progress.md"]

    assert "title: Practice Progress" in page
    assert "**1 / 2** core problems completed." in page
    assert "- [x] Two Sum (2026-07-15)" in page
    assert "`just practice-start comments arrays three_sum`: Three Sum" in page
    assert "challenge-reset" not in page
    assert "just challenge " not in page


@pytest.mark.parametrize(
    ("contents", "expected"),
    [
        (None, {}),
        ("", {}),
        (
            "- [ ] arrays/two_sum 2026-10-06\n"
            "- [x] ../private/notes 2026-10-06\n"
            "- [X] arrays/two_sum 2026-10-06\n"
            "  - [x] arrays/two_sum 2026-10-06\n",
            {},
        ),
        (
            "- [x] arrays/two_sum: old\n"
            "- [x] arrays/two_sum \u2014 2026-10-06\n"
            "- [x] trees/invert_tree\n"
            "- [x] arrays/three_sum unparseable date\n"
            "- [x] unknown/not_core 2026-10-06\n",
            {
                "arrays/two_sum": "2026-10-06",
                "trees/invert_tree": "",
                "arrays/three_sum": "unparseable date",
                "unknown/not_core": "2026-10-06",
            },
        ),
    ],
)
def test_progress_consumers_preserve_existing_completion_labels(
    tmp_path: Path, contents: str | None, expected: dict[str, str]
) -> None:
    _, namespace = load_generator("gen_progress_page")
    completed = cast("Callable[[Path], dict[str, str]]", namespace["_completed"])

    progress = tmp_path / "progress.md"
    if contents is not None:
        progress.write_text(contents)
    parse = cast("FunctionType", namespace["_parse_progress"])
    parse.__globals__["PROGRESS_FILE"] = progress

    assert parse() == expected
    assert completed(progress) == expected
