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
    # The module's runfiles tree contains declared inputs at their root-relative
    # locations. Exclude the runner's generated interpreter/bootstrap only.
    generated = shutil.ignore_patterns("*.venv", "*_stage2_bootstrap.py")
    for entry in runfiles_root.iterdir():
        destination = snapshot / entry.name
        if entry.is_dir():
            shutil.copytree(entry, destination, ignore=generated)
        elif entry.is_file():
            shutil.copyfile(entry, destination)
    os.chdir(snapshot)
    sys.path.insert(0, str(snapshot / "src"))
    return snapshot
