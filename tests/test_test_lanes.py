"""The shared test partition rejects omissions, duplication, and executable input."""

from __future__ import annotations

from pathlib import Path

import pytest
from tools.run_integration import load_lanes, validate_lanes


def lanes() -> dict[str, list[str]]:
    return {
        "UNIT_TESTS": ["tests/test_unit.py"],
        "INTEGRATION_TESTS": ["tests/test_runtime.py"],
        "BOOKLET_SMOKE_TESTS": ["tests/booklet_pdf_smoke.sh"],
    }


def test_complete_partition_has_one_owner_per_entrypoint() -> None:
    partition = lanes()
    validate_lanes(partition, {path for paths in partition.values() for path in paths})


@pytest.mark.parametrize("duplicate_lane", ["UNIT_TESTS", "INTEGRATION_TESTS"])
def test_duplicates_within_and_across_lanes_are_rejected(duplicate_lane: str) -> None:
    partition = lanes()
    inventory = {path for paths in partition.values() for path in paths}
    partition[duplicate_lane].append("tests/test_unit.py")
    with pytest.raises(ValueError, match="overlapping or duplicate"):
        validate_lanes(partition, inventory)


def test_new_tracked_test_requires_a_lane() -> None:
    partition = lanes()
    inventory = {path for paths in partition.values() for path in paths}
    with pytest.raises(ValueError, match=r"unassigned tests: tests/test_new\.py"):
        validate_lanes(partition, inventory | {"tests/test_new.py"})


def test_deleted_test_cannot_remain_in_a_lane() -> None:
    partition = lanes()
    inventory = {"tests/test_unit.py", "tests/booklet_pdf_smoke.sh"}
    with pytest.raises(
        ValueError, match=r"untracked or missing tests: tests/test_runtime\.py"
    ):
        validate_lanes(partition, inventory)


@pytest.mark.parametrize(
    "statement",
    [
        'UNIT_TESTS = __import__("os").system("false")',
        "UNIT_TESTS = [path for path in []]",
        "import os",
        'UNIT_TESTS = ["../tests/test_private.py"]',
        'UNIT_TESTS = ["tests/booklet_pdf_smoke.sh"]',
        "UNKNOWN_TESTS = []",
    ],
)
def test_parser_rejects_executable_or_invalid_manifest_content(
    tmp_path: Path, statement: str
) -> None:
    manifest = tmp_path / "test_lanes.bzl"
    manifest.write_text(
        statement + "\nINTEGRATION_TESTS = []\nBOOKLET_SMOKE_TESTS = []\n"
    )
    with pytest.raises(ValueError):
        load_lanes(manifest)


def test_parser_reads_the_public_manifest() -> None:
    root = Path(__file__).resolve().parents[1]
    partition = load_lanes(root / "tools" / "test_lanes.bzl")
    assert "tests/test_session.py" in partition["INTEGRATION_TESTS"]
    assert "tests/test_environment.py" in partition["INTEGRATION_TESTS"]
    assert partition["BOOKLET_SMOKE_TESTS"] == ["tests/booklet_pdf_smoke.sh"]
