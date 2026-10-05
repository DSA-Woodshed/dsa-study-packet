"""Run the declared maintainer suite using Bazel's Python interpreter."""

from __future__ import annotations

import sys

import pytest
from hypothesis import HealthCheck, settings
from tools.run_integration import declared_tests, load_lanes, validate_lanes
from tools.validation_snapshot import enter_snapshot

if __name__ == "__main__":
    root = enter_snapshot()
    validate_lanes(load_lanes(root / "tools" / "test_lanes.bzl"), declared_tests(root))
    # Correctness is deterministic; host scheduling is not a test oracle.
    settings.register_profile(
        "bazel",
        database=None,
        derandomize=True,
        max_examples=200,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    settings.load_profile("bazel")
    raise SystemExit(pytest.main(["-p", "pytest_benchmark.plugin", *sys.argv[1:]]))
