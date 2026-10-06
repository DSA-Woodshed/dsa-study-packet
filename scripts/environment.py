"""Public environment readiness and an optional installed seat-adapter bridge.

Setup preserves candidate files. Public checks are offline. The optional adapter
validates local runtime bindings; it does not establish issuer authorization.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK_TIMEOUT = 5
ADAPTER_TIMEOUT = 15


def prepare_state(root: Path) -> Path:
    state = root / ".challenges"
    with contextlib.suppress(FileExistsError):
        state.mkdir(mode=0o700)
    info = state.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError(
            ".challenges must be your regular directory, without a symlink"
        )
    state.chmod(0o700)
    return state


def private_state(root: Path) -> bool:
    try:
        info = (root / ".challenges").lstat()
        return (
            stat.S_ISDIR(info.st_mode)
            and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) == 0o700
        )
    except OSError:
        return False


def child_environment() -> dict[str, str]:
    # Public checks and the installed adapter need ordinary account paths,
    # never ambient provider tokens, loader overrides or proxy settings.
    names = {"HOME", "USER", "LOGNAME", "PATH", "LANG", "TMPDIR", "XDG_RUNTIME_DIR"}
    return {name: value for name, value in os.environ.items() if name in names}


def public_readiness(root: Path) -> dict[str, object]:
    checks = {"private_practice_directory": private_state(root)}
    for name in ("uv", "just"):
        executable = shutil.which(name)
        try:
            result = subprocess.run(
                [executable, "--version"] if executable else ["/nonexistent"],
                cwd=root,
                env=child_environment(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=CHECK_TIMEOUT,
                check=False,
            )
            checks[name] = result.returncode == 0
        except OSError, subprocess.TimeoutExpired:
            checks[name] = False
    try:
        result = subprocess.run(
            [
                str(root / ".venv/bin/python"),
                "-I",
                "-c",
                "import importlib.util, sys; "
                "sys.exit(0 if sys.version_info[:2] == (3, 14) "
                "and importlib.util.find_spec('pytest') else 1)",
            ],
            cwd=root,
            env=child_environment(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=CHECK_TIMEOUT,
            check=False,
        )
        checks["python_3_14_and_pytest"] = result.returncode == 0
    except OSError, subprocess.TimeoutExpired:
        checks["python_3_14_and_pytest"] = False
    return {
        "public_core": "ready" if all(checks.values()) else "unavailable",
        "checks": checks,
        "practice_storage": (
            "codespaces-workspace"
            if Path("/workspaces") in root.resolve().parents
            else "local-workspace"
        ),
        "protected_capabilities": "not-requested",
    }


def installed_adapter() -> Path | None:
    executable = shutil.which("portable-seat-attach")
    if not executable:
        return None
    try:
        declared = Path(executable)
        if not declared.is_absolute():
            return None
        # Qualify each carrier before following its links: resolve() alone
        # discards user-owned aliases that can point at any root-owned program.
        path = Path("/")
        info = path.lstat()
        if info.st_uid != 0 or info.st_mode & 0o022:
            return None
        pending = list(declared.parts[1:])
        links = 0
        while pending:
            component = pending.pop(0)
            if component == "..":
                path = path.parent
                continue
            path = path / component
            info = path.lstat()
            if info.st_uid != 0:
                return None
            if stat.S_ISLNK(info.st_mode):
                links += 1
                if links > 40:
                    return None
                target = path.readlink()
                # Symlink mode 0777 does not grant mutation: its owner and
                # already-qualified containing directory control the carrier.
                pending = (
                    list(target.parts[1:] if target.is_absolute() else target.parts)
                    + pending
                )
                path = Path("/") if target.is_absolute() else path.parent
            elif info.st_mode & 0o022 or (pending and not stat.S_ISDIR(info.st_mode)):
                return None
        if not stat.S_ISREG(info.st_mode) or not os.access(path, os.X_OK):
            return None
        return path
    except OSError:
        return None


def protected_capability() -> tuple[dict[str, object], int]:
    # A successful attach validates local managed-runtime coordination. It
    # does not authenticate a subject or recheck issuer grants/withdrawal.
    boundary = {
        "issuer_authorization": "not-checked",
        "public_core": "independent",
    }
    adapter = installed_adapter()
    if adapter is None:
        return {
            **boundary,
            "protected_capabilities": "unavailable",
            "reason": "independently installed portable-seat-attach adapter absent or untrusted",
        }, 78
    try:
        result = subprocess.run(
            [str(adapter)],
            env=child_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=ADAPTER_TIMEOUT,
            check=False,
        )
    except OSError, subprocess.TimeoutExpired:
        return {
            **boundary,
            "protected_capabilities": "unavailable",
            "reason": "installed adapter failed or exceeded its readiness deadline",
        }, 78
    return {
        **boundary,
        "protected_capabilities": "local-runtime-validated"
        if result.returncode == 0
        else "unavailable",
        "reason": "installed adapter validated local runtime bindings; issuer authorization was not checked"
        if result.returncode == 0
        else "installed adapter did not validate local runtime bindings",
    }, 0 if result.returncode == 0 else 78


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("setup", "check", "protected"))
    args = parser.parse_args(argv)
    if args.action == "protected":
        result, status = protected_capability()
    elif args.action == "setup":
        try:
            prepare_state(ROOT)
        except (OSError, ValueError) as error:
            print(str(error), file=sys.stderr)
            return 1
        result, status = (
            {"practice_storage": "prepared", "candidate_files": "preserved"},
            0,
        )
    else:
        result = public_readiness(ROOT)
        status = 0 if result["public_core"] == "ready" else 1
    print(json.dumps(result, sort_keys=True))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
