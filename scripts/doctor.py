"""Preflight: report editor-practice toolchain readiness, with hints.

Runs on the system interpreter on purpose (`just doctor` calls python3, not
`uv run`) so it still works when the venv is broken. That is when you need a
doctor. Exits 1 only if a core tool (uv, just, git) is missing; everything
else is informational.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

CORE = (
    ("uv", "installs python + deps; https://astral.sh/uv"),
    ("just", "runs every recipe; https://just.systems"),
    ("git", "loads immutable practice source from the checkout's committed HEAD"),
)
LOOP = (
    ("watchexec", "'just practice-watch'; test/repl loop works without it"),
    ("code", "opens candidate source + test tabs; paths print if absent"),
)
PUBLISHING = (
    ("pandoc", "'just pdf-all' reference-sheet PDFs (optional)"),
    ("tectonic", "'just packet' booklet PDF (optional)"),
    ("bazelisk", "'just remote-*' cache-first builds (optional)"),
)


def pytest_interpreter() -> Path | None:
    """Return a project interpreter only when it can import pytest."""
    candidates = (Path(".venv/bin/python"), Path(".venv/Scripts/python.exe"))
    for interpreter in candidates:
        if not interpreter.is_file():
            continue
        try:
            result = subprocess.run(
                [str(interpreter), "-c", "import pytest"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except OSError:
            continue
        except subprocess.SubprocessError:
            continue
        if result.returncode == 0:
            return interpreter
    return None


def report(title: str, tools: tuple[tuple[str, str], ...]) -> list[str]:
    print(title)
    missing = []
    for name, hint in tools:
        found = shutil.which(name)
        mark = "ok" if found else "--"
        print(f"  {name:<10} {mark:<4} {hint}")
        if not found:
            missing.append(name)
    return missing


def main() -> int:
    print(f"doctor: python {sys.version.split()[0]} at {sys.executable}")
    print()
    core_missing = report("Core", CORE)
    report("Practice loop", LOOP)
    if os.environ.get("CODESPACES"):
        print("  codespace  ok   Codespaces environment detected")
    print("Feedback: optional; choose tools on your personal contribution fork")
    report("Publishing (optional)", PUBLISHING)
    print()
    interpreter = pytest_interpreter()
    if interpreter:
        print(f"pytest: ok; import succeeds with {interpreter}")
    elif not Path(".venv").is_dir():
        print("venv: missing; run 'uv sync --extra dev' first (pytest unavailable)")
    else:
        print("pytest: unavailable in .venv; run 'uv sync --extra dev'")
    if core_missing:
        print(f"MISSING core tools: {', '.join(core_missing)}", file=sys.stderr)
        return 1
    print(
        "Core toolchain ok. Start with 'just session' or 'just practice-start comments'."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
