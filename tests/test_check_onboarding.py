"""Tests for the native Codespaces onboarding drift guard."""

import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_onboarding import (  # type: ignore[import-not-found]
    FORBIDDEN,
    SURFACES,
    check,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _mirror_surfaces(dst: Path) -> None:
    """Copy every guarded surface from the real repo into a temporary tree."""
    for rel in set(SURFACES) | set(FORBIDDEN):
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / rel, out)


def test_real_repo_surfaces_agree() -> None:
    assert check(REPO_ROOT) == []


def test_removed_practice_command_is_caught(tmp_path: Path) -> None:
    _mirror_surfaces(tmp_path)
    victim = tmp_path / "README.md"
    command = "just practice-next"
    victim.write_text(victim.read_text().replace(command, ""))

    failures = check(tmp_path)

    assert f'README.md: missing "{command}"' in failures
    assert all(failure.startswith("README.md:") for failure in failures)


@pytest.mark.parametrize(
    ("relative", "needle"),
    [
        ("agent-map.md", "just practice-study topic problem"),
        ("docs/challenges/index.md", "TESTS_FIRST"),
        ("docs/guide/source-of-truth.md", "just practice-open"),
    ],
)
def test_public_study_surface_drift_is_caught(
    tmp_path: Path, relative: str, needle: str
) -> None:
    _mirror_surfaces(tmp_path)
    victim = tmp_path / relative
    victim.write_text(victim.read_text().replace(needle, ""))

    failures = check(tmp_path)

    assert f'{relative}: missing "{needle}"' in failures
    assert all(failure.startswith(f"{relative}:") for failure in failures)


def test_non_list_vscode_extensions_are_caught(tmp_path: Path) -> None:
    _mirror_surfaces(tmp_path)
    victim = tmp_path / ".devcontainer/devcontainer.json"
    config = json.loads(victim.read_text())
    config["customizations"]["vscode"]["extensions"] = {"GitHub.copilot-chat": True}
    victim.write_text(json.dumps(config))

    assert (
        ".devcontainer/devcontainer.json: VS Code extensions must be a list of strings"
    ) in check(tmp_path)


def test_non_string_vscode_extension_is_caught(tmp_path: Path) -> None:
    _mirror_surfaces(tmp_path)
    victim = tmp_path / ".devcontainer/devcontainer.json"
    config = json.loads(victim.read_text())
    config["customizations"]["vscode"]["extensions"].append(42)
    victim.write_text(json.dumps(config))

    assert (
        ".devcontainer/devcontainer.json: VS Code extensions must be a list of strings"
    ) in check(tmp_path)


def test_folder_open_launcher_is_caught(tmp_path: Path) -> None:
    _mirror_surfaces(tmp_path)
    victim = tmp_path / ".vscode/tasks.json"
    victim.write_text(victim.read_text() + '\n"runOn": "folderOpen"\n')

    assert any(
        failure.startswith(".vscode/tasks.json: contains forbidden")
        and "folderOpen" in failure
        for failure in check(tmp_path)
    )


def test_missing_surface_file_is_caught(tmp_path: Path) -> None:
    _mirror_surfaces(tmp_path)
    (tmp_path / ".vscode/tasks.json").unlink()

    assert ".vscode/tasks.json: missing file" in check(tmp_path)


def test_native_pytest_false_green_is_caught(tmp_path: Path) -> None:
    _mirror_surfaces(tmp_path)
    victim = tmp_path / ".vscode/settings.json"
    victim.write_text(
        victim.read_text().replace(
            '"python.testing.pytestEnabled": false',
            '"python.testing.pytestEnabled": true',
        )
    )

    assert any(
        "native pytest must stay disabled" in failure for failure in check(tmp_path)
    )


def test_packet_suite_cannot_replace_default_rep_test(tmp_path: Path) -> None:
    _mirror_surfaces(tmp_path)
    victim = tmp_path / ".vscode/tasks.json"
    text = victim.read_text()
    text = text.replace(
        '"label": "maintainer: test packet",\n      "type": "shell",',
        '"label": "maintainer: test packet",\n      "group": "test",\n      "type": "shell",',
    )
    victim.write_text(text)

    assert any("must not compete" in failure for failure in check(tmp_path))
