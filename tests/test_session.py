"""Behavior of the public chooser and its existing workspace/receipt engine."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import catalog  # type: ignore[import-not-found]  # noqa: E402
import practice_workspace as practice  # type: ignore[import-not-found]  # noqa: E402
import session  # type: ignore[import-not-found]  # noqa: E402


@pytest.fixture
def session_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    files = {
        "src/algo/arrays/two_sum.py": '''"""Find two indices whose values add to the target.

Problem:
    Return the indices of two values whose sum is target.
"""

def two_sum(values: list[int], target: int) -> tuple[int, int]:
    for left, value in enumerate(values):
        for right in range(left + 1, len(values)):
            if value + values[right] == target:
                return left, right
    raise ValueError("no matching values")
''',
        "src/algo/__init__.py": "",
        "src/algo/arrays/__init__.py": "",
        "tests/arrays/test_two_sum.py": "from algo.arrays.two_sum import two_sum\n\ndef test_sum() -> None:\n    assert two_sum([2, 3], 5) == (0, 1)\n",
        "src/concepts/explanation.py": '"""A concept explanation."""\n',
        "src/practice/decomposition/ex01_example.md": "# Decomposition example\n\nAnalyze the constraints.\n",
        "reference-sheets/01-example.md": "# A reference\n\nRead this.\n",
        "reference-sheets/10-whiteboard-performance-protocol.md": "# Method\n\nChoose how to reason.\n",
        "scripts/study_schedule.py": "# Review queue implementation\n",
        "CONTRIBUTING.md": "# Contributing\n\nContribute from a fork.\n",
    }
    for relative, text in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgSign=false",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=tmp_path,
        check=True,
    )
    monkeypatch.setenv("PRACTICE_NO_OPEN", "1")
    return tmp_path


def test_inventory_discovers_material_and_counts_without_a_second_corpus(
    session_repo: Path,
) -> None:
    before = catalog.capability_inventory(session_repo)
    (session_repo / "src/concepts/addition.py").write_text('"""New concept."""\n')
    (session_repo / "src/practice/decomposition/ex02_new.md").write_text(
        "# New exercise\n"
    )
    (session_repo / "reference-sheets/02-new.md").write_text("# New reference\n")
    after = catalog.capability_inventory(session_repo)
    for kind in ("concept", "advanced", "reference"):
        assert after["counts"][kind] == before["counts"][kind] + 1
    available = [
        entry for entry in after["capabilities"] if entry["availability"] == "available"
    ]
    assert {entry["kind"] for entry in available} == {
        "algorithm",
        "concept",
        "advanced",
        "reference",
        "method",
        "review",
        "contribution",
    }
    assert len({entry["id"] for entry in available}) == len(available)
    assert len({entry["source"] for entry in available}) == len(available)


def test_inventory_export_needs_no_installed_packet_dependencies() -> None:
    process = subprocess.run(
        [sys.executable, "-S", str(SCRIPTS / "catalog.py"), "--json"],
        text=True,
        capture_output=True,
        check=True,
    )
    value = json.loads(process.stdout)
    assert value["schema"] == 1
    assert sum(value["counts"].values()) == len(value["capabilities"])
    assert next(
        entry
        for entry in value["capabilities"]
        if entry["id"] == "algorithm/arrays/two_sum"
    )["modes"] == ["study", "implement", "tests-first", "talk", "board", "mock"]


def test_study_readiness_is_explicit_and_never_runs_tests(
    session_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_tests(*_args: object, **_kwargs: object) -> None:
        pytest.fail("study, opening, readiness, and closeout must not run tests")

    monkeypatch.setattr(practice, "_execute_test_run", no_tests)
    identity = "algorithm/arrays/two_sum"
    assert session.start_session(session_repo, identity, "study", 15) == 0
    record = session.current_session(session_repo)["selection"]
    assert not (session_repo / practice.WORKSPACE_REL).exists()
    source = session_repo / record["study"]["source"]
    assert source.stat().st_mode & 0o222 == 0
    assert session.resume_session(session_repo) == 0
    with pytest.raises(practice.PracticeError, match="explicitly choose readiness"):
        session.start_session(session_repo, identity, "implement", 30)
    assert (
        session.start_session(session_repo, identity, "tests-first", 30, ready=True)
        == 0
    )
    state = session.current_session(session_repo)
    assert state["selection"]["studied"] is True
    assert state["selection"]["focus"] == "test"
    assert state["workspace"]["session_id"] == state["selection"]["workspace_id"]
    candidate = session_repo / state["workspace"]["source"]
    assert "return left, right" not in candidate.read_text()
    candidate.write_text(
        candidate.read_text()
        + "\n# My notes use ordinary prose, with no special schema.\n"
    )
    assert session.finish_session(session_repo, "trace my edge case") == 0
    assert practice.current_metadata(session_repo)["test_outcome"] == "not_run"
    assert "My notes use ordinary prose" in candidate.read_text()


def test_closing_study_does_not_schedule_a_rep(session_repo: Path) -> None:
    session.start_session(session_repo, "algorithm/arrays/two_sum", "study", 15)
    session.finish_session(session_repo, "read the return contract")
    assert not (session_repo / ".challenges/reps.md").exists()
    assert not (session_repo / ".challenges/progress.md").exists()
    assert session.current_session(session_repo)["state"] == "CLOSED"


@pytest.mark.parametrize("mode", ["talk", "board", "mock"])
def test_presentation_closes_once_without_inventing_scores(
    session_repo: Path, mode: str
) -> None:
    session.start_session(session_repo, "algorithm/arrays/two_sum", mode, 30)
    assert practice.current_metadata(session_repo)["prepared_only"] is True
    session.finish_session(session_repo, "trace the duplicate value")
    session.finish_session(session_repo, "trace the duplicate value")
    log = (session_repo / ".challenges/reps.md").read_text().splitlines()
    assert len(log) == 1
    assert log[0].endswith("fix: trace the duplicate value")
    assert "C0" not in log[0]
    assert (session_repo / ".challenges/progress.md").read_text().count(
        "arrays/two_sum"
    ) == 1
    assert session.resume_session(session_repo) == 0


def test_reading_resume_and_history_use_immutable_source_and_private_receipts(
    session_repo: Path,
) -> None:
    original = (session_repo / "src/concepts/explanation.py").read_text()
    session.start_session(session_repo, "concept/explanation", "read", 15)
    record = session.current_session(session_repo)["selection"]
    snapshot = session_repo / record["reading"]["source"]
    assert snapshot.read_text() == original
    assert snapshot.stat().st_mode & 0o222 == 0
    assert session.resume_session(session_repo) == 0
    session.finish_session(session_repo, "explain the tradeoff")
    session.start_session(session_repo, "contribution/guide", "contribute", 30)
    saved = session._read_choice(session_repo)
    assert saved["history"][-1]["note"] == "explain the tradeoff"
    assert saved["history"][-1]["reading"]["source"] == record["reading"]["source"]
    assert (session_repo / "src/concepts/explanation.py").read_text() == original


def test_reading_snapshot_cannot_redirect_to_a_tracked_source(
    session_repo: Path,
) -> None:
    session.start_session(session_repo, "concept/explanation", "read", 15)
    choice = session._read_choice(session_repo)
    choice["current"]["reading"]["source"] = "src/concepts/explanation.py"
    session._save_choice(session_repo, choice)
    with pytest.raises(practice.PracticeError, match="invalid reading snapshot"):
        session.resume_session(session_repo)
    assert (session_repo / "src/concepts/explanation.py").stat().st_mode & 0o200


def test_reading_drift_is_reported_without_overwriting_it(session_repo: Path) -> None:
    session.start_session(session_repo, "concept/explanation", "read", 15)
    record = session.current_session(session_repo)["selection"]
    snapshot = session_repo / record["reading"]["source"]
    snapshot.chmod(0o644)
    snapshot.write_text("changed privately")
    with pytest.raises(practice.PracticeError, match="drifted"):
        session.resume_session(session_repo)
    assert snapshot.read_text() == "changed privately"


def test_reading_snapshot_cannot_change_permissions_of_a_hard_linked_source(
    session_repo: Path,
) -> None:
    session.start_session(session_repo, "concept/explanation", "read", 15)
    record = session.current_session(session_repo)["selection"]
    snapshot = session_repo / record["reading"]["source"]
    source = session_repo / "src/concepts/explanation.py"
    snapshot.unlink()
    os.link(source, snapshot)
    with pytest.raises(practice.PracticeError, match="detached regular file"):
        session.resume_session(session_repo)
    assert source.stat().st_mode & 0o200


def test_review_shows_due_targets_without_starting_an_editor_rep(
    session_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    session.start_session(session_repo, "review/due", "review", 15)
    assert capsys.readouterr().out.count("DUE:") == 5
    assert not (session_repo / practice.WORKSPACE_REL).exists()
    session.finish_session(session_repo, "choose a graph problem next")
    assert not (session_repo / ".challenges/progress.md").exists()


def test_an_open_reading_activity_cannot_be_silently_replaced(
    session_repo: Path,
) -> None:
    session.start_session(session_repo, "concept/explanation", "read", 15)
    with pytest.raises(practice.PracticeError, match="already open"):
        session.start_session(session_repo, "algorithm/arrays/two_sum", "implement", 30)
    assert not (session_repo / practice.WORKSPACE_REL).exists()


def test_failed_editor_open_retains_the_same_session_for_headless_resume(
    session_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("PRACTICE_NO_OPEN")
    monkeypatch.setattr(practice.shutil, "which", lambda _: None)
    assert (
        session.start_session(session_repo, "algorithm/arrays/two_sum", "implement", 30)
        == 1
    )
    saved = session.current_session(session_repo)["workspace"]["session_id"]
    assert "OPEN_FAILED" in capsys.readouterr().out
    assert session.resume_session(session_repo, no_open=True) == 0
    assert session.current_session(session_repo)["workspace"]["session_id"] == saved


@pytest.mark.parametrize("minutes", [0, -1, 1441, True])
def test_invalid_budgets_do_not_create_a_workspace(
    session_repo: Path, minutes: int
) -> None:
    with pytest.raises(practice.PracticeError, match="whole number"):
        session.start_session(
            session_repo, "algorithm/arrays/two_sum", "implement", minutes
        )
    assert not (session_repo / practice.WORKSPACE_REL).exists()


def test_legacy_start_study_readiness_and_finish_share_the_dispatcher(
    session_repo: Path,
) -> None:
    assert session.dispatch_workspace(session_repo, ["study", "arrays", "two_sum"]) == 0
    assert (
        session.dispatch_workspace(
            session_repo, ["start", "comments", "arrays", "two_sum"]
        )
        == 0
    )
    metadata = practice.current_metadata(session_repo)
    assert (
        session.current_session(session_repo)["selection"]["workspace_id"]
        == metadata["session_id"]
    )
    assert session.dispatch_workspace(session_repo, ["next"]) == 0
    assert (
        session.dispatch_workspace(session_repo, ["finish", "trace the empty input"])
        == 0
    )
    assert session.current_session(session_repo)["state"] == "CLOSED"


def test_explicit_fresh_archive_preserves_the_prior_choice_and_candidate(
    session_repo: Path,
) -> None:
    session.start_session(session_repo, "algorithm/arrays/two_sum", "implement", 30)
    before = practice.current_metadata(session_repo)
    candidate = session_repo / before["source"]
    candidate.write_text(candidate.read_text() + "\n# Preserve this draft.\n")
    assert (
        session.dispatch_workspace(
            session_repo, ["start", "comments", "arrays", "two_sum", "--fresh"]
        )
        == 0
    )
    after = session.current_session(session_repo)
    assert before["session_id"] != after["workspace"]["session_id"]
    assert session._read_choice(session_repo)["history"][-1]["transition"] == "archive"
    archived = list((session_repo / practice.HISTORY_REL).glob("*/two_sum.py"))
    assert any("Preserve this draft." in path.read_text() for path in archived)


def test_dialogue_requires_an_exact_choice_and_accepts_a_custom_budget(
    session_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    answers = iter(["implement", "22", "two sum"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert session._choose(session_repo) == (
        "algorithm/arrays/two_sum",
        "implement",
        22,
    )


def test_recreated_runtime_can_resume_saved_state(session_repo: Path) -> None:
    session.start_session(session_repo, "algorithm/arrays/two_sum", "implement", 30)
    identity = practice.current_metadata(session_repo)["session_id"]
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            "import pathlib,sys;sys.path.insert(0,sys.argv[1]);import session;raise SystemExit(session.main(['resume','--no-open'],root=pathlib.Path(sys.argv[2])))",
            str(SCRIPTS),
            str(session_repo),
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    assert "After an explicit save, run just practice-next." in process.stdout
    assert practice.current_metadata(session_repo)["session_id"] == identity


def test_resume_and_repeated_start_wait_for_an_explicit_save_boundary(
    session_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = "algorithm/arrays/two_sum"
    session.start_session(session_repo, identity, "implement", 30)
    metadata = practice.current_metadata(session_repo)
    source = session_repo / metadata["source"]
    source.write_text(source.read_text() + "\n# My incomplete draft.\n")

    def unexpected_review(*_args: object, **_kwargs: object) -> None:
        pytest.fail("opening a saved draft is not an explicit save/review boundary")

    monkeypatch.setattr(practice, "_next_source_native_step", unexpected_review)
    assert session.resume_session(session_repo) == 0
    assert session.start_session(session_repo, identity, "implement", 30) == 0
    assert "My incomplete draft." in source.read_text()


def test_explicit_tests_produce_the_receipt_used_by_closeout(
    session_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session.start_session(session_repo, "algorithm/arrays/two_sum", "tests-first", 30)
    metadata = practice.current_metadata(session_repo)
    candidate = session_repo / metadata["source"]
    candidate.write_text(
        candidate.read_text().replace("raise NotImplementedError", "return (0, 1)")
    )
    (session_repo / metadata["candidate_test"]).write_text(
        "from algo.arrays.two_sum import two_sum\n\ndef test_my_example() -> None:\n    assert two_sum([2, 3], 5) == (0, 1)\n"
    )
    assert session.current_session(session_repo)["state"] == "REFLECT"
    assert session.dispatch_workspace(session_repo, ["test"]) == 0
    assert session.current_session(session_repo)["state"] == "CLOSE"

    def unexpected_pytest(*_args: object, **_kwargs: object) -> None:
        pytest.fail("finish must use the explicit test receipt")

    monkeypatch.setattr(practice, "_execute_test_run", unexpected_pytest)
    session.finish_session(session_repo, "add a no-match example next")
    assert practice.current_metadata(session_repo)["test_outcome"] == "passed"


def test_interrupted_choice_closeout_recovers_without_a_second_talk_rep(
    session_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session.start_session(session_repo, "algorithm/arrays/two_sum", "talk", 30)
    save = session._save_choice

    def interrupted_save(_root: Path, _value: object) -> None:
        raise OSError("simulated interrupted selection write")

    monkeypatch.setattr(session, "_save_choice", interrupted_save)
    with pytest.raises(OSError, match="interrupted"):
        session.finish_session(session_repo, "trace the first example")
    assert session.current_session(session_repo)["state"] == "CLOSED"
    monkeypatch.setattr(session, "_save_choice", save)
    session.finish_session(session_repo, "a different retry note")
    log = (session_repo / ".challenges/reps.md").read_text().splitlines()
    assert len(log) == 1
    assert log[0].endswith("fix: trace the first example")


def test_a_preexisting_workspace_can_resume_and_close_idempotently_without_a_choice_file(
    session_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        session_repo, "comments", "arrays", "two_sum"
    )
    assert not (session_repo / ".challenges/session-choice.json").exists()
    assert session.resume_session(session_repo) == 0
    assert session.finish_session(session_repo, "trace the existing draft") == 0
    assert session.finish_session(session_repo, "trace the existing draft") == 0
    assert session.current_session(session_repo)["state"] == "CLOSED"
    assert (session_repo / ".challenges/reps.md").read_text().count(
        "arrays/two_sum"
    ) == 1
    assert (
        practice.current_metadata(session_repo)["session_id"] == metadata["session_id"]
    )
