"""Guard provider-independent practice commands and honest editor test routing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BRAND = "The DSA Woodshed"

# Public command and editor contracts are independent of optional providers.
SURFACES: dict[str, tuple[str, ...]] = {
    "agent-map.md": (
        "just practice-open",
        "just practice-study topic problem",
        "just practice-start-tests topic problem",
        "IMPLEMENT",
        "TESTS_FIRST",
    ),
    "README.md": (
        BRAND,
        "just practice-start",
        "just practice-start-tests",
        "just practice-study",
        "just practice-next",
        "just practice-finish",
    ),
    "docs/challenges/index.md": (
        "just practice-study topic problem",
        "IMPLEMENT",
        "TESTS_FIRST",
    ),
    "docs/guide/source-of-truth.md": (
        "just practice-open",
        "just practice-study",
        "just practice-start-tests",
        "just practice-next",
    ),
    "WELCOME.md": ("just practice-start", "just practice-next", "just practice-finish"),
    ".vscode/settings.json": ("python.testing.pytestEnabled",),
    ".vscode/tasks.json": (
        "practice-start",
        "practice-next",
        "practice-test",
        "practice-watch",
        "practice-repl",
        "practice-open",
        "practice-finish",
    ),
}

FORBIDDEN: dict[str, tuple[str, ...]] = {
    ".devcontainer/devcontainer.json": (
        "ANTHROPIC_API_KEY",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "OPENAI_API_KEY",
    ),
    ".vscode/tasks.json": (
        '"runOn": "folderOpen"',
        ".devcontainer/launch-agent.sh",
        "exec bash",
    ),
}

REMEDY = "Keep ordinary practice commands and the current-rep editor test task in agreement; see scripts/check_onboarding.py"


def check(root: Path) -> list[str]:
    """Return one actionable line per missing or forbidden contract string."""
    failures: list[str] = []
    files = set(SURFACES) | set(FORBIDDEN)
    for rel in sorted(files):
        path = root / rel
        if not path.exists():
            failures.append(f"{rel}: missing file")
            continue
        text = path.read_text()
        failures.extend(
            f'{rel}: missing "{needle}"'
            for needle in SURFACES.get(rel, ())
            if needle not in text
        )
        failures.extend(
            f'{rel}: contains forbidden "{needle}"'
            for needle in FORBIDDEN.get(rel, ())
            if needle in text
        )
    settings_path = root / ".vscode/settings.json"
    tasks_path = root / ".vscode/tasks.json"
    devcontainer_path = root / ".devcontainer/devcontainer.json"
    if devcontainer_path.is_file():
        try:
            devcontainer = json.loads(devcontainer_path.read_text())
            raw_extensions = devcontainer["customizations"]["vscode"]["extensions"]
        except json.JSONDecodeError, KeyError, TypeError:
            failures.append(
                ".devcontainer/devcontainer.json: invalid VS Code customization"
            )
        else:
            if not isinstance(raw_extensions, list) or not all(
                isinstance(extension, str) for extension in raw_extensions
            ):
                failures.append(
                    ".devcontainer/devcontainer.json: "
                    "VS Code extensions must be a list of strings"
                )
    if settings_path.is_file():
        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            settings = None
            failures.append(".vscode/settings.json: invalid JSON")
        if (
            settings is not None
            and settings.get("python.testing.pytestEnabled") is not False
        ):
            failures.append(
                ".vscode/settings.json: native pytest must stay disabled; "
                "it cannot load the current practice workspace honestly"
            )
    if tasks_path.is_file():
        try:
            task_document = json.loads(tasks_path.read_text())
        except json.JSONDecodeError:
            task_document = None
            failures.append(".vscode/tasks.json: invalid JSON")
        tasks = task_document.get("tasks", []) if task_document is not None else []
        practice_test = next(
            (
                task
                for task in tasks
                if task.get("label") == "practice: test current rep"
            ),
            None,
        )
        if task_document is not None and (
            practice_test is None
            or practice_test.get("group")
            != {
                "kind": "test",
                "isDefault": True,
            }
        ):
            failures.append(
                ".vscode/tasks.json: current-rep test must be the default test task"
            )
        for task in tasks:
            if task.get("label") != "practice: test current rep" and task.get(
                "group"
            ) in ("test", {"kind": "test", "isDefault": True}):
                failures.append(
                    f".vscode/tasks.json: {task.get('label', 'unnamed task')} "
                    "must not compete with the current-rep test task"
                )
    return failures


def main() -> int:
    failures = check(ROOT)
    if failures:
        print("Codespaces onboarding drift:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        print(f"  {REMEDY}", file=sys.stderr)
        return 1
    print(f"Onboarding guard passed; {len(SURFACES)} native surfaces agree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
