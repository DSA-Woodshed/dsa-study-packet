"""Guide a practice choice and dispatch to the existing private workspace.

Run ``just session`` for a dialogue, or use start/resume/finish/current for a
terminal, website, or optional personal adapter. No provider CLI is required.
Saved reasoning is ordinary prose. Opening, testing, and readiness are explicit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import practice_workspace as practice
from catalog import Capability, capabilities, matching_entries
from study_schedule import ranked_queue

ROOT = Path(__file__).resolve().parents[1]
CHOICE_FILE = "session-choice.json"
MAX_HISTORY = 100
EDITOR_MODES = {"implement", "tests-first"}
PRESENTATION_MODES = {"talk", "board", "mock"}
INTENT_OUTCOMES = {
    "study": "read a committed solution and its tests before choosing readiness",
    "implement": "reason in comments, write your implementation, and choose when to test",
    "tests-first": "begin with your own focused examples in the candidate test tab",
    "talk": "reason through an algorithm aloud with no clock",
    "board": "rehearse a board-style explanation within your chosen budget",
    "mock": "practice an observed interview with your chosen human or personal adapter",
    "read": "review a concept, advanced exercise, reference, or method snapshot",
    "review": "inspect your private due queue and choose the next problem",
    "contribute": "read the contribution guide and choose a change to contribute",
}


def _read_choice(root: Path) -> dict[str, Any]:
    path = practice._state_file(root, CHOICE_FILE)
    if not path.exists():
        return {"schema": 1, "current": None, "history": []}
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise practice.PracticeError(f"invalid session choice: {exc}") from exc
    if (
        not isinstance(value, dict)
        or value.get("schema") != 1
        or not isinstance(value.get("history"), list)
        or len(value["history"]) > MAX_HISTORY
        or (value.get("current") is not None and not isinstance(value["current"], dict))
    ):
        raise practice.PracticeError("invalid session choice fields")
    for record in [
        *value["history"],
        *([value["current"]] if value["current"] else []),
    ]:
        if (
            not isinstance(record, dict)
            or not all(
                isinstance(record.get(key), str)
                for key in ("id", "mode", "session_id", "started_at")
            )
            or type(record.get("minutes")) is not int
            or not 1 <= record["minutes"] <= 1440
        ):
            raise practice.PracticeError("invalid saved session")
    return value


def _save_choice(root: Path, value: dict[str, Any]) -> None:
    practice._replace_file(
        practice._state_file(root, CHOICE_FILE), json.dumps(value, indent=2) + "\n"
    )


def _capability(root: Path, identity: str) -> Capability:
    entry = next((entry for entry in capabilities(root) if entry.id == identity), None)
    if entry is None:
        raise practice.PracticeError(
            f"unknown capability: {identity}\nNEXT: just capabilities"
        )
    if entry.availability != "available":
        raise practice.PracticeError(
            f"capability source is unavailable: {entry.source}"
        )
    return entry


def _active_workspace(root: Path) -> dict[str, Any] | None:
    path = root / practice.WORKSPACE_REL / practice.METADATA_NAME
    if not path.exists() and not path.is_symlink():
        return None
    metadata = practice.current_metadata(root)
    if "finished_at" in metadata or practice._is_presented(metadata):
        return None
    return metadata


def _record_active(root: Path, record: dict[str, Any]) -> bool:
    if "closed_at" in record:
        return False
    if record.get("workspace_id"):
        metadata = _active_workspace(root)
        return metadata is not None and metadata["session_id"] == record["workspace_id"]
    return True


def _selection_guard(
    root: Path, identity: str, mode: str, *, ready: bool
) -> dict[str, Any]:
    choice = _read_choice(root)
    current = choice["current"]
    if current and _record_active(root, current):
        if current["id"] != identity:
            raise practice.PracticeError(
                'an activity is already open\nNEXT: just session finish "one correction"'
            )
        if current["mode"] == "study" and mode in EDITOR_MODES and not ready:
            raise practice.PracticeError(
                "study stays open until you explicitly choose readiness\n"
                f"NEXT: just session start {identity} --mode {mode} --minutes {current['minutes']} --ready"
            )
        if current["mode"] != mode and not (
            current["mode"] == "study" and mode in EDITOR_MODES
        ):
            raise practice.PracticeError(
                'finish the current mode before switching\nNEXT: just session finish "one correction"'
            )
    workspace = _active_workspace(root)
    if (
        workspace is not None
        and identity != f"algorithm/{workspace['topic']}/{workspace['problem']}"
    ):
        raise practice.PracticeError(
            'an editor or talk rep is already open\nNEXT: just practice-finish "one correction"'
        )
    return choice


def _reading_snapshot(root: Path, entry: Capability) -> dict[str, str]:
    revision = practice._head_revision(root)
    text = practice._committed_source_at(root, revision, Path(entry.source))
    digest = hashlib.sha256(text.encode()).hexdigest()
    parent = practice._confined_directory(
        root, practice._state_dir(root) / "reading", "reading snapshots", create=True
    )
    directory = practice._confined_directory(
        root, parent / digest, "reading snapshot", create=True
    )
    path = directory / Path(entry.source).name
    if path.is_symlink() or (
        path.exists() and (not path.is_file() or path.stat().st_nlink != 1)
    ):
        raise practice.PracticeError("reading snapshot must be a regular file")
    if path.exists() and path.read_text() != text:
        raise practice.PracticeError("reading snapshot drifted; preserve it and retry")
    if not path.exists():
        practice._replace_file(path, text)
    path.chmod(0o444)
    return {
        "source": path.relative_to(root).as_posix(),
        "revision": revision,
        "digest": digest,
    }


def _open_reading(
    root: Path, entry: Capability, record: dict[str, Any], *, no_open: bool
) -> int:
    snapshot = record["reading"]
    if not isinstance(snapshot, dict):
        raise practice.PracticeError("invalid reading snapshot")
    digest = snapshot.get("digest", "")
    expected = f".challenges/reading/{digest}/{Path(entry.source).name}"
    if (
        not isinstance(digest, str)
        or practice.HEX_DIGEST.fullmatch(digest) is None
        or snapshot.get("source") != expected
        or not isinstance(snapshot.get("revision"), str)
        or practice.GIT_OBJECT_ID.fullmatch(snapshot["revision"]) is None
    ):
        raise practice.PracticeError("invalid reading snapshot")
    parent = practice._confined_directory(
        root, practice._state_dir(root) / "reading", "reading snapshots", create=False
    )
    practice._confined_directory(
        root, parent / digest, "reading snapshot", create=False
    )
    path = practice._required_file(root, snapshot["source"], workspace=False)
    if path.stat().st_nlink != 1:
        raise practice.PracticeError("reading snapshot must be a detached regular file")
    if hashlib.sha256(path.read_bytes()).hexdigest() != snapshot["digest"]:
        raise practice.PracticeError("reading snapshot drifted")
    path.chmod(0o444)
    print(f"STATE: {'CLOSED' if 'closed_at' in record else 'READ'}")
    print(f"SOURCE: {snapshot['source']}")
    print(f"REVISION: {snapshot['revision']}")
    if not no_open and not os.environ.get("PRACTICE_NO_OPEN"):
        code = shutil.which("code")
        try:
            opened = (
                code is not None
                and subprocess.run(
                    [code, "--reuse-window", str(path)],
                    cwd=root,
                    check=False,
                    timeout=practice.EDITOR_OPEN_TIMEOUT_SECONDS,
                ).returncode
                == 0
            )
        except OSError, subprocess.TimeoutExpired:
            opened = False
        if not opened:
            print("OPEN_FAILED: restore the code CLI, then run just session resume")
            return 1
        print(f"OPENED: {snapshot['source']}")
    print('NEXT: read the snapshot, then run just session finish "one correction".')
    return 0


def start_session(
    root: Path,
    identity: str,
    mode: str,
    minutes: int,
    *,
    ready: bool = False,
    no_open: bool = False,
    paradigm: str = "comments",
) -> int:
    if type(minutes) is not int or not 1 <= minutes <= 1440:
        raise practice.PracticeError("minutes must be a whole number from 1 to 1440")
    entry = _capability(root, identity)
    if mode not in entry.modes:
        raise practice.PracticeError(
            f"unsupported mode {mode!r}; choose {', '.join(entry.modes)}"
        )
    with practice._practice_lock(root):
        choice = _selection_guard(root, identity, mode, ready=ready)
        current = choice["current"]
        if current and _record_active(root, current) and current["mode"] == mode:
            if mode in EDITOR_MODES and current.get("paradigm") != paradigm:
                raise practice.PracticeError(
                    "finish the current reasoning vocabulary before switching"
                )
            if current["minutes"] != minutes:
                raise practice.PracticeError(
                    "session budget is already selected; resume it or finish before changing it"
                )
            return resume_session(root, no_open=no_open)
        record: dict[str, Any] = {
            "id": identity,
            "mode": mode,
            "minutes": minutes,
            "session_id": str(uuid.uuid4()),
            "started_at": datetime.now(UTC).isoformat(),
        }
        if current:
            previous = dict(current)
            if not _record_active(root, current) and "closed_at" not in previous:
                previous["closed_at"] = datetime.now(UTC).isoformat()
            if current["mode"] == "study" and mode in EDITOR_MODES:
                previous["closed_at"] = datetime.now(UTC).isoformat()
                previous["transition"] = mode
                record["studied"] = True
            choice["history"] = [*choice["history"], previous][-MAX_HISTORY:]
        if entry.kind == "algorithm":
            _, topic, problem = identity.split("/")
            if mode == "study":
                record["study"] = practice.prepare_study_snapshot(root, topic, problem)
            elif mode in EDITOR_MODES:
                metadata, action, archived = practice.prepare_session(
                    root, paradigm, topic, problem
                )
                record["workspace_id"] = metadata["session_id"]
                record["paradigm"] = paradigm
                focus = "test" if mode == "tests-first" else "source"
                record["focus"] = focus
            else:
                metadata = practice.prepare_open_target(root, topic, problem)
                metadata = practice.mark_presentation_started(root, metadata)
                record["workspace_id"] = metadata["session_id"]
        elif mode != "review":
            record["reading"] = _reading_snapshot(root, entry)
        choice["current"] = record
        _save_choice(root, choice)
        print(f"CAPABILITY: {identity}")
        print(f"MODE: {mode}")
        print(f"MINUTES: {minutes} (chosen budget; no automatic clock)")
        if mode in EDITOR_MODES:
            print(f"PREPARATION: {'STUDIED' if record.get('studied') else 'COLD'}")
            if (
                not no_open
                and not os.environ.get("PRACTICE_NO_OPEN")
                and not practice.open_session(root, metadata, focus=focus)
            ):
                return 1
            practice._print_start(root, metadata, action, archived, focus=focus)
            return 0
        return resume_session(root, no_open=no_open)


def current_session(root: Path, *, derive: bool = True) -> dict[str, Any]:
    with practice._practice_lock(root):
        choice = _read_choice(root)
        current = choice["current"]
        if current is None:
            path = root / practice.WORKSPACE_REL / practice.METADATA_NAME
            if not path.exists() and not path.is_symlink():
                raise practice.PracticeError("no session to resume\nNEXT: just session")
            metadata = practice.current_metadata(root)
            if "finished_at" in metadata or practice._is_presented(metadata):
                state = "CLOSED"
            elif practice._is_prepared(metadata):
                state = "PREPARED"
            else:
                state = practice.next_step(root, metadata)[0] if derive else "ACTIVE"
            return {
                "schema": 1,
                "selection": None,
                "workspace": metadata,
                "state": state,
            }
        result = {
            "schema": 1,
            "selection": current,
            "state": "CLOSED" if "closed_at" in current else current["mode"].upper(),
        }
        if current.get("workspace_id") and "closed_at" not in current:
            metadata = practice.current_metadata(root)
            if metadata["session_id"] != current["workspace_id"]:
                raise practice.PracticeError(
                    "session selection points to an older workspace\nNEXT: just practice-current"
                )
            result["workspace"] = metadata
            if "finished_at" in metadata or practice._is_presented(metadata):
                result["state"] = "CLOSED"
            elif derive and not practice._is_prepared(metadata):
                result["state"] = practice.next_step(root, metadata)[0]
        return result


def resume_session(root: Path, *, no_open: bool = False) -> int:
    current = current_session(root, derive=False)
    record = current["selection"]
    if current["state"] == "CLOSED":
        print("STATE: CLOSED\nNEXT: just session")
        return 0
    if record is None:
        metadata = current["workspace"]
        if (
            not no_open
            and not os.environ.get("PRACTICE_NO_OPEN")
            and not practice.open_session(root, metadata)
        ):
            return 1
        practice._print_start(root, metadata, "resumed", None)
        return 0
    entry = _capability(root, record["id"])
    print(
        f"CAPABILITY: {record['id']}\nMODE: {record['mode']}\nMINUTES: {record['minutes']}"
    )
    if record["mode"] == "study":
        manifest = record["study"]
        if f"algorithm/{manifest.get('topic')}/{manifest.get('problem')}" != entry.id:
            raise practice.PracticeError(
                "study snapshot belongs to a different selection"
            )
        if (
            not no_open
            and not os.environ.get("PRACTICE_NO_OPEN")
            and not practice.open_study_snapshot(root, manifest)
        ):
            return 1
        practice._validate_and_seal_study_snapshot(root, manifest)
        print(
            f"STATE: STUDY\nSTUDY_SOURCE: {manifest['source']}\nSTUDY_TEST: {manifest['test']}\nREVISION: {manifest['revision']}"
        )
        print(
            f"IMPLEMENT: just session start {entry.id} --mode implement --minutes {record['minutes']} --ready"
        )
        print(
            f"TESTS_FIRST: just session start {entry.id} --mode tests-first --minutes {record['minutes']} --ready"
        )
        print("NEXT: choose a readiness transition explicitly, or keep studying.")
        return 0
    if record.get("workspace_id"):
        metadata = current["workspace"]
        if (
            not no_open
            and not os.environ.get("PRACTICE_NO_OPEN")
            and not practice.open_session(
                root, metadata, focus=record.get("focus", "source")
            )
        ):
            return 1
        if record["mode"] in PRESENTATION_MODES:
            print(
                practice.present_problem(
                    root, metadata["topic"], metadata["problem"]
                ).rstrip()
            )
            print(
                f"STATE: {record['mode'].upper()}\nSOURCE: {metadata['source']}\nTEST: {metadata['candidate_test']}"
            )
            print(
                'NEXT: restate the problem and clarify it; close with just session finish "one correction".'
            )
            return 0
        practice._print_start(
            root, metadata, "resumed", None, focus=record.get("focus", "source")
        )
        return 0
    if record["mode"] == "review":
        for urgency, topic, problem in ranked_queue(
            practice._state_file(root, "progress.md")
        )[:5]:
            print(f"DUE: algorithm/{topic}/{problem} | urgency {urgency}")
        print(
            'STATE: REVIEW\nNEXT: close with just session finish "one correction", then choose a due algorithm explicitly.'
        )
        return 0
    return _open_reading(root, entry, record, no_open=no_open)


def finish_session(root: Path, note: str) -> int:
    normalized = practice._normalized_note(note)
    with practice._practice_lock(root):
        current = current_session(root)
        record = current["selection"]
        if record is None:
            if practice._is_prepared(current["workspace"]):
                raise practice.PracticeError(
                    "prepared tabs have no editor rep to close; use just rep-finish with the exact talk rep"
                )
            return practice.finish_session(root, current["workspace"], normalized)
        if "closed_at" in record:
            print(f"STATE: CLOSED\nRECEIPT: .challenges/{CHOICE_FILE}")
            return 0
        if record.get("workspace_id") and current["state"] != "CLOSED":
            metadata = current["workspace"]
            if record["mode"] in PRESENTATION_MODES:
                mode = {"talk": "talk", "board": "cold", "mock": "mock"}[record["mode"]]
                practice.finish_non_editor(
                    root,
                    metadata["topic"],
                    metadata["problem"],
                    f"{mode} {metadata['topic']}/{metadata['problem']} fix: {normalized}",
                )
            else:
                practice.finish_session(root, metadata, normalized)
        choice = _read_choice(root)
        choice["current"] = {
            **record,
            "closed_at": datetime.now(UTC).isoformat(),
            "note": normalized,
        }
        _save_choice(root, choice)
        print(f"STATE: CLOSED\nRECEIPT: .challenges/{CHOICE_FILE}\nNEXT: just session")
        return 0


def _choose(root: Path) -> tuple[str, str, int]:
    entries = tuple(
        entry for entry in capabilities(root) if entry.availability == "available"
    )
    counts = Counter(entry.kind for entry in entries)
    print("Choose how to use this session. Available material:")
    print(", ".join(f"{kind}: {counts[kind]}" for kind in sorted(counts)))
    offered_modes = [
        mode
        for mode in INTENT_OUTCOMES
        if any(mode in entry.modes for entry in entries)
    ]
    print("\n".join(f"{mode}: {INTENT_OUTCOMES[mode]}" for mode in offered_modes))
    mode = input(f"Intent [{' / '.join(offered_modes)}]: ").strip()
    eligible = tuple(entry for entry in entries if mode in entry.modes)
    if not eligible:
        raise practice.PracticeError("choose an intent from the offered list")
    raw = input("Time [15 / 30 / 60 / custom minutes]: ").strip()
    try:
        minutes = int(raw)
    except ValueError as exc:
        raise practice.PracticeError(
            "enter your budget as a whole number of minutes"
        ) from exc
    print(
        "\n".join(
            f"{entry.id} | {entry.title} | suggested {entry.duration} min"
            for entry in eligible
        )
    )
    query = input("Choose a capability ID or a problem name: ").strip()
    exact = [entry for entry in eligible if entry.id == query]
    if exact:
        matches = exact
    elif mode in {"study", *EDITOR_MODES, *PRESENTATION_MODES}:
        identities = {
            f"algorithm/{entry.slug}" for entry in matching_entries(query, root)
        }
        matches = [entry for entry in eligible if entry.id in identities]
    else:
        matches = [
            entry
            for entry in eligible
            if query and query.casefold() in f"{entry.id} {entry.title}".casefold()
        ]
    if len(matches) > 1:
        print(
            "\n".join(
                f"{index}. {entry.id} | {entry.title}"
                for index, entry in enumerate(matches, 1)
            )
        )
        try:
            selected = int(input("Choose the exact item number: ").strip())
        except ValueError as exc:
            raise practice.PracticeError("choose an exact item number") from exc
        if not 1 <= selected <= len(matches):
            raise practice.PracticeError("item number is outside the offered choices")
        matches = [matches[selected - 1]]
    if not matches:
        raise practice.PracticeError(
            "no available capability matches; run just session to choose again"
        )
    return matches[0].id, mode, minutes


def dispatch_workspace(root: Path, argv: list[str]) -> int:
    """Compatibility recipes share the engine and explicitly express intent."""
    args = practice._parser().parse_args(argv)
    if args.command in {"start", "study", "present"}:
        topic, problem = practice.select_problem(root, args.topic, args.problem)
        mode = (
            "study"
            if args.command == "study"
            else "talk"
            if args.command == "present"
            else "tests-first"
            if args.focus == "test"
            else "implement"
        )
        if args.command != "start" or not args.fresh:
            choice = _read_choice(root)
            current = choice["current"]
            minutes = (
                current["minutes"]
                if current and current["id"] == f"algorithm/{topic}/{problem}"
                else 30
            )
            return start_session(
                root,
                f"algorithm/{topic}/{problem}",
                mode,
                minutes,
                ready=True,
                no_open=getattr(args, "no_open", False),
                paradigm=getattr(args, "paradigm", "comments"),
            )
        # Fresh explicitly archives through the existing engine. Adopt its new
        # identity only after preparation succeeded, including an open failure.
        previous_metadata = _active_workspace(root)
        result = practice.main(argv, root=root)
        metadata = _active_workspace(root)
        if metadata is None or (
            previous_metadata
            and metadata["session_id"] == previous_metadata["session_id"]
        ):
            return result
        with practice._practice_lock(root):
            choice = _read_choice(root)
            if choice["current"]:
                archived = {
                    **choice["current"],
                    "closed_at": datetime.now(UTC).isoformat(),
                    "transition": "archive",
                }
                choice["history"] = [*choice["history"], archived][-MAX_HISTORY:]
            choice["current"] = {
                "id": f"algorithm/{metadata['topic']}/{metadata['problem']}",
                "mode": mode,
                "minutes": 30,
                "session_id": str(uuid.uuid4()),
                "started_at": datetime.now(UTC).isoformat(),
                "workspace_id": metadata["session_id"],
                "paradigm": args.paradigm,
                "focus": args.focus,
            }
            _save_choice(root, choice)
        return result
    if args.command == "finish":
        return finish_session(root, args.note)
    return practice.main(argv, root=root)


def main(argv: list[str] | None = None, *, root: Path | None = None) -> int:
    root = ROOT if root is None else root
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command")
    start = commands.add_parser("start")
    start.add_argument("id")
    start.add_argument("--mode", required=True)
    start.add_argument("--minutes", type=int, required=True)
    start.add_argument("--ready", action="store_true")
    start.add_argument("--no-open", action="store_true")
    start.add_argument(
        "--paradigm", choices=tuple(practice.PARADIGMS), default="comments"
    )
    resume = commands.add_parser("resume")
    resume.add_argument("--no-open", action="store_true")
    finish = commands.add_parser("finish")
    finish.add_argument("note")
    commands.add_parser("current")
    workspace = commands.add_parser("workspace")
    workspace.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        if args.command is None:
            if not sys.stdin.isatty():
                raise practice.PracticeError(
                    "interactive choice needs a terminal\nNEXT: just capabilities, then just session start <id> --mode <mode> --minutes 30"
                )
            identity, mode, minutes = _choose(root)
            return start_session(root, identity, mode, minutes)
        if args.command == "start":
            return start_session(
                root,
                args.id,
                args.mode,
                args.minutes,
                ready=args.ready,
                no_open=args.no_open,
                paradigm=args.paradigm,
            )
        if args.command == "resume":
            return resume_session(root, no_open=args.no_open)
        if args.command == "finish":
            return finish_session(root, args.note)
        if args.command == "current":
            print(json.dumps(current_session(root), indent=2))
            return 0
        if args.command == "workspace":
            return dispatch_workspace(root, args.args)
    except (practice.PracticeError, EOFError, KeyboardInterrupt) as exc:
        print(f"session: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
