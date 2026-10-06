"""Verify exact personal-fork Codespaces identity independently of providers."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import codespaces_acceptance as acceptance  # type: ignore[import-not-found]

SHA = "a" * 40
PRODUCT = "DSA-Woodshed/dsa-study-packet"
SOURCE = "Jesssullivan/dsa-study-packet-contrib"
PRODUCT_ID = 1184530300
ENV = {"CODESPACES": "true", "CODESPACE_NAME": "exact-fork-proof"}


def _root(tmp_path: Path) -> Path:
    (tmp_path / "tinyland.repo.json").write_text(
        json.dumps({"repo": {"github": PRODUCT}})
    )
    return tmp_path


def _outputs() -> dict[tuple[str, ...], str]:
    return {
        ("gh", "api", f"repos/{PRODUCT}"): json.dumps(
            {"id": PRODUCT_ID, "full_name": PRODUCT, "fork": False}
        ),
        ("gh", "api", f"repos/{SOURCE}"): json.dumps(
            {
                "id": 2,
                "full_name": SOURCE,
                "fork": True,
                "parent": {"id": PRODUCT_ID, "full_name": PRODUCT},
            }
        ),
        (
            "gh",
            "api",
            f"repos/{SOURCE}/branches/codespaces-acceptance-fork",
            "--jq",
            ".commit.sha",
        ): SHA,
        ("git", "rev-parse", "HEAD"): SHA,
        ("git", "remote", "get-url", "origin"): f"git@github.com:{SOURCE}.git",
        ("git", "status", "--porcelain=v1", "--untracked-files=normal"): "",
        ("code", "--version"): "1.131.0\ncommit\narm64",
        ("code", "--list-extensions", "--show-versions"): "ms-python.python@2026.10.0",
    }


def _mock_capture(
    monkeypatch: pytest.MonkeyPatch, outputs: dict[tuple[str, ...], str]
) -> None:
    monkeypatch.setattr(
        acceptance, "_capture", lambda command, _cwd: outputs[tuple(command)]
    )


def test_plan_resolves_only_the_verified_fork_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = _outputs()
    _mock_capture(monkeypatch, outputs)
    lines = acceptance.plan(_root(tmp_path), "codespaces-acceptance-fork", SOURCE)
    assert f"PRODUCT_REPOSITORY: {PRODUCT}" in lines
    assert f"SOURCE_REPOSITORY: {SOURCE}" in lines
    assert "SOURCE_RELATION: TRUE_PRODUCT_FORK" in lines
    assert f"EXPECTED_SHA: {SHA}" in lines
    assert (
        f"CREATE_URL: https://codespaces.new/{SOURCE}/tree/codespaces-acceptance-fork"
        in lines
    )
    assert "HOSTED_ACCEPTANCE: NOT_TESTED" in lines
    assert not any("COPILOT" in line or "quickstart" in line for line in lines)
    assert f"`just codespaces-acceptance-verify {SHA} {SOURCE}`" in lines[-1]


def test_plan_can_infer_the_personal_source_from_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_capture(monkeypatch, _outputs())
    assert f"SOURCE_REPOSITORY: {SOURCE}" in acceptance.plan(
        _root(tmp_path), "codespaces-acceptance-fork"
    )


@pytest.mark.parametrize("source", [PRODUCT, "not-a-repository", "../copied-repo"])
def test_plan_rejects_product_pushes_and_invalid_repository_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    _mock_capture(monkeypatch, _outputs())
    with pytest.raises(acceptance.AcceptanceError):
        acceptance.plan(_root(tmp_path), "codespaces-acceptance-fork", source)


@pytest.mark.parametrize(
    "change",
    [
        {"fork": False},
        {"parent": {"id": 9, "full_name": PRODUCT}},
        {"parent": {"id": PRODUCT_ID, "full_name": "Elsewhere/copied-repo"}},
        {"full_name": "Elsewhere/different-fork"},
    ],
)
def test_copied_or_unrelated_repository_cannot_claim_fork_acceptance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: dict[str, object]
) -> None:
    outputs = _outputs()
    key = ("gh", "api", f"repos/{SOURCE}")
    record = json.loads(outputs[key]) | change
    outputs[key] = json.dumps(record)
    _mock_capture(monkeypatch, outputs)
    with pytest.raises(acceptance.AcceptanceError, match="NOT_PRODUCT_FORK"):
        acceptance.plan(_root(tmp_path), "codespaces-acceptance-fork", SOURCE)


def test_plan_rejects_a_non_disposable_branch(tmp_path: Path) -> None:
    with pytest.raises(acceptance.AcceptanceError, match="BRANCH: INVALID"):
        acceptance.plan(_root(tmp_path), "main", SOURCE)


def test_verify_checks_exact_selected_source_without_requiring_an_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_capture(monkeypatch, _outputs())
    lines = acceptance.verify(_root(tmp_path), SHA, ENV, SOURCE)
    assert f"PRODUCT_REPOSITORY: {PRODUCT}" in lines
    assert f"SOURCE_REPOSITORY: {SOURCE}" in lines
    assert "REPOSITORY_CHECKOUT: PASS" in lines
    assert "EDITOR_CLI: METADATA_RECORDED" in lines
    assert "NATIVE_EDITOR_ACCEPTANCE: NOT_TESTED" in lines
    assert "WORKTREE: CLEAN (ignored private state excluded)" in lines
    assert "REPOSITORY_WRITE_AUTH: NOT_TESTED" in lines
    assert "HOSTED_PRACTICE_ACCEPTANCE: NOT_TESTED" in lines
    assert "FEEDBACK_PROVIDER: OPTIONAL_NOT_TESTED" in lines
    assert "PROTECTED_CAPABILITY: OPTIONAL_NOT_TESTED" in lines
    assert not any("COPILOT" in line for line in lines)


@pytest.mark.parametrize(
    "reason",
    ["COMMAND: MISSING (code)", "COMMAND: FAILED (code)", "COMMAND: TIMED_OUT (code)"],
)
def test_unavailable_editor_does_not_hide_valid_source_or_claim_attachment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reason: str
) -> None:
    outputs = _outputs()

    def capture(command: list[str], _cwd: Path) -> str:
        if command[0] == "code":
            raise acceptance.AcceptanceError(reason)
        return outputs[tuple(command)]

    monkeypatch.setattr(acceptance, "_capture", capture)
    lines = acceptance.verify(_root(tmp_path), SHA, ENV, SOURCE)
    assert "REPOSITORY_CHECKOUT: PASS" in lines
    assert "EDITOR_CLI: UNAVAILABLE" in lines
    assert f"EDITOR_CLI_REASON: {reason}" in lines
    assert "NATIVE_EDITOR_ACCEPTANCE: NOT_TESTED" in lines
    assert "EXTENSION_LIST: RECORDED" not in lines


@pytest.mark.parametrize(
    "output", ["", "Command is only available inside a VS Code terminal."]
)
def test_success_exit_without_editor_version_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output: str
) -> None:
    outputs = _outputs()
    outputs[("code", "--version")] = output
    _mock_capture(monkeypatch, outputs)
    lines = acceptance.verify(_root(tmp_path), SHA, ENV, SOURCE)
    assert "REPOSITORY_CHECKOUT: PASS" in lines
    assert "EDITOR_CLI: UNAVAILABLE" in lines
    assert "NATIVE_EDITOR_ACCEPTANCE: NOT_TESTED" in lines


def test_capture_bounds_an_owned_stalled_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(acceptance, "COMMAND_TIMEOUT_SECONDS", 0.1)
    with pytest.raises(acceptance.AcceptanceError, match="COMMAND: TIMED_OUT"):
        acceptance._capture(
            [sys.executable, "-c", "import time; time.sleep(10)"], tmp_path
        )


def test_required_source_command_timeout_is_still_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def stalled(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired("git", acceptance.COMMAND_TIMEOUT_SECONDS)

    monkeypatch.setattr(acceptance.subprocess, "run", stalled)
    with pytest.raises(acceptance.AcceptanceError, match="COMMAND: TIMED_OUT \\(git"):
        acceptance.verify(_root(tmp_path), SHA, ENV, SOURCE)


def test_verify_rejects_another_origin_even_when_the_sha_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = _outputs()
    outputs[("git", "remote", "get-url", "origin")] = (
        "git@github.com:AnotherUser/dsa-study-packet-contrib.git"
    )
    _mock_capture(monkeypatch, outputs)
    with pytest.raises(acceptance.AcceptanceError, match="EXPECTED_REPOSITORY"):
        acceptance.verify(_root(tmp_path), SHA, ENV, SOURCE)


def test_verify_rechecks_actual_fork_parent_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = _outputs()
    outputs[("gh", "api", f"repos/{SOURCE}")] = json.dumps(
        {"id": 2, "full_name": SOURCE, "fork": False}
    )
    _mock_capture(monkeypatch, outputs)
    with pytest.raises(acceptance.AcceptanceError, match="NOT_PRODUCT_FORK"):
        acceptance.verify(_root(tmp_path), SHA, ENV, SOURCE)


def test_verify_rejects_a_stale_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = _outputs()
    outputs[("git", "rev-parse", "HEAD")] = "b" * 40
    _mock_capture(monkeypatch, outputs)
    with pytest.raises(acceptance.AcceptanceError, match="delete this stale Codespace"):
        acceptance.verify(_root(tmp_path), SHA, ENV, SOURCE)


@pytest.mark.parametrize(
    "status", [" M .devcontainer/devcontainer.json", "?? conftest.py"]
)
def test_verify_rejects_lifecycle_mutation_and_untracked_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    outputs = _outputs()
    outputs[("git", "status", "--porcelain=v1", "--untracked-files=normal")] = status
    _mock_capture(monkeypatch, outputs)
    with pytest.raises(acceptance.AcceptanceError, match="WORKTREE: DIRTY"):
        acceptance.verify(_root(tmp_path), SHA, ENV, SOURCE)


def test_verify_rejects_a_non_codespaces_environment(tmp_path: Path) -> None:
    with pytest.raises(acceptance.AcceptanceError, match="CODESPACES: NOT_DETECTED"):
        acceptance.verify(_root(tmp_path), SHA, {}, SOURCE)


def test_expected_sha_must_be_lowercase(tmp_path: Path) -> None:
    with pytest.raises(acceptance.AcceptanceError, match="EXPECTED_SHA: INVALID"):
        acceptance.verify(_root(tmp_path), "A" * 40, ENV, SOURCE)


def test_verification_requires_the_recorded_source_argument() -> None:
    with pytest.raises(SystemExit):
        acceptance._parser().parse_args(["verify", "--expected-sha", SHA])
