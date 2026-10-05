"""Copy runfiles into a writable test directory without resolving source links."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def enter_snapshot() -> Path:
    """Give tests that resolve __file__ only the declared Bazel input tree."""
    runfiles_root = Path(__file__).absolute().parents[1]
    snapshot = Path(os.environ["TEST_TMPDIR"]) / "packet"
    snapshot.mkdir()
    entries = [
        runfiles_root / name
        for name in (
            "src",
            "scripts",
            "build_support",
            "tests",
            "docs",
            "reference-sheets",
            "pyproject.toml",
            "README.md",
        )
    ]
    for entry in entries:
        destination = snapshot / entry.name
        if entry.is_dir():
            shutil.copytree(entry, destination)
        elif entry.is_file():
            shutil.copyfile(entry, destination)
    (snapshot / "tools").mkdir()
    for name in ("check.py", "pytest_main.py", "validation_snapshot.py"):
        shutil.copyfile(runfiles_root / "tools" / name, snapshot / "tools" / name)
    os.chdir(snapshot)
    sys.path.insert(0, str(snapshot / "src"))
    return snapshot
