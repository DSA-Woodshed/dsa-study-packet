"""Keep personal agent configuration out of the tracked product contribution."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PERSONAL_DIRECTORIES = {
    ".agents",
    ".claude",
    ".gemini",
    ".codex",
    ".github/agents",
    ".github/prompts",
    ".github/hooks",
    "docs/agent-notes",
}
PERSONAL_FILES = {"AGENTS.md", "CLAUDE.md", "SKILL.md", ".mcp.json"}


def check(root: Path) -> list[str]:
    """Inspect tracked paths so a contributor's local overlay remains usable."""
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=root, text=True
    ).split("\0")
    failures = []
    for relative in filter(None, tracked):
        path = PurePosixPath(relative)
        if path.name in PERSONAL_FILES or relative == ".github/copilot-instructions.md":
            failures.append(
                f"{relative}: personal agent directive belongs on the fork overlay"
            )
        elif any(
            relative == directory or relative.startswith(f"{directory}/")
            for directory in PERSONAL_DIRECTORIES
        ):
            failures.append(
                f"{relative}: personal agent tooling belongs on the fork overlay"
            )

    settings_path = root / ".vscode/settings.json"
    if ".vscode/settings.json" in tracked and settings_path.is_file():
        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            failures.append(".vscode/settings.json: invalid JSON")
        else:
            for key in settings:
                if key.startswith(("chat.", "github.copilot.")):
                    failures.append(
                        f".vscode/settings.json: {key} belongs in a local overlay"
                    )
    return failures


def main() -> int:
    failures = check(ROOT)
    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print("Contribution boundary passed; tracked product is provider independent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
