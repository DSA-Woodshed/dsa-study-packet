"""Public readiness remains independent from optional runtime seat admission."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "environment", ROOT / "scripts/environment.py"
)
assert SPEC
assert SPEC.loader
environment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(environment)


def test_repeated_setup_preserves_candidate_work_and_private_mode(
    tmp_path: Path,
) -> None:
    state = environment.prepare_state(tmp_path)
    candidate = state / "candidate.py"
    candidate.write_text("# trace before optimizing\n")
    state.chmod(0o755)

    assert environment.prepare_state(tmp_path) == state
    assert candidate.read_text() == "# trace before optimizing\n"
    assert state.stat().st_mode & 0o777 == 0o700
    assert environment.private_state(tmp_path)


def test_setup_refuses_symlink_without_touching_its_target(tmp_path: Path) -> None:
    target = tmp_path / "elsewhere"
    target.mkdir(mode=0o755)
    (tmp_path / ".challenges").symlink_to(target, target_is_directory=True)

    with pytest.raises(ValueError, match="regular directory"):
        environment.prepare_state(tmp_path)
    assert target.stat().st_mode & 0o777 == 0o755
    assert not environment.private_state(tmp_path)


def test_setup_refuses_a_file_in_place_of_practice_state(tmp_path: Path) -> None:
    state = tmp_path / ".challenges"
    state.write_text("keep this data")
    with pytest.raises(ValueError, match="regular directory"):
        environment.prepare_state(tmp_path)
    assert state.read_text() == "keep this data"


def test_public_check_is_offline_and_ignores_unavailable_protected_runtime(
    tmp_path: Path,
) -> None:
    environment.prepare_state(tmp_path)
    with (
        patch.object(environment.shutil, "which", return_value="/usr/bin/public-tool"),
        patch.object(
            environment.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0),
        ) as run,
        patch.object(
            environment,
            "installed_adapter",
            side_effect=AssertionError("public readiness must not attach"),
        ),
    ):
        result = environment.public_readiness(tmp_path)

    assert result["public_core"] == "ready"
    assert result["protected_capabilities"] == "not-requested"
    assert len(run.call_args_list) == 3
    for call in run.call_args_list:
        assert call.kwargs["timeout"] == environment.CHECK_TIMEOUT
        assert call.kwargs["stdout"] == subprocess.DEVNULL
        assert call.kwargs["stderr"] == subprocess.DEVNULL


def test_missing_or_hung_tools_cannot_report_readiness(tmp_path: Path) -> None:
    environment.prepare_state(tmp_path)
    with (
        patch.object(environment.shutil, "which", return_value=None),
        patch.object(
            environment.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired("tool", 5),
        ),
    ):
        result = environment.public_readiness(tmp_path)
    assert result["public_core"] == "unavailable"
    assert result["checks"]["private_practice_directory"]
    assert not result["checks"]["python_3_14_and_pytest"]


def test_provider_credentials_and_loader_overrides_are_not_forwarded() -> None:
    with patch.dict(
        os.environ,
        {
            "PATH": "/usr/bin",
            "HOME": "/home/learner",
            "GH_TOKEN": "private",
            "BAO_TOKEN": "private",
            "LD_PRELOAD": "private",
            "HTTPS_PROXY": "private",
        },
        clear=True,
    ):
        assert environment.child_environment() == {
            "PATH": "/usr/bin",
            "HOME": "/home/learner",
        }


def test_missing_seat_adapter_remains_explicitly_unavailable() -> None:
    with patch.object(environment, "installed_adapter", return_value=None):
        result, status = environment.protected_capability()
    assert status == 78
    assert result["protected_capabilities"] == "unavailable"
    assert result["public_core"] == "independent"


def test_writable_checkout_cannot_supply_the_authoritative_adapter(
    tmp_path: Path,
) -> None:
    adapter = tmp_path / "portable-seat-attach"
    adapter.write_text("#!/bin/sh\nexit 0\n")
    adapter.chmod(0o755)
    with patch.object(environment.shutil, "which", return_value=str(adapter)):
        assert environment.installed_adapter() is None


def test_user_owned_alias_cannot_claim_admission_from_a_root_owned_program(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = tmp_path / "portable-seat-attach"
    adapter.symlink_to("/usr/bin/true")
    monkeypatch.setenv("PATH", str(tmp_path))

    result, status = environment.protected_capability()

    assert status == 78
    assert result["protected_capabilities"] == "unavailable"


def test_root_owned_symlink_carrier_and_ancestry_qualify() -> None:
    # Use the operating system's genuine root-managed symlink chain; only the
    # command lookup is substituted. This checks installation, not admission.
    carrier = Path("/bin/sh")
    with patch.object(environment.shutil, "which", return_value=str(carrier)):
        assert environment.installed_adapter() == carrier.resolve(strict=True)


def test_replaceable_parent_alias_cannot_select_a_root_owned_program(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "system-bin"
    parent.symlink_to("/usr/bin", target_is_directory=True)
    with patch.object(environment.shutil, "which", return_value=str(parent / "true")):
        assert environment.installed_adapter() is None


def test_relative_lookup_cannot_select_a_root_owned_program(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir("/")
    with patch.object(environment.shutil, "which", return_value="usr/bin/true"):
        assert environment.installed_adapter() is None


@pytest.mark.parametrize(
    ("returncode", "expected"),
    [(0, "admitted"), (78, "unavailable"), (1, "unavailable")],
)
def test_admission_comes_only_from_installed_adapter(
    returncode: int, expected: str
) -> None:
    adapter = Path("/immutable/portable-seat-attach")
    with (
        patch.object(environment, "installed_adapter", return_value=adapter),
        patch.object(
            environment.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], returncode),
        ) as run,
    ):
        result, status = environment.protected_capability()
    assert result["protected_capabilities"] == expected
    assert status == (0 if returncode == 0 else 78)
    assert run.call_args.args == ([str(adapter)],)
    assert run.call_args.kwargs["stdin"] == subprocess.DEVNULL
    assert run.call_args.kwargs["stdout"] == subprocess.DEVNULL
    assert run.call_args.kwargs["stderr"] == subprocess.DEVNULL
    assert run.call_args.kwargs["timeout"] == environment.ADAPTER_TIMEOUT


def test_hung_adapter_cannot_leave_a_successful_readiness_result() -> None:
    with (
        patch.object(
            environment, "installed_adapter", return_value=Path("/immutable/adapter")
        ),
        patch.object(
            environment.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired("adapter", 15),
        ),
    ):
        result, status = environment.protected_capability()
    assert status == 78
    assert result["protected_capabilities"] == "unavailable"


def test_cli_missing_adapter_is_machine_readable_and_nonzero() -> None:
    process = subprocess.run(
        [sys.executable, str(ROOT / "scripts/environment.py"), "protected"],
        env={"PATH": "/nonexistent"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 78
    assert json.loads(process.stdout)["protected_capabilities"] == "unavailable"
    assert process.stderr == ""
