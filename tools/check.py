"""Run locked quality tools over declared files without the host venv."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tools.validation_snapshot import enter_snapshot


def main() -> None:
    tool = sys.argv[1]
    executable = Path(sys.argv[2]).absolute() if tool == "ruff" else None
    enter_snapshot()
    if tool == "ruff":
        raise SystemExit(
            subprocess.run(
                [
                    str(executable),
                    "check",
                    "--no-cache",
                    "src",
                    "tests",
                    "scripts",
                    "tools",
                    "build_support",
                ],
                check=False,
            ).returncode
        )
    from mypy import api

    output, errors, status = api.run(
        [
            "--no-incremental",
            "--cache-dir=/dev/null",
            "--python-executable",
            sys.executable,
        ]
    )
    print(output, end="")
    print(errors, end="", file=sys.stderr)
    raise SystemExit(status)


if __name__ == "__main__":
    main()
