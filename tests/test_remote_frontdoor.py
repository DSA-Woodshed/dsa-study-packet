"""Retired profile configuration never authorizes a remote action."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, body: str) -> None:
    path.write_text(f"#!/bin/sh\nset -eu\n{body}\n")
    path.chmod(0o755)


@pytest.mark.parametrize(
    ("recipe", "targets"),
    [
        ("remote-compile", ()),
        ("remote-build", ("//...",)),
        ("remote-test", ("//:booklet_smoke",)),
        ("remote-test", ("//...",)),
        ("remote-check", ()),
    ],
)
@pytest.mark.parametrize("profile", ["absent", "environment", "file"])
def test_remote_frontdoors_refuse_retired_profiles(
    tmp_path: Path,
    recipe: str,
    targets: tuple[str, ...],
    profile: str,
) -> None:
    (tmp_path / ".bazelversion").write_text("9.0.1\n")
    (tmp_path / "justfile").write_text((ROOT / "justfile").read_text())
    fragment = ROOT / "justfile.flywheel"
    if fragment.is_file():
        (tmp_path / fragment.name).write_text(fragment.read_text())
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    trace = tmp_path / "trace"
    fake_bazel = bin_dir / "bazel"
    _write_executable(
        bin_dir / "uv",
        'printf "uv %s\\n" "$*" >> "$TRACE"',
    )
    _write_executable(
        fake_bazel,
        'printf "bazel %s\\n" "$*" >> "$TRACE"',
    )
    for command in ("gloriousflywheel-bazel", "flywheel-doctor", "flywheel-verify"):
        _write_executable(bin_dir / command, 'printf "provider called\\n" >> "$TRACE"')
    if profile == "file":
        (tmp_path / ".env.flywheel.local").write_text(
            'printf "profile loaded\\n" >> "$TRACE"\n'
            "BAZEL_REMOTE_CACHE=unused.invalid\n"
        )
    env = {
        **os.environ,
        "BAZEL_BIN": str(fake_bazel),
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "TRACE": str(trace),
        "BAZEL_REMOTE_CACHE": "unused.invalid" if profile == "environment" else "",
    }

    completed = subprocess.run(
        [
            "just",
            "--justfile",
            str(tmp_path / "justfile"),
            "--working-directory",
            str(tmp_path),
            recipe,
            *targets,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode == 78, completed.stderr
    assert "unavailable" in completed.stderr.lower()
    assert not trace.exists()
