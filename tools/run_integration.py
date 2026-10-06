"""Validate the public test partition and run only uv's integration lane."""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath

LANE_NAMES = ("UNIT_TESTS", "INTEGRATION_TESTS", "BOOKLET_SMOKE_TESTS")


def is_test_entrypoint(relative: str) -> bool:
    path = PurePosixPath(relative)
    return (
        bool(path.parts)
        and path.parts[0] == "tests"
        and (
            path.suffix == ".sh"
            or (
                path.suffix == ".py"
                and (path.name.startswith("test_") or path.name.endswith("_test.py"))
            )
        )
    )


def load_lanes(path: Path) -> dict[str, list[str]]:
    """Read only literal assignments; never execute a Starlark/Python module."""
    lanes: dict[str, list[str]] = {}
    for node in ast.parse(path.read_text(encoding="utf-8"), filename=str(path)).body:
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue
        if (
            not isinstance(node, ast.Assign)
            or len(node.targets) != 1
            or not isinstance(node.targets[0], ast.Name)
            or node.targets[0].id not in LANE_NAMES
            or node.targets[0].id in lanes
        ):
            raise ValueError(
                "test_lanes.bzl must contain each named lane once as a literal list"
            )
        name = node.targets[0].id
        value = ast.literal_eval(node.value)
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise ValueError(f"{name} must be a literal list of paths")
        for relative in value:
            candidate = PurePosixPath(relative)
            if (
                not is_test_entrypoint(relative)
                or candidate.is_absolute()
                or ".." in candidate.parts
                or relative != candidate.as_posix()
            ):
                raise ValueError(f"{name} has an invalid test path: {relative}")
            expected_suffix = ".sh" if name == "BOOKLET_SMOKE_TESTS" else ".py"
            if candidate.suffix != expected_suffix:
                raise ValueError(f"{name} has the wrong test kind: {relative}")
        lanes[name] = value
    if set(lanes) != set(LANE_NAMES):
        raise ValueError("test_lanes.bzl is missing a named lane")
    return lanes


def validate_lanes(lanes: dict[str, list[str]], inventory: set[str]) -> None:
    """Require every test entrypoint exactly once across all three lanes."""
    counts = Counter(path for paths in lanes.values() for path in paths)
    failures = []
    duplicates = sorted(path for path, count in counts.items() if count != 1)
    if duplicates:
        failures.append("overlapping or duplicate tests: " + ", ".join(duplicates))
    missing = sorted(inventory - counts.keys())
    if missing:
        failures.append("unassigned tests: " + ", ".join(missing))
    stale = sorted(counts.keys() - inventory)
    if stale:
        failures.append("untracked or missing tests: " + ", ".join(stale))
    if failures:
        raise ValueError("; ".join(failures))


def tracked_tests(root: Path) -> set[str]:
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", "tests"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\0")
    return {relative for relative in tracked if is_test_entrypoint(relative)}


def declared_tests(root: Path) -> set[str]:
    """Inventory an isolated Bazel snapshot without relying on host Git."""
    return {
        path.relative_to(root).as_posix()
        for path in (root / "tests").rglob("*")
        if path.is_file() and is_test_entrypoint(path.relative_to(root).as_posix())
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        lanes = load_lanes(root / "tools" / "test_lanes.bzl")
        validate_lanes(lanes, tracked_tests(root))
    except (OSError, SyntaxError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"test lanes: {exc}", file=sys.stderr)
        return 2
    print("TEST_LANES: PASS (every tracked test assigned exactly once)", flush=True)
    if args.check_only:
        return 0
    import pytest

    forwarded = args.pytest_args
    if forwarded[:1] == ["--"]:
        forwarded = forwarded[1:]
    return int(pytest.main([*lanes["INTEGRATION_TESTS"], *forwarded]))


if __name__ == "__main__":
    raise SystemExit(main())
