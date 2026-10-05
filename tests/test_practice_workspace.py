"""Tests for the isolated, editor-first practice workspace."""

from __future__ import annotations

import ast
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Any, cast

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
REPO_ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import practice_workspace as practice  # type: ignore[import-not-found]  # noqa: E402
from core42 import (  # type: ignore[import-not-found]  # noqa: E402
    CORE_42,
    PRACTICE_TARGETS,
)

SOURCE = '''"""arrays / {problem}

Problem:
    Return the sum of the values.

Approach:
    This committed explanation must not reach the cold workspace.
"""

from dataclasses import dataclass


@dataclass
class Wrapper:
    value: int


def solve(values: list[int]) -> int:
    """Return the sum."""
    secret = _support(values)
    return secret


def alternate(values: list[int]) -> int:
    """Committed alternate used by the complete reference test file."""
    return _support(values)


def _support(values: list[int]) -> int:
    return sum(values)
'''

LRU_SOURCE = '''"""linked_lists / lru_cache

Problem:
    Keep the least recently used entry at the front.
"""

from collections import OrderedDict


class LRUCache:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.cache: OrderedDict[int, int] = OrderedDict()

    def get(self, key: int) -> int:
        if key not in self.cache:
            return -1
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: int, value: int) -> None:
        self.cache[key] = value
        self.cache.move_to_end(key)
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)
'''


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _inject_after_future(source: str, injected: str) -> str:
    marker = "from __future__ import annotations\n"
    assert marker in source
    return source.replace(marker, f"{marker}\n{injected}", 1)


def _legacy_schema4_metadata(
    metadata: dict[str, Any], paradigm_name: str | None = None
) -> dict[str, Any]:
    name = paradigm_name or str(metadata["paradigm"])
    paradigm = practice._metadata_paradigm(name)
    assert paradigm is not None
    legacy = dict(metadata)
    legacy.update(
        {
            "schema": practice.LEGACY_METADATA_SCHEMA,
            "paradigm": name,
            "paradigm_title": practice.LEGACY_SCHEMA4_TITLES[name],
            "seeds": list(paradigm.seeds),
            "pre_code_labels": list(
                practice._legacy_schema4_pre_code_labels(name, paradigm)
            ),
            "lock": practice.LEGACY_SCHEMA4_LOCK,
        }
    )
    return legacy


def _rewrite_as_legacy_prepared(
    root: Path, metadata: dict[str, Any], *, extra_source: str = ""
) -> str:
    paradigm = practice.PARADIGMS["comments"]
    source_path = root / str(metadata["source"])
    legacy_lines = [
        *paradigm.seeds[:3],
        practice.LEGACY_SCHEMA4_LOCK,
        *paradigm.seeds[3:],
    ]
    legacy_block = "".join(f"    {line}\n" for line in legacy_lines)
    legacy_source = source_path.read_text().replace(
        f"    {practice.SOURCE_COMMENT_GUIDANCE}\n",
        legacy_block,
    )
    assert legacy_source != source_path.read_text()
    legacy_source += extra_source
    source_path.write_text(legacy_source)
    metadata_path = root / practice.WORKSPACE_REL / practice.METADATA_NAME
    metadata_path.write_text(
        json.dumps(
            _legacy_schema4_metadata(metadata, "comments"),
            indent=2,
        )
        + "\n"
    )
    return legacy_source


def _lock_is_available(path: Path) -> bool:
    if not path.is_file():
        return False
    with path.open("r+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return True


def _wait_for_lock_release(path: Path, timeout: float = 3) -> bool:
    deadline = time.monotonic() + timeout
    while not _lock_is_available(path):
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.02)
    return True


def _kill_lock_holder(path: Path) -> None:
    if _lock_is_available(path):
        return
    try:
        pid = int(path.read_text().split()[0])
        os.kill(pid, signal.SIGKILL)
    except OSError, ValueError:
        pass


def _commit_fixture(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
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
        cwd=root,
        check=True,
    )


def _reference_target_only(candidate: str, committed: str, target: str) -> str:
    """Put only the committed target body into an otherwise cold candidate."""

    def selected_function(source: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
        node = next(
            (
                item
                for item in ast.parse(source).body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name == target
            ),
            None,
        )
        assert node is not None
        return node

    reference_node = selected_function(committed)
    implementation = reference_node.body
    if (
        implementation
        and isinstance(implementation[0], ast.Expr)
        and isinstance(implementation[0].value, ast.Constant)
        and isinstance(implementation[0].value.value, str)
    ):
        implementation = implementation[1:]
    assert implementation

    candidate_node = selected_function(candidate)
    cold_body = candidate_node.body[-1]
    assert isinstance(cold_body, ast.Raise)
    reference_lines = committed.splitlines(keepends=True)
    candidate_lines = candidate.splitlines(keepends=True)
    start = implementation[0].lineno - 1
    end = implementation[-1].end_lineno or implementation[-1].lineno
    cold_end = cold_body.end_lineno or cold_body.lineno
    candidate_lines[cold_body.lineno - 1 : cold_end] = reference_lines[start:end]
    return "".join(candidate_lines)


def test_every_core_problem_has_a_real_practice_target() -> None:
    core = {
        (topic, problem) for topic, problems in CORE_42.items() for problem in problems
    }
    assert len(core) == 43
    assert core <= set(PRACTICE_TARGETS)


def test_every_catalog_algorithm_can_start_with_one_explicit_target(
    tmp_path: Path,
) -> None:
    catalog = {
        (path.parent.name, path.stem)
        for path in (REPO_ROOT / "src/algo").glob("*/*.py")
        if path.name != "__init__.py"
    }
    assert len(catalog) == 72
    assert set(PRACTICE_TARGETS) == catalog

    for topic, problem in sorted(catalog):
        source = (REPO_ROOT / f"src/algo/{topic}/{problem}.py").read_text()
        target = PRACTICE_TARGETS[(topic, problem)]
        assert (REPO_ROOT / f"tests/{topic}/test_{problem}.py").is_file()
        assert target in practice._public_symbols(source)
        assert practice._practice_target(topic, problem, source) == target
        candidate = practice.render_candidate(
            source, practice.PARADIGMS["comments"], target
        )
        candidate_tree = ast.parse(candidate)
        visible_definitions = [
            node
            for node in candidate_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        assert visible_definitions[-1].name == target
        assert {node.name for node in visible_definitions[:-1]} <= {
            "GraphNode",
            "ListNode",
            "TreeNode",
        }
        loaded_names = {
            node.id
            for node in ast.walk(candidate_tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        for node in candidate_tree.body:
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                continue
            for alias in node.names:
                assert (alias.asname or alias.name.split(".", 1)[0]) in loaded_names
        assert all(
            ast.get_docstring(node, clean=False) is None
            for definition in visible_definitions
            for node in ast.walk(definition)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        )
        if isinstance(visible_definitions[-1], ast.ClassDef):
            assert all(
                not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                or node.name == "__init__"
                or not node.name.startswith("_")
                for node in visible_definitions[-1].body
            )
        namespace: dict[str, object] = {}
        exec(compile(candidate, f"{topic}/{problem}.py", "exec"), namespace)
        assert target in namespace
        assert "THINKING GATE" not in candidate
        output = tmp_path / topic / f"{problem}.py"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(candidate)

    lint = subprocess.run(
        ["ruff", "check", "--isolated", "--select", "F821", str(tmp_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert lint.returncode == 0, lint.stdout + lint.stderr


def test_candidate_renderer_hides_named_alternates_and_strategy_imports() -> None:
    kth = practice.render_candidate(
        (REPO_ROOT / "src/algo/heaps/kth_largest.py").read_text(),
        practice.PARADIGMS["comments"],
        "find_kth_largest",
    )
    topo = practice.render_candidate(
        (REPO_ROOT / "src/algo/graphs/topological_sort.py").read_text(),
        practice.PARADIGMS["comments"],
        "topological_sort_kahn",
    )
    csp = practice.render_candidate(
        (REPO_ROOT / "src/algo/dp/constraint_satisfaction.py").read_text(),
        practice.PARADIGMS["comments"],
        "CSP",
    )

    assert "heapq" not in kth
    assert "nlargest" not in kth
    assert "dfs" not in topo.lower()
    assert "from collections.abc import Callable, Mapping, Sequence" in csp


@pytest.fixture
def practice_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setitem(practice.PRACTICE_TARGETS, ("arrays", "first"), "solve")
    monkeypatch.setitem(practice.PRACTICE_TARGETS, ("arrays", "second"), "solve")
    monkeypatch.setitem(
        practice.PRACTICE_TARGETS, ("linked_lists", "lru_cache"), "LRUCache"
    )
    _write(tmp_path / ".gitignore", ".challenges/\n")
    _write(tmp_path / "src/algo/__init__.py", "")
    _write(tmp_path / "src/algo/arrays/__init__.py", "")
    for problem in ("first", "second"):
        _write(
            tmp_path / f"src/algo/arrays/{problem}.py",
            SOURCE.format(problem=problem),
        )
        _write(
            tmp_path / f"tests/arrays/test_{problem}.py",
            (
                f"from algo.arrays.{problem} import alternate, solve\n\n\n"
                f"def test_{problem}() -> None:\n"
                "    assert solve([1, 2, 3]) == 6\n\n\n"
                "def test_committed_alternate() -> None:\n"
                "    assert alternate([1, 2, 3]) == 6\n"
            ),
        )
    _write(tmp_path / "src/algo/linked_lists/__init__.py", "")
    _write(tmp_path / "src/algo/linked_lists/lru_cache.py", LRU_SOURCE)
    _write(
        tmp_path / "tests/linked_lists/test_lru_cache.py",
        (
            "from algo.linked_lists.lru_cache import LRUCache\n\n\n"
            "def test_evicts_the_least_recent_key() -> None:\n"
            "    cache = LRUCache(1)\n"
            "    cache.put(1, 10)\n"
            "    cache.put(2, 20)\n"
            "    assert cache.get(1) == -1\n"
            "    assert cache.get(2) == 20\n"
        ),
    )
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
            "-c",
            "core.hooksPath=/dev/null",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=tmp_path,
        check=True,
    )
    return tmp_path


def _workspace_snapshot(workspace: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(workspace): path.read_bytes()
        for path in workspace.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize("paradigm_name", tuple(practice.PARADIGMS))
def test_each_paradigm_is_source_native_without_a_thinking_gate(
    paradigm_name: str,
) -> None:
    paradigm = practice.PARADIGMS[paradigm_name]
    rendered = practice.render_candidate(SOURCE.format(problem="first"), paradigm)

    assert "THINKING GATE" not in rendered
    if paradigm_name == "comments":
        assert practice.SOURCE_COMMENT_GUIDANCE in rendered
        assert not any(seed in rendered for seed in paradigm.seeds)
    else:
        assert all(rendered.count(seed) == 1 for seed in paradigm.seeds)
    assert "secret = sum(values)" not in rendered


def test_guidance_is_inserted_only_at_the_selected_function_stub() -> None:
    source = (
        "def helper() -> None:\n"
        "    raise ValueError('ordinary failure')\n"
        "\n"
        "def solve() -> int:\n"
        "    raise NotImplementedError\n"
    )

    rendered = practice._insert_source_guidance(
        source, "solve", ("# Explain the next choice in your own words.",)
    )

    assert "    raise ValueError('ordinary failure')" in rendered
    assert (
        "def solve() -> int:\n"
        "    # Explain the next choice in your own words.\n"
        "    raise NotImplementedError\n"
    ) in rendered
    assert "THINKING GATE" not in rendered


def test_guidance_uses_the_first_stub_in_a_selected_class() -> None:
    source = (
        "class Solver:\n"
        "    def __init__(self) -> None:\n"
        "        raise NotImplementedError\n"
        "\n"
        "    def run(self) -> int:\n"
        "        raise NotImplementedError\n"
    )

    rendered = practice._insert_source_guidance(
        source, "Solver", ("# Describe how the object will maintain its state.",)
    )

    assert rendered.count("# Describe how the object will maintain its state.") == 1
    assert (
        "    def __init__(self) -> None:\n"
        "        # Describe how the object will maintain its state.\n"
        "        raise NotImplementedError\n"
    ) in rendered


def test_workspace_is_created_without_mutating_tracked_source(
    practice_repo: Path,
) -> None:
    tracked = practice_repo / "src/algo/arrays/first.py"
    before = tracked.read_text()

    metadata, action, archived = practice.prepare_session(
        practice_repo, "reacto", "arrays", "first"
    )

    workspace = practice_repo / ".challenges/workspace"
    candidate = workspace / "first.py"
    assert action == "created"
    assert archived is None
    assert tracked.read_text() == before
    assert candidate.is_file()
    assert "THINKING GATE" not in candidate.read_text()
    assert "secret = sum(values)" not in candidate.read_text()
    assert "return _support(values)" not in candidate.read_text()
    assert "def alternate" not in candidate.read_text()
    assert "from dataclasses import dataclass" not in candidate.read_text()
    assert metadata["schema"] == 5
    assert uuid.UUID(metadata["session_id"]).version == 4
    assert metadata["target"] == "solve"
    assert metadata["source"] == ".challenges/workspace/first.py"
    assert metadata["candidate_test"] == (
        ".challenges/workspace/test_first_candidate.py"
    )
    raw_metadata = json.loads((workspace / practice.METADATA_NAME).read_text())
    assert raw_metadata == metadata
    assert {"lock", "seeds", "pre_code_labels"}.isdisjoint(raw_metadata)
    assert "THINKING GATE" not in json.dumps(raw_metadata)
    assert (
        "# from algo.arrays.first import solve"
        in (workspace / "test_first_candidate.py").read_text()
    )
    assert (workspace / "practice_plugin.py").is_file()
    assert (workspace / "repl.py").is_file()
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=practice_repo,
        text=True,
        capture_output=True,
        check=True,
    )
    assert status.stdout == ""


def test_present_reads_committed_statement_without_creating_workspace(
    practice_repo: Path,
) -> None:
    tracked = practice_repo / "src/algo/arrays/first.py"
    tracked.write_text('"""Working-tree notes must not leak."""\n')

    statement = practice.present_problem(practice_repo, "arrays", "first")

    assert "arrays / first" in statement
    assert "Problem:" in statement
    assert "Approach:" not in statement
    assert "Working-tree notes" not in statement
    assert not (practice_repo / ".challenges/workspace").exists()


def test_open_target_creates_neutral_prepared_candidate_surface(
    practice_repo: Path,
) -> None:
    tracked = practice_repo / "src/algo/arrays/first.py"
    before = tracked.read_text()

    metadata = practice.prepare_open_target(practice_repo, "arrays", "first")

    candidate = practice_repo / str(metadata["source"])
    assert metadata["prepared_only"] is True
    assert metadata["paradigm"] == "prepared"
    assert metadata["candidate_test"] == (
        ".challenges/workspace/test_first_candidate.py"
    )
    assert "THINKING GATE" not in candidate.read_text()
    assert practice.SOURCE_COMMENT_GUIDANCE in candidate.read_text()
    assert not any(
        label in candidate.read_text()
        for label in ("RESTATE:", "REPEAT:", "CLARIFY:", "UNDERSTAND:")
    )
    assert "secret = _support(values)" not in candidate.read_text()
    assert "def alternate" not in candidate.read_text()
    assert tracked.read_text() == before


def test_legacy_pristine_prepared_tabs_use_the_legacy_render_for_disposition(
    practice_repo: Path,
) -> None:
    prepared = practice.prepare_open_target(practice_repo, "arrays", "first")
    legacy_source = _rewrite_as_legacy_prepared(practice_repo, prepared)

    next_prepared = practice.prepare_open_target(practice_repo, "arrays", "second")

    assert next_prepared["problem"] == "second"
    archives = list((practice_repo / practice.HISTORY_REL).iterdir())
    assert len(archives) == 1
    archived_source = (archives[0] / "first.py").read_text()
    assert archived_source == legacy_source.replace(
        f"    {practice.LEGACY_SCHEMA4_LOCK}\n", ""
    )
    archived_metadata = json.loads((archives[0] / practice.METADATA_NAME).read_text())
    assert archived_metadata["schema"] == practice.METADATA_SCHEMA
    assert {"lock", "seeds", "pre_code_labels"}.isdisjoint(archived_metadata)


def test_legacy_edited_prepared_tabs_are_preserved_and_block_replacement(
    practice_repo: Path,
) -> None:
    prepared = practice.prepare_open_target(practice_repo, "arrays", "first")
    _rewrite_as_legacy_prepared(
        practice_repo,
        prepared,
        extra_source="\n# Keep this candidate-authored note.\n",
    )

    with pytest.raises(practice.PracticeError, match="contain unclosed work"):
        practice.prepare_open_target(practice_repo, "arrays", "second")

    candidate = practice_repo / str(prepared["source"])
    assert "Keep this candidate-authored note" in candidate.read_text()
    assert practice.LEGACY_SCHEMA4_LOCK not in candidate.read_text()
    persisted = json.loads(
        (practice_repo / practice.WORKSPACE_REL / practice.METADATA_NAME).read_text()
    )
    assert persisted["schema"] == practice.METADATA_SCHEMA
    assert not (practice_repo / practice.HISTORY_REL).exists()


def test_prepared_tabs_promote_to_comments_without_modification(
    practice_repo: Path,
) -> None:
    prepared = practice.prepare_open_target(practice_repo, "arrays", "first")
    candidate = practice_repo / str(prepared["source"])
    candidate.write_text(candidate.read_text() + "\n# Keep this reading note.\n")
    before = _workspace_snapshot(practice_repo / practice.WORKSPACE_REL)

    active, action, archived = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )

    assert action == "resumed"
    assert archived is None
    assert "prepared_only" not in active
    after = _workspace_snapshot(practice_repo / practice.WORKSPACE_REL)
    assert after[Path("first.py")] == before[Path("first.py")]
    assert not (practice_repo / practice.HISTORY_REL).exists()


@pytest.mark.parametrize("paradigm_name", tuple(practice.PARADIGMS))
@pytest.mark.parametrize("dirty", [False, True])
def test_prepared_tabs_activate_any_mode_without_discarding_candidate_files(
    practice_repo: Path,
    paradigm_name: str,
    dirty: bool,
) -> None:
    prepared = practice.prepare_open_target(practice_repo, "arrays", "first")
    workspace = practice_repo / practice.WORKSPACE_REL
    candidate = practice_repo / str(prepared["source"])
    candidate_test = practice_repo / str(prepared["candidate_test"])
    if dirty:
        candidate.write_text(candidate.read_text() + "\n# Keep this reading note.\n")
        candidate_test.write_text(
            candidate_test.read_text() + "\n# Keep this candidate test note.\n"
        )
    scratch = workspace / "scratch.txt"
    scratch.write_text("candidate notes\n")
    source_before = candidate.read_bytes()
    test_before = candidate_test.read_bytes()
    scratch_before = scratch.read_bytes()

    active, action, archived = practice.prepare_session(
        practice_repo, paradigm_name, "arrays", "first"
    )

    assert action == "resumed"
    assert archived is None
    assert active["paradigm"] == paradigm_name
    assert "prepared_only" not in active
    assert candidate.read_bytes() == source_before
    assert candidate_test.read_bytes() == test_before
    assert scratch.read_bytes() == scratch_before
    assert not (practice_repo / practice.HISTORY_REL).exists()


def test_presented_prepared_tabs_allow_the_next_target_and_archive_edits(
    practice_repo: Path,
) -> None:
    prepared = practice.prepare_open_target(practice_repo, "arrays", "first")
    candidate = practice_repo / str(prepared["source"])
    candidate.write_text(candidate.read_text() + "\n# Preserve this talk note.\n")

    assert (
        practice.finish_non_editor(
            practice_repo,
            "arrays",
            "first",
            "talk arrays/first C1 L1 A1 R1 P1 h0 trace the edge",
        )
        == 0
    )
    assert "presented_at" in practice.current_metadata(practice_repo)

    next_prepared = practice.prepare_open_target(practice_repo, "arrays", "second")

    assert next_prepared["problem"] == "second"
    assert next_prepared["prepared_only"] is True
    archives = list((practice_repo / practice.HISTORY_REL).iterdir())
    assert len(archives) == 1
    assert "Preserve this talk note" in (archives[0] / "first.py").read_text()


def test_presented_tabs_promote_to_comments_for_same_target(
    practice_repo: Path,
) -> None:
    prepared = practice.prepare_open_target(practice_repo, "arrays", "first")
    candidate = practice_repo / str(prepared["source"])
    candidate.write_text(candidate.read_text() + "\n# Keep this talk note.\n")
    practice.finish_non_editor(
        practice_repo,
        "arrays",
        "first",
        "talk arrays/first C1 L1 A1 R1 P1 h0 trace the edge",
    )

    active, action, archived = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )

    assert action == "resumed"
    assert archived is None
    assert "prepared_only" not in active
    assert "presented_at" not in active
    assert "Keep this talk note" in candidate.read_text()


def test_open_target_reopens_matching_rep_without_modification(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "reacto", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(candidate.read_text() + "\n# Keep this reasoning.\n")
    workspace = practice_repo / practice.WORKSPACE_REL
    before = _workspace_snapshot(workspace)

    reopened = practice.prepare_open_target(practice_repo, "arrays", "first")

    after = _workspace_snapshot(workspace)
    assert reopened == metadata
    assert reopened["paradigm"] == "reacto"
    assert after == before


def test_open_target_refuses_a_different_unfinished_rep_without_mutation(
    practice_repo: Path,
) -> None:
    practice.prepare_session(practice_repo, "umpire", "arrays", "first")
    workspace = practice_repo / practice.WORKSPACE_REL
    before = _workspace_snapshot(workspace)

    with pytest.raises(practice.PracticeError, match="unfinished editor rep"):
        practice.prepare_open_target(practice_repo, "arrays", "second")

    after = _workspace_snapshot(workspace)
    assert after == before
    assert practice.current_metadata(practice_repo)["problem"] == "first"


@pytest.mark.parametrize(
    ("topic", "problem"),
    [("arrays", None), (None, "first")],
)
def test_open_target_rejects_a_partial_pair_before_creating_state(
    practice_repo: Path,
    topic: str | None,
    problem: str | None,
) -> None:
    with pytest.raises(practice.PracticeError, match="NEXT: run `just catalog"):
        practice.prepare_open_target(practice_repo, topic, problem)

    assert not (practice_repo / ".challenges").exists()


@pytest.mark.parametrize(
    ("topic", "problem"),
    [("../arrays", "first"), ("arrays", "../first")],
)
def test_open_target_rejects_unconfined_names_before_creating_state(
    practice_repo: Path,
    topic: str,
    problem: str,
) -> None:
    with pytest.raises(practice.PracticeError, match="lowercase Python identifiers"):
        practice.prepare_open_target(practice_repo, topic, problem)

    assert not (practice_repo / ".challenges").exists()


def test_same_target_different_paradigm_still_requires_finish(
    practice_repo: Path,
) -> None:
    active, _, _ = practice.prepare_session(practice_repo, "reacto", "arrays", "first")
    workspace = practice_repo / practice.WORKSPACE_REL
    before = _workspace_snapshot(workspace)

    with pytest.raises(practice.PracticeError, match="unfinished editor rep"):
        practice.prepare_session(practice_repo, "clarp", "arrays", "first")

    assert practice.current_metadata(practice_repo) == active
    assert _workspace_snapshot(workspace) == before


def test_problem_selection_rejects_half_an_explicit_pair(practice_repo: Path) -> None:
    with pytest.raises(practice.PracticeError, match="NEXT: run `just catalog"):
        practice.select_problem(practice_repo, "arrays", None)


def test_unknown_selection_is_rejected_before_file_access_with_matches(
    practice_repo: Path,
) -> None:
    with pytest.raises(practice.PracticeError) as raised:
        practice.prepare_session(practice_repo, "comments", "strings", "anagram")

    message = str(raised.value)
    assert "MATCH: strings/valid_anagram" in message
    assert "MATCH: arrays/group_anagrams" in message
    assert 'NEXT: run `just catalog "anagram"`' in message
    assert "missing reference tests" not in message
    assert not (practice_repo / ".challenges").exists()


def test_problem_selection_draws_first_due_and_rejects_empty_queue(
    practice_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        practice, "ranked_queue", lambda _path: [(10, "arrays", "first")]
    )
    assert practice.select_problem(practice_repo) == ("arrays", "first")

    monkeypatch.setattr(practice, "ranked_queue", lambda _path: [])
    with pytest.raises(practice.PracticeError, match="queue is empty"):
        practice.select_problem(practice_repo)


def test_reference_reads_committed_solution_without_restoring_tracked_file(
    practice_repo: Path,
) -> None:
    tracked = practice_repo / "src/algo/arrays/first.py"
    tracked.write_text('"""Candidate work in progress."""\n')

    reference = practice.reference_solution(practice_repo, "arrays", "first")

    assert "secret = _support(values)" in reference
    assert "Candidate work in progress" not in reference
    assert tracked.read_text() == '"""Candidate work in progress."""\n'


def test_study_snapshot_uses_committed_source_and_tests_without_starting_rep(
    practice_repo: Path,
) -> None:
    tracked_source = practice_repo / "src/algo/arrays/first.py"
    tracked_test = practice_repo / "tests/arrays/test_first.py"
    tracked_source.write_text('"""Dirty source must not leak."""\n')
    tracked_test.write_text("# Dirty tests must not leak.\n")

    manifest = practice.prepare_study_snapshot(practice_repo, "arrays", "first")

    source = practice_repo / str(manifest["source"])
    test = practice_repo / str(manifest["test"])
    metadata = source.parent / practice.STUDY_METADATA_NAME
    assert "secret = _support(values)" in source.read_text()
    assert "Dirty source" not in source.read_text()
    assert "test_committed_alternate" in test.read_text()
    assert "Dirty tests" not in test.read_text()
    assert manifest["source_origin"] == "src/algo/arrays/first.py"
    assert manifest["test_origin"] == "tests/arrays/test_first.py"
    assert manifest["source_digest"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert manifest["test_digest"] == hashlib.sha256(test.read_bytes()).hexdigest()
    assert json.loads(metadata.read_text()) == manifest
    assert source.stat().st_mode & 0o222 == 0
    assert test.stat().st_mode & 0o222 == 0
    assert metadata.stat().st_mode & 0o222 == 0
    assert not (practice_repo / practice.WORKSPACE_REL).exists()
    state_names = {path.name for path in (practice_repo / practice.STATE_REL).iterdir()}
    assert state_names == {practice.LOCK_REL.name, practice.STUDY_REL.name}


def test_study_snapshot_is_idempotent_for_one_revision(
    practice_repo: Path,
) -> None:
    first = practice.prepare_study_snapshot(practice_repo, "arrays", "first")
    snapshot = (practice_repo / str(first["source"])).parent
    before = _workspace_snapshot(snapshot)
    for path in snapshot.iterdir():
        path.chmod(0o644)

    second = practice.prepare_study_snapshot(practice_repo, "arrays", "first")

    assert second == first
    assert _workspace_snapshot(snapshot) == before
    assert all(path.stat().st_mode & 0o222 == 0 for path in snapshot.iterdir())
    revision_dirs = list(
        (practice_repo / practice.STUDY_REL / "arrays" / "first").iterdir()
    )
    assert revision_dirs == [snapshot]


def test_study_snapshots_for_different_problems_coexist(
    practice_repo: Path,
) -> None:
    first = practice.prepare_study_snapshot(practice_repo, "arrays", "first")
    lru = practice.prepare_study_snapshot(practice_repo, "linked_lists", "lru_cache")

    first_source = practice_repo / str(first["source"])
    lru_source = practice_repo / str(lru["source"])
    assert first_source.is_file()
    assert lru_source.is_file()
    assert first_source.parent != lru_source.parent


@pytest.mark.parametrize("drift", ["contents", "extra", "missing", "symlink"])
def test_practice_study_regenerates_drifted_generated_snapshot(
    practice_repo: Path,
    drift: str,
) -> None:
    manifest = practice.prepare_study_snapshot(practice_repo, "arrays", "first")
    snapshot = (practice_repo / str(manifest["source"])).parent
    source = practice_repo / str(manifest["source"])

    if drift == "contents":
        source.chmod(0o644)
        source.write_text("# changed\n")
    elif drift == "extra":
        (snapshot / "notes.txt").write_text("not part of the snapshot\n")
    elif drift == "missing":
        source.unlink()
    else:
        source.unlink()
        source.symlink_to(practice_repo / "src/algo/arrays/first.py")

    repaired = practice.prepare_study_snapshot(practice_repo, "arrays", "first")

    repaired_source = practice_repo / str(repaired["source"])
    repaired_snapshot = repaired_source.parent
    assert repaired == manifest
    assert "secret = _support(values)" in repaired_source.read_text()
    assert {path.name for path in repaired_snapshot.iterdir()} == {
        "first.py",
        "test_first.py",
        practice.STUDY_METADATA_NAME,
    }
    assert all(path.stat().st_mode & 0o222 == 0 for path in repaired_snapshot.iterdir())
    recoveries = list(repaired_snapshot.parent.glob(".recovery-*"))
    assert len(recoveries) == 1
    if drift == "extra":
        assert (recoveries[0] / "notes.txt").read_text() == (
            "not part of the snapshot\n"
        )


def test_study_open_revalidates_snapshot_after_prepare(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = practice.prepare_study_snapshot(practice_repo, "arrays", "first")
    source = practice_repo / str(manifest["source"])
    source.unlink()
    source.symlink_to(practice_repo / "src/algo/arrays/first.py")
    real_run = practice.subprocess.run

    def reject_code(
        argv: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if argv and argv[0] == "code":
            pytest.fail("must not invoke code")
        return cast("subprocess.CompletedProcess[str]", real_run(argv, **kwargs))

    monkeypatch.setattr(
        practice.subprocess,
        "run",
        reject_code,
    )

    with pytest.raises(practice.PracticeError, match="snapshot drifted"):
        practice.open_study_snapshot(practice_repo, manifest)

    repaired = practice.prepare_study_snapshot(practice_repo, "arrays", "first")
    assert not (practice_repo / str(repaired["source"])).is_symlink()
    assert (
        "secret = _support(values)"
        in (practice_repo / str(repaired["source"])).read_text()
    )


def test_study_rejects_self_consistent_manifest_and_source_tampering(
    practice_repo: Path,
) -> None:
    manifest = practice.prepare_study_snapshot(practice_repo, "arrays", "first")
    source = practice_repo / str(manifest["source"])
    metadata_path = source.parent / practice.STUDY_METADATA_NAME
    false_source = "# internally consistent, but not committed\n"
    source.chmod(0o644)
    source.write_text(false_source)
    tampered = dict(manifest)
    tampered["source_digest"] = hashlib.sha256(false_source.encode()).hexdigest()
    metadata_path.chmod(0o644)
    metadata_path.write_text(json.dumps(tampered, indent=2) + "\n")

    with pytest.raises(practice.PracticeError, match="snapshot drifted"):
        practice.open_study_snapshot(practice_repo, tampered)

    repaired = practice.prepare_study_snapshot(practice_repo, "arrays", "first")
    assert (
        "secret = _support(values)"
        in (practice_repo / str(repaired["source"])).read_text()
    )
    assert repaired == manifest


def test_study_open_rejects_hardlinks_without_chmodding_tracked_source(
    practice_repo: Path,
) -> None:
    manifest = practice.prepare_study_snapshot(practice_repo, "arrays", "first")
    snapshot_source = practice_repo / str(manifest["source"])
    tracked_source = practice_repo / "src/algo/arrays/first.py"
    tracked_mode = tracked_source.stat().st_mode
    snapshot_source.unlink()
    os.link(tracked_source, snapshot_source)

    with pytest.raises(practice.PracticeError, match="snapshot drifted"):
        practice.open_study_snapshot(practice_repo, manifest)

    assert tracked_source.stat().st_mode == tracked_mode
    repaired = practice.prepare_study_snapshot(practice_repo, "arrays", "first")
    assert (practice_repo / str(repaired["source"])).stat().st_nlink == 1


def test_new_head_creates_a_new_study_snapshot_without_replacing_old_one(
    practice_repo: Path,
) -> None:
    first = practice.prepare_study_snapshot(practice_repo, "arrays", "first")
    first_source = practice_repo / str(first["source"])
    first_bytes = first_source.read_bytes()
    tracked = practice_repo / "src/algo/arrays/first.py"
    tracked.write_text(
        tracked.read_text().replace("return secret", "return secret + 0")
    )
    subprocess.run(
        ["git", "add", str(tracked.relative_to(practice_repo))],
        cwd=practice_repo,
        check=True,
    )
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
            "new reference revision",
        ],
        cwd=practice_repo,
        check=True,
    )

    second = practice.prepare_study_snapshot(practice_repo, "arrays", "first")

    assert second["revision"] != first["revision"]
    assert second["source"] != first["source"]
    assert "return secret + 0" in (practice_repo / str(second["source"])).read_text()
    assert first_source.read_bytes() == first_bytes


def test_study_snapshot_retains_only_three_newest_committed_revisions(
    practice_repo: Path,
) -> None:
    manifests = [practice.prepare_study_snapshot(practice_repo, "arrays", "first")]
    tracked = practice_repo / "src/algo/arrays/first.py"
    for revision in range(1, 5):
        tracked.write_text(tracked.read_text() + f"\n# revision {revision}\n")
        subprocess.run(["git", "add", "."], cwd=practice_repo, check=True)
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
                f"study revision {revision}",
            ],
            cwd=practice_repo,
            check=True,
        )
        manifests.append(
            practice.prepare_study_snapshot(practice_repo, "arrays", "first")
        )

    parent = practice_repo / practice.STUDY_REL / "arrays" / "first"
    retained = {
        path.name
        for path in parent.iterdir()
        if practice.GIT_OBJECT_ID.fullmatch(path.name)
    }
    assert retained == {str(manifest["revision"]) for manifest in manifests[-3:]}
    current = manifests[-1]
    assert (practice_repo / str(current["source"])).is_file()
    assert "# revision 4" in (practice_repo / str(current["source"])).read_text()
    assert not (practice_repo / str(manifests[0]["source"])).exists()


def test_study_snapshot_cleans_only_abandoned_generated_temp_directories(
    practice_repo: Path,
) -> None:
    manifest = practice.prepare_study_snapshot(practice_repo, "arrays", "first")
    parent = (practice_repo / str(manifest["source"])).parent.parent
    abandoned = parent / f".{manifest['revision']}-deadbeef.tmp"
    human_named = parent / f".{manifest['revision']}-human-notes.tmp"
    unrelated = parent / ".keep-me.tmp"
    abandoned.mkdir()
    (abandoned / "partial").write_text("generated")
    human_named.mkdir()
    (human_named / "note").write_text("not a tempfile name")
    unrelated.mkdir()
    (unrelated / "note").write_text("not a generated snapshot")

    resumed = practice.prepare_study_snapshot(practice_repo, "arrays", "first")

    assert resumed == manifest
    assert not abandoned.exists()
    assert (human_named / "note").read_text() == "not a tempfile name"
    assert (unrelated / "note").read_text() == "not a generated snapshot"
    assert (practice_repo / str(resumed["source"])).is_file()


def test_study_snapshot_retains_three_newest_drift_recoveries(
    practice_repo: Path,
) -> None:
    manifest = practice.prepare_study_snapshot(practice_repo, "arrays", "first")
    source = practice_repo / str(manifest["source"])
    parent = source.parent.parent
    previous: set[Path] = set()
    for number in range(1, 5):
        source.chmod(0o644)
        source.write_text(f"# drift {number}\n")
        practice.prepare_study_snapshot(practice_repo, "arrays", "first")
        recoveries = set(parent.glob(".recovery-*"))
        created = recoveries - previous
        assert len(created) == 1
        newest = created.pop()
        os.utime(newest, ns=(number, number))
        previous = recoveries

    recovery_paths = list(parent.glob(".recovery-*"))
    recovered_text = {
        (recovery / "first.py").read_text() for recovery in recovery_paths
    }
    assert len(recovery_paths) == practice.MAX_STUDY_RECOVERIES
    assert "# drift 4\n" in recovered_text
    assert "# drift 1\n" not in recovered_text
    assert "secret = _support(values)" in source.read_text()


def test_study_snapshot_reports_a_missing_committed_reference_test(
    practice_repo: Path,
) -> None:
    reference_test = practice_repo / "tests/arrays/test_first.py"
    reference_test.unlink()
    subprocess.run(["git", "add", "."], cwd=practice_repo, check=True)
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
            "remove reference test",
        ],
        cwd=practice_repo,
        check=True,
    )

    with pytest.raises(
        practice.PracticeError,
        match=r"cannot load committed tests/arrays/test_first\.py",
    ):
        practice.prepare_study_snapshot(practice_repo, "arrays", "first")

    assert not (practice_repo / practice.STUDY_REL).exists()


def test_study_snapshot_reads_source_and_tests_from_one_captured_revision(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = practice._committed_source_at
    calls = 0

    def advance_head_after_source(root: Path, revision: str, relative: Path) -> str:
        nonlocal calls
        calls += 1
        text = cast("str", original(root, revision, relative))
        if calls == 1:
            tracked_test = root / "tests/arrays/test_first.py"
            tracked_test.write_text(tracked_test.read_text() + "\n# newer HEAD\n")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
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
                    "advance during snapshot",
                ],
                cwd=root,
                check=True,
            )
        return text

    old_revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=practice_repo,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    monkeypatch.setattr(practice, "_committed_source_at", advance_head_after_source)

    manifest = practice.prepare_study_snapshot(practice_repo, "arrays", "first")

    assert calls == 2
    assert manifest["revision"] == old_revision
    assert "# newer HEAD" not in (practice_repo / str(manifest["test"])).read_text()


def test_study_snapshot_opens_only_detached_read_only_paths(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest = practice.prepare_study_snapshot(practice_repo, "arrays", "first")
    calls: list[tuple[list[str], Path, bool, int]] = []
    real_run = practice.subprocess.run

    def fake_run(args: list[str], **kwargs: Any) -> Any:
        if args[0] == "git":
            return real_run(args, **kwargs)
        cwd = cast("Path", kwargs["cwd"])
        check = cast("bool", kwargs["check"])
        timeout = cast("int", kwargs["timeout"])
        calls.append((args, cwd, check, timeout))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(practice.shutil, "which", lambda _name: "/mock/code")
    monkeypatch.setattr(practice.subprocess, "run", fake_run)

    assert practice.open_study_snapshot(practice_repo, manifest)

    source = str(manifest["source"])
    test = str(manifest["test"])
    source_text = (practice_repo / source).read_text()
    expected_line = practice._study_cursor_line(
        source_text, practice.PRACTICE_TARGETS[("arrays", "first")]
    )
    assert calls == [
        (
            [
                "/mock/code",
                "--reuse-window",
                test,
                "--goto",
                f"{source}:{expected_line}",
            ],
            practice_repo,
            False,
            practice.EDITOR_OPEN_TIMEOUT_SECONDS,
        )
    ]
    args = calls[0][0]
    assert all("src/algo/" not in arg for arg in args)
    assert all("tests/arrays/" not in arg for arg in args)
    assert source.startswith(".challenges/study/")
    assert test.startswith(".challenges/study/")
    output = capsys.readouterr().out
    assert f"OPENED: {source}:{expected_line}" in output
    assert "STATE: STUDY" in output
    assert f"STUDY_SOURCE: {source}" in output
    assert f"STUDY_TEST: {test}" in output
    assert "FOCUS: SOURCE" in output
    assert "IMPLEMENT: just practice-start comments arrays first" in output
    assert "TESTS_FIRST: just practice-start-tests arrays first" in output
    assert "implement it or write tests first" in output


def test_study_snapshot_opens_a_class_target_at_its_definition(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = practice.prepare_study_snapshot(
        practice_repo, "linked_lists", "lru_cache"
    )
    calls: list[list[str]] = []
    real_run = practice.subprocess.run

    def fake_run(args: list[str], **kwargs: Any) -> Any:
        if args[0] == "git":
            return real_run(args, **kwargs)
        calls.append(args)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(practice.shutil, "which", lambda _name: "/mock/code")
    monkeypatch.setattr(practice.subprocess, "run", fake_run)

    assert practice.open_study_snapshot(practice_repo, manifest)

    source = practice_repo / str(manifest["source"])
    expected_line = next(
        number
        for number, line in enumerate(source.read_text().splitlines(), start=1)
        if line == "class LRUCache:"
    )
    assert "OrderedDict" in source.read_text()
    assert (
        "test_evicts_the_least_recent_key"
        in (practice_repo / str(manifest["test"])).read_text()
    )
    assert calls[0][-1] == f"{manifest['source']}:{expected_line}"


@pytest.mark.parametrize("failure", ["missing", "timeout", "nonzero"])
def test_study_open_failures_emit_the_complete_safe_state(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    manifest = practice.prepare_study_snapshot(practice_repo, "arrays", "first")
    real_run = practice.subprocess.run
    monkeypatch.setattr(
        practice.shutil,
        "which",
        lambda _name: None if failure == "missing" else "/mock/code",
    )

    def fail_run(args: list[str], **kwargs: Any) -> Any:
        if args[0] == "git":
            return real_run(args, **kwargs)
        timeout = cast("int", kwargs["timeout"])
        if failure == "timeout":
            raise subprocess.TimeoutExpired("code", timeout)
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr(practice.subprocess, "run", fail_run)

    assert not practice.open_study_snapshot(practice_repo, manifest)

    output = capsys.readouterr().out
    assert "OPEN_FAILED:" in output
    assert "STATE: STUDY" not in output
    assert "STUDY_SOURCE:" not in output
    assert "STUDY_TEST:" not in output
    assert "REVISION:" not in output
    assert "FOCUS:" not in output
    assert "IMPLEMENT:" not in output
    assert "TESTS_FIRST:" not in output
    assert "NEXT: Restore the code CLI, then run just practice-study arrays first." in (
        output
    )
    assert "src/algo/" not in output
    assert "tests/arrays/" not in output


def test_study_then_implementation_starts_from_a_cold_candidate(
    practice_repo: Path,
) -> None:
    study = practice.prepare_study_snapshot(practice_repo, "arrays", "first")
    study_source = practice_repo / str(study["source"])
    study_before = study_source.read_bytes()

    metadata, action, archived = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )

    candidate = practice_repo / str(metadata["source"])
    assert action == "created"
    assert archived is None
    assert "raise NotImplementedError" in candidate.read_text()
    assert "secret = _support(values)" not in candidate.read_text()
    assert "def alternate" not in candidate.read_text()
    assert study_source.read_bytes() == study_before


def test_lru_study_then_implementation_hides_ordered_dict_bodies(
    practice_repo: Path,
) -> None:
    study = practice.prepare_study_snapshot(practice_repo, "linked_lists", "lru_cache")
    metadata, action, _ = practice.prepare_session(
        practice_repo,
        "comments",
        "linked_lists",
        "lru_cache",
    )

    studied = (practice_repo / str(study["source"])).read_text()
    candidate = (practice_repo / str(metadata["source"])).read_text()
    assert action == "created"
    assert "OrderedDict" in studied
    assert "class LRUCache" in candidate
    assert "OrderedDict" not in candidate
    assert candidate.count("raise NotImplementedError") == 3


def test_study_to_candidate_iteration_runs_next_and_focused_tests(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    practice.prepare_study_snapshot(practice_repo, "arrays", "first")
    metadata, action, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        candidate.read_text()
        .replace(
            practice.SOURCE_COMMENT_GUIDANCE,
            "# Add every input value; an empty input should return zero.",
        )
        .replace("raise NotImplementedError", "return sum(values)")
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "from algo.arrays.first import solve\n\n\n"
        "def test_candidate_empty_input() -> None:\n"
        "    assert solve([]) == 0\n"
    )

    assert action == "created"
    assert not practice._is_prepared(metadata)
    monkeypatch.setattr(practice, "ROOT", practice_repo)
    monkeypatch.setattr(sys, "argv", ["practice_workspace.py", "next"])
    assert practice.main() == 0
    assert "STATE: REFLECT" in capsys.readouterr().out

    monkeypatch.setattr(sys, "argv", ["practice_workspace.py", "test"])
    assert practice.main() == 0


def test_issue_99_prepared_lru_study_activation_runs_candidate_tests(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = practice.prepare_open_target(practice_repo, "linked_lists", "lru_cache")
    practice.prepare_study_snapshot(practice_repo, "linked_lists", "lru_cache")

    metadata, action, archived = practice.prepare_session(
        practice_repo,
        "comments",
        "linked_lists",
        "lru_cache",
    )

    assert practice._is_prepared(prepared)
    assert action == "resumed"
    assert archived is None
    assert not practice._is_prepared(metadata)
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        '"""Candidate-owned LRU implementation."""\n\n'
        "from collections import OrderedDict\n\n\n"
        "class LRUCache:\n"
        "    def __init__(self, capacity: int) -> None:\n"
        "        # Keep the least recent key at the front.\n"
        "        self.capacity = capacity\n"
        "        self.cache: OrderedDict[int, int] = OrderedDict()\n\n"
        "    def get(self, key: int) -> int:\n"
        "        if key not in self.cache:\n"
        "            return -1\n"
        "        self.cache.move_to_end(key)\n"
        "        return self.cache[key]\n\n"
        "    def put(self, key: int, value: int) -> None:\n"
        "        self.cache[key] = value\n"
        "        self.cache.move_to_end(key)\n"
        "        if len(self.cache) > self.capacity:\n"
        "            self.cache.popitem(last=False)\n"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "from algo.linked_lists.lru_cache import LRUCache\n\n\n"
        "def test_candidate_refreshes_a_read() -> None:\n"
        "    cache = LRUCache(2)\n"
        "    cache.put(1, 10)\n"
        "    cache.put(2, 20)\n"
        "    assert cache.get(1) == 10\n"
        "    cache.put(3, 30)\n"
        "    assert cache.get(2) == -1\n"
    )

    monkeypatch.setattr(practice, "ROOT", practice_repo)
    monkeypatch.setattr(sys, "argv", ["practice_workspace.py", "test"])
    assert practice.main() == 0
    assert practice._test_receipt_status(practice_repo, metadata) == "passed"


def test_study_refuses_to_expose_solution_during_an_unfinished_rep(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(candidate.read_text() + "\n# Preserve this work.\n")

    with pytest.raises(practice.PracticeError, match="unfinished editor rep"):
        practice.prepare_study_snapshot(practice_repo, "arrays", "first")

    assert "Preserve this work" in candidate.read_text()
    assert not (practice_repo / practice.STUDY_REL).exists()


def test_study_open_rechecks_for_a_rep_started_after_snapshot_creation(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = practice.prepare_study_snapshot(practice_repo, "arrays", "first")
    practice.prepare_session(practice_repo, "comments", "arrays", "first")
    monkeypatch.setattr(
        practice,
        "_open_study_snapshot_locked",
        lambda _root, _manifest: pytest.fail("must not expose the snapshot"),
    )

    with pytest.raises(practice.PracticeError, match="unfinished editor rep"):
        practice.open_study_snapshot(practice_repo, manifest)


def test_study_opens_a_detached_view_beside_issue_99s_pristine_prepared_tabs(
    practice_repo: Path,
) -> None:
    prepared = practice.prepare_open_target(practice_repo, "arrays", "first")

    manifest = practice.prepare_study_snapshot(practice_repo, "arrays", "first")

    assert practice._is_prepared(prepared)
    assert (
        "raise NotImplementedError"
        in (practice_repo / str(prepared["source"])).read_text()
    )
    assert (
        "secret = _support(values)"
        in (practice_repo / str(manifest["source"])).read_text()
    )


def test_study_blocks_an_active_talk_or_board_presentation(
    practice_repo: Path,
) -> None:
    prepared = practice.prepare_open_target(practice_repo, "arrays", "first")
    active = practice.mark_presentation_started(practice_repo, prepared)

    with pytest.raises(
        practice.PracticeError,
        match="active non-editor rep",
    ) as exc_info:
        practice.prepare_study_snapshot(practice_repo, "arrays", "first")

    assert "just interview arrays first" in str(exc_info.value)
    assert practice._is_presentation_active(active)
    assert not (practice_repo / practice.STUDY_REL).exists()


def test_study_blocks_edited_prepared_candidate_work_with_an_activation_path(
    practice_repo: Path,
) -> None:
    prepared = practice.prepare_open_target(practice_repo, "arrays", "first")
    candidate = practice_repo / str(prepared["source"])
    candidate.write_text(candidate.read_text() + "\n# Work I want to keep.\n")

    with pytest.raises(
        practice.PracticeError,
        match="prepared candidate work exists",
    ) as error:
        practice.prepare_study_snapshot(practice_repo, "arrays", "first")

    assert "just practice-start comments arrays first" in str(error.value)
    assert "Work I want to keep" in candidate.read_text()


def test_study_allows_a_completed_non_editor_presentation(
    practice_repo: Path,
) -> None:
    practice.prepare_open_target(practice_repo, "arrays", "first")
    assert (
        practice.finish_non_editor(
            practice_repo,
            "arrays",
            "first",
            "talk arrays/first C2 L2 A1 R1 P1 h0 trace before optimizing",
        )
        == 0
    )

    manifest = practice.prepare_study_snapshot(practice_repo, "arrays", "first")

    assert manifest["topic"] == "arrays"
    assert manifest["problem"] == "first"


def test_representing_a_completed_pair_blocks_study_until_the_new_close(
    practice_repo: Path,
) -> None:
    prepared = practice.prepare_open_target(practice_repo, "arrays", "first")
    practice.mark_presentation_started(practice_repo, prepared)
    assert (
        practice.finish_non_editor(
            practice_repo,
            "arrays",
            "first",
            "talk arrays/first C2 L2 A1 R1 P1 h0 trace before optimizing",
        )
        == 0
    )
    completed = practice.current_metadata(practice_repo)
    assert practice._is_presented(completed)

    reopened = practice.prepare_open_target(practice_repo, "arrays", "first")
    active = practice.mark_presentation_started(practice_repo, reopened)

    assert practice._is_presentation_active(active)
    with pytest.raises(practice.PracticeError, match="active non-editor rep"):
        practice.prepare_study_snapshot(practice_repo, "arrays", "first")


def test_same_session_resumes_without_overwriting_candidate_work(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "reacto", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate_test = practice_repo / str(metadata["candidate_test"])
    candidate.write_text(candidate.read_text() + "\n# candidate reasoning survives\n")
    candidate_test.write_text(
        candidate_test.read_text() + "\n# candidate test survives\n"
    )

    resumed, action, archived = practice.prepare_session(
        practice_repo, "reacto", "arrays", "first"
    )

    assert action == "resumed"
    assert archived is None
    assert resumed == metadata
    assert "candidate reasoning survives" in candidate.read_text()
    assert "candidate test survives" in candidate_test.read_text()


def _complete_session(root: Path, metadata: dict[str, Any]) -> None:
    candidate = root / str(metadata["source"])
    candidate.write_text(
        candidate.read_text().replace(
            "raise NotImplementedError",
            "return sum(values)  # Sum once, then return the total.",
        )
    )
    (root / str(metadata["candidate_test"])).write_text(
        "def test_candidate_example() -> None:\n    assert True\n"
    )
    practice._write_test_receipt(
        root,
        metadata,
        "passed",
        practice._test_input_digests(root, metadata),
    )


def _implement_with_candidate_test(
    root: Path,
    metadata: dict[str, Any],
    commentary: str = "",
) -> None:
    candidate = root / str(metadata["source"])
    replacement = (
        f"{commentary}\n    return sum(values)"
        if commentary
        else ("return sum(values)")
    )
    candidate.write_text(
        candidate.read_text().replace("raise NotImplementedError", replacement)
    )
    (root / str(metadata["candidate_test"])).write_text(
        "from algo.arrays.first import solve\n\n\n"
        "def test_candidate_example() -> None:\n"
        "    assert solve([1, 2]) == 3\n"
    )


@pytest.mark.parametrize("paradigm_name", tuple(practice.PARADIGMS))
def test_each_paradigm_uses_the_same_mechanical_state_machine(
    practice_repo: Path,
    paradigm_name: str,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, paradigm_name, "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])

    assert "THINKING GATE" not in candidate.read_text()
    assert practice.next_step(practice_repo, metadata)[0] == "THINK"

    candidate.write_text(
        candidate.read_text().replace("raise NotImplementedError", "return sum(values)")
    )
    assert practice.next_step(practice_repo, metadata)[0] == "BUILD"

    (practice_repo / str(metadata["candidate_test"])).write_text(
        "def test_candidate_example() -> None:\n    assert True\n"
    )
    assert practice.next_step(practice_repo, metadata)[0] == "REFLECT"

    practice._write_test_receipt(
        practice_repo,
        metadata,
        "passed",
        practice._test_input_digests(practice_repo, metadata),
    )
    assert practice.next_step(practice_repo, metadata)[0] == "CLOSE"

    candidate.write_text(candidate.read_text() + "\n# Revise after the run.\n")
    assert practice._test_receipt_status(practice_repo, metadata) == "stale"
    assert practice.next_step(practice_repo, metadata)[0] == "REFLECT"


@pytest.mark.parametrize("paradigm_name", tuple(practice.PARADIGMS))
@pytest.mark.parametrize(
    "commentary",
    [
        "",
        "# Visit each value once and return the accumulated total.",
        (
            '"""Return the sum of the values.\n\n'
            "An empty input returns zero; otherwise visit each value once.\n"
            '"""'
        ),
        "# RESTATE EXAMPLE APPROACH REACTO CLARP UMPIRE TODO TODO TODO",
    ],
    ids=["none", "ordinary-comment", "docstring", "keyword-stuffing"],
)
def test_prose_shape_never_changes_mechanical_progress(
    practice_repo: Path,
    paradigm_name: str,
    commentary: str,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, paradigm_name, "arrays", "first"
    )

    _implement_with_candidate_test(practice_repo, metadata, commentary)

    assert practice.next_step(practice_repo, metadata)[0] == "REFLECT"
    practice._require_unlocked(practice_repo, metadata)


@pytest.mark.parametrize("paradigm_name", tuple(practice.PARADIGMS))
def test_practice_next_is_read_only_and_idempotent(
    practice_repo: Path,
    paradigm_name: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, paradigm_name, "arrays", "first"
    )
    workspace = practice_repo / practice.WORKSPACE_REL
    before = _workspace_snapshot(workspace)

    assert practice.show_next(practice_repo, metadata) == 0
    first = capsys.readouterr().out
    assert practice.show_next(practice_repo, metadata) == 0
    second = capsys.readouterr().out

    assert first == second
    assert _workspace_snapshot(workspace) == before
    assert not (workspace / "comment-receipt.json").exists()
    assert not practice._test_receipt_path(practice_repo).exists()


@pytest.mark.parametrize(
    ("outcome", "returncode", "timed_out", "expected_state"),
    [
        ("passed", 0, False, "CLOSE"),
        ("failed", 1, False, "REFLECT"),
        ("timeout", 124, True, "REFLECT"),
    ],
)
def test_focused_run_receipt_controls_close_state(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
    returncode: int,
    timed_out: bool,
    expected_state: str,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _implement_with_candidate_test(practice_repo, metadata)

    def focused_run(
        _root: Path, _current: dict[str, Any], before: dict[str, str]
    ) -> practice.TestRun:
        return practice.TestRun(
            returncode=returncode,
            before=before,
            after=dict(before),
            timed_out=timed_out,
            completed=not timed_out,
        )

    monkeypatch.setattr(practice, "_execute_test_run", focused_run)

    assert practice.run_tests(practice_repo, metadata) == returncode
    assert practice._test_receipt_status(practice_repo, metadata) == outcome
    assert practice.next_step(practice_repo, metadata)[0] == expected_state


def test_pass_receipt_becomes_stale_after_any_candidate_edit(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _implement_with_candidate_test(practice_repo, metadata)
    practice._write_test_receipt(
        practice_repo,
        metadata,
        "passed",
        practice._test_input_digests(practice_repo, metadata),
    )
    assert practice.next_step(practice_repo, metadata)[0] == "CLOSE"

    candidate_test = practice_repo / str(metadata["candidate_test"])
    candidate_test.write_text(candidate_test.read_text() + "\n# another edge\n")

    assert practice._test_receipt_status(practice_repo, metadata) == "stale"
    assert practice.next_step(practice_repo, metadata)[0] == "REFLECT"


def test_pass_receipt_becomes_stale_after_committed_reference_source_changes(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _implement_with_candidate_test(practice_repo, metadata)
    practice._write_test_receipt(
        practice_repo,
        metadata,
        "passed",
        practice._test_input_digests(practice_repo, metadata),
    )
    assert practice.next_step(practice_repo, metadata)[0] == "CLOSE"

    reference = practice_repo / "src/algo/arrays/first.py"
    reference.write_text(
        reference.read_text().replace("return sum(values)", "return 7")
    )
    subprocess.run(["git", "add", reference], cwd=practice_repo, check=True)
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
            "change reference",
        ],
        cwd=practice_repo,
        check=True,
    )

    assert practice._test_receipt_status(practice_repo, metadata) == "stale"
    assert practice.next_step(practice_repo, metadata)[0] == "REFLECT"


def test_legacy_test_receipt_is_treated_as_no_current_evidence(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    legacy_inputs = {
        key: digest
        for key, digest in practice._test_input_digests(practice_repo, metadata).items()
        if key in practice.LEGACY_TEST_INPUT_KEYS
    }
    practice._test_receipt_path(practice_repo).write_text(
        json.dumps(
            {
                "schema": 1,
                "session_id": metadata["session_id"],
                "outcome": "passed",
                "inputs": legacy_inputs,
            }
        )
    )

    assert practice._test_receipt_status(practice_repo, metadata) == "never"


def test_focused_receipt_contains_only_outcome_and_digests(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    private_reasoning = "# My private example is [41, 1]."
    _implement_with_candidate_test(practice_repo, metadata, private_reasoning)
    practice._write_test_receipt(
        practice_repo,
        metadata,
        "passed",
        practice._test_input_digests(practice_repo, metadata),
    )

    receipt = practice._test_receipt_path(practice_repo).read_text()
    assert private_reasoning not in receipt
    assert "passed" in receipt


def test_test_preflight_rejects_a_save_during_unlock_validation(
    practice_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    monkeypatch.setattr(
        practice,
        "_require_committed_reference_test",
        lambda _root, _metadata: None,
    )

    def save_during_validation(_root: Path, _metadata: dict[str, Any]) -> None:
        candidate.write_text(candidate.read_text() + "\n# Saved concurrently.\n")

    monkeypatch.setattr(practice, "_require_unlocked", save_during_validation)

    with pytest.raises(practice.PracticeError, match="changed during test preflight"):
        practice._prepare_test_run(
            practice_repo,
            metadata,
            require_unlocked=True,
        )


def test_placeholder_keywords_do_not_control_tool_authorization(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        candidate.read_text().replace(
            practice.SOURCE_COMMENT_GUIDANCE,
            "# TODO RESTATE EXAMPLE APPROACH CODE TEST OPTIMIZE",
        )
    )

    practice._require_unlocked(practice_repo, metadata)


def test_candidate_tests_require_a_fresh_pass_before_close(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _implement_with_candidate_test(practice_repo, metadata)

    assert practice.next_step(practice_repo, metadata)[0] == "REFLECT"
    practice._write_test_receipt(
        practice_repo,
        metadata,
        "passed",
        practice._test_input_digests(practice_repo, metadata),
    )
    assert practice.next_step(practice_repo, metadata)[0] == "CLOSE"


def test_next_step_reports_candidate_test_syntax_error(practice_repo: Path) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "reacto", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        candidate.read_text().replace("raise NotImplementedError", "return sum(values)")
    )
    (practice_repo / str(metadata["candidate_test"])).write_text("def broken(:\n")

    state, next_action = practice.next_step(practice_repo, metadata)
    assert state == "BUILD"
    assert "syntax error in your test file" in next_action


def test_source_syntax_error_fails_closed_after_natural_comments(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        candidate.read_text().replace("raise NotImplementedError", "value = (")
    )

    state, next_action = practice.next_step(practice_repo, metadata)
    assert state == "BUILD"
    assert "syntax error in your source file" in next_action
    with pytest.raises(practice.PracticeError, match="source has a syntax error"):
        practice._require_unlocked(practice_repo, metadata)


def test_renamed_target_reports_build_instead_of_an_impossible_think_loop(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(candidate.read_text().replace("def solve(", "def renamed("))

    state, next_action = practice.next_step(practice_repo, metadata)
    assert state == "BUILD"
    assert "Restore the required `solve` definition" in next_action
    with pytest.raises(
        practice.PracticeError,
        match="source no longer defines required target 'solve'",
    ):
        practice._require_unlocked(practice_repo, metadata)


def test_class_target_without_methods_is_not_a_usable_definition() -> None:
    source = "class Solver:\n    pass\n"

    assert practice._target_definition(source, "Solver") is None
    assert not practice._target_is_started(source, "Solver")
    assert not practice._target_is_implemented(source, "Solver")


def test_nested_class_method_does_not_make_outer_target_usable() -> None:
    source = (
        "class Solver:\n"
        "    class Inner:\n"
        "        def run(self) -> int:\n"
        "            return 1\n"
    )

    assert practice._target_definition(source, "Solver") is None
    assert not practice._target_is_started(source, "Solver")
    assert not practice._target_is_implemented(source, "Solver")


def test_partial_class_implementation_advances_from_think_to_build(
    practice_repo: Path,
) -> None:
    source = (
        "class Solver:\n"
        '    """Candidate reasoning alone does not change mechanical state."""\n'
        "\n"
        "    def __init__(self) -> None:\n"
        "        self.values: list[int] = []\n"
        "\n"
        "    def run(self) -> int:\n"
        "        raise NotImplementedError\n"
    )
    metadata = {
        "target": "Solver",
        "candidate_test": ".challenges/workspace/test_solver_candidate.py",
    }
    _write(practice_repo / str(metadata["candidate_test"]), "")

    assert practice._target_is_started(source, "Solver")
    assert not practice._target_is_implemented(source, "Solver")
    state, next_action = practice._next_source_native_step(
        practice_repo, metadata, source
    )
    assert state == "BUILD"
    assert "no cold stubs" in next_action


def test_duplicate_target_definitions_are_not_a_usable_definition() -> None:
    source = "def solve() -> int:\n    return 1\n\ndef solve() -> int:\n    return 2\n"

    assert practice._target_definition(source, "solve") is None
    assert not practice._target_is_started(source, "solve")
    assert not practice._target_is_implemented(source, "solve")


def test_later_target_assignment_is_not_a_usable_definition() -> None:
    source = "def solve() -> int:\n    return 1\n\nsolve = lambda: 2\n"

    assert practice._target_definition(source, "solve") is None
    assert not practice._target_is_started(source, "solve")
    assert not practice._target_is_implemented(source, "solve")


def test_status_reports_only_mechanical_progress(
    practice_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )

    assert practice.show_status(practice_repo, metadata) == 0
    assert capsys.readouterr().out.splitlines() == [
        "target: stub",
        "candidate tests: 0",
        "focused tests: never",
    ]


def test_pytest_fixture_named_like_a_test_does_not_count(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "import pytest\n\n@pytest.fixture\ndef test_case() -> int:\n    return 1\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 0


def test_aliased_pytest_fixture_named_like_a_test_does_not_count(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "from pytest import fixture as fx\n\n"
        "@fx\n"
        "def test_case() -> int:\n"
        "    return 1\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 0


def test_assigned_pytest_fixture_alias_does_not_count(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "import pytest\n\n"
        "fx = pytest.fixture\n\n"
        "@fx\n"
        "def test_case() -> int:\n"
        "    return 1\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 0


def test_configured_pytest_fixture_alias_does_not_count(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "import pytest\n\n"
        'fx = pytest.fixture(scope="module")\n\n'
        "@fx\n"
        "def test_case() -> int:\n"
        "    return 1\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 0


def test_module_aliased_pytest_fixture_does_not_count(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "import pytest as pt\n\n"
        'fx = pt.fixture(scope="module")\n\n'
        "@fx\n"
        "def test_case() -> int:\n"
        "    return 1\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 0


def test_unrelated_fixture_attribute_does_not_hide_a_test(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "class Helpers:\n"
        "    @staticmethod\n"
        "    def fixture(function):\n"
        "        return function\n\n"
        "helpers = Helpers()\n\n"
        "@helpers.fixture\n"
        "def test_case() -> None:\n"
        "    assert True\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 1


@pytest.mark.parametrize(
    "candidate_tests",
    [
        (
            "from hypothesis import example, given, settings, strategies as st\n\n"
            "@settings(max_examples=3)\n"
            "@example(0)\n"
            "@given(st.integers())\n"
            "def test_property(value: int) -> None:\n"
            "    assert value == value\n"
        ),
        (
            "from unittest.mock import patch\n\n"
            "@patch('builtins.len', wraps=len)\n"
            "def test_patch(_mock_len: object) -> None:\n"
            "    assert True\n"
        ),
        (
            "from unittest.mock import patch\n\n"
            "@patch.object(str, 'lower', autospec=True)\n"
            "def test_patch_object(_mock_lower: object) -> None:\n"
            "    assert True\n"
        ),
        (
            "def transparent(function):\n"
            "    return function\n\n"
            "@transparent\n"
            "def test_local_decorator() -> None:\n"
            "    assert True\n"
        ),
        ("@staticmethod\ndef test_static() -> None:\n    assert True\n"),
    ],
)
def test_known_callable_preserving_decorators_count(
    practice_repo: Path, candidate_tests: str
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(candidate_tests)

    assert practice._candidate_test_count(practice_repo, metadata) == 1


def test_async_identity_shaped_decorator_does_not_count(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "async def transparent(function):\n"
        "    return function\n\n"
        "@transparent\n"
        "def test_local_decorator() -> None:\n"
        "    assert True\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 0


def test_unittest_case_methods_count_without_a_test_class_prefix(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "import unittest\n\n"
        "class CandidateChecks(unittest.TestCase):\n"
        "    def test_example(self) -> None:\n"
        "        self.assertTrue(True)\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 1


def test_aliased_unittest_case_methods_count(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "from unittest import TestCase as Base\n\n"
        "class CandidateChecks(Base):\n"
        "    def test_example(self) -> None:\n"
        "        self.assertTrue(True)\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 1


def test_module_aliased_unittest_case_methods_count(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "import unittest as unit\n\n"
        "Base = unit.TestCase\n\n"
        "class CandidateChecks(Base):\n"
        "    def test_example(self) -> None:\n"
        "        self.assertTrue(True)\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 1


def test_indirect_unittest_case_methods_count(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "import unittest\n\n"
        "class Base(unittest.TestCase):\n"
        "    pass\n\n"
        "class Candidate(Base):\n"
        "    def test_x(self) -> None:\n"
        "        pass\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 1


def test_unittest_constructor_does_not_prevent_collection(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "import unittest\n\n"
        "class Candidate(unittest.TestCase):\n"
        "    def __init__(self, method_name: str = 'runTest') -> None:\n"
        "        super().__init__(method_name)\n\n"
        "    def test_x(self) -> None:\n"
        "        pass\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 1


def test_falsey_module_test_flag_prevents_collection(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "__test__ = 0\n\ndef test_example() -> None:\n    assert True\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 0


def test_falsey_collection_module_test_flag_prevents_collection(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "__test__ = []\n\ndef test_example() -> None:\n    assert True\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 0


def test_truthy_class_test_flag_allows_collection_without_name_prefix(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "class CandidateChecks:\n"
        "    __test__ = True\n\n"
        "    def test_example(self) -> None:\n"
        "        assert True\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 1


def test_non_boolean_class_test_flag_does_not_force_collection(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "class CandidateChecks:\n"
        "    __test__ = 1\n\n"
        "    def test_example(self) -> None:\n"
        "        assert True\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 0


def test_unrelated_test_case_attribute_does_not_force_collection(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "class Helpers:\n"
        "    class TestCase:\n"
        "        pass\n\n"
        "helpers = Helpers()\n\n"
        "class CandidateChecks(helpers.TestCase):\n"
        "    def test_example(self) -> None:\n"
        "        assert True\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 0


def test_inherited_constructor_prevents_pytest_class_collection(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "class Base:\n"
        "    def __init__(self) -> None:\n"
        "        pass\n\n"
        "class TestCandidate(Base):\n"
        "    def test_x(self) -> None:\n"
        "        pass\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 0


def test_nested_pytest_classes_count_tests(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "class TestOuter:\n"
        "    class TestInner:\n"
        "        def test_x(self) -> None:\n"
        "            pass\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 1


def test_default_pytest_prefix_and_explicit_function_flag_count(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "def testExample() -> None:\n"
        "    pass\n\n"
        "def candidate_check() -> None:\n"
        "    pass\n\n"
        "candidate_check.__test__ = True\n\n"
        "class TestGroup:\n"
        "    def testCase(self) -> None:\n"
        "        pass\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 3


def test_finish_pairs_rep_log_and_spaced_update_idempotently(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(practice_repo, "clarp", "arrays", "first")
    _complete_session(practice_repo, metadata)

    assert practice.finish_session(practice_repo, metadata, "h0 trace the edge") == 0
    assert practice.finish_session(practice_repo, metadata, "h0 trace the edge") == 0

    reps = (practice_repo / ".challenges/reps.md").read_text().splitlines()
    progress = (practice_repo / ".challenges/progress.md").read_text().splitlines()
    assert len(reps) == 1
    assert "clarp arrays/first fix: h0 trace the edge" in reps[0]
    assert len(progress) == 1
    assert progress[0].startswith("- [x] arrays/first ")


def test_finish_reuses_the_completed_receipt_without_running_tests(
    practice_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _complete_session(practice_repo, metadata)
    receipt = practice._test_receipt_path(practice_repo).read_text()

    def unexpected_pytest(*_args: object, **_kwargs: object) -> None:
        pytest.fail("closeout must not implicitly rerun candidate tests")

    monkeypatch.setattr(practice, "_execute_test_run", unexpected_pytest)
    assert practice.finish_session(practice_repo, metadata, "trace the edge") == 0
    assert practice.current_metadata(practice_repo)["test_outcome"] == "passed"
    assert practice._test_receipt_path(practice_repo).read_text() == receipt


def test_finish_preserves_progress_for_similar_problem_name(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(practice_repo, "clarp", "arrays", "first")
    _complete_session(practice_repo, metadata)
    _write(
        practice_repo / ".challenges/progress.md",
        "- [x] arrays/first_extended 2026-01-01\n",
    )

    practice.finish_session(practice_repo, metadata, "h0 trace the edge")

    progress = (practice_repo / ".challenges/progress.md").read_text()
    assert "arrays/first_extended 2026-01-01" in progress
    assert "arrays/first " in progress


def test_finish_does_not_execute_workspace_python_startup(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _complete_session(practice_repo, metadata)
    workspace = practice_repo / practice.WORKSPACE_REL
    sentinel = practice_repo / "startup-executed"
    (workspace / "sitecustomize.py").write_text(
        f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('executed')\n"
    )
    assert practice.finish_session(practice_repo, metadata, "trace the edge") == 0
    assert not sentinel.exists()
    assert practice.current_metadata(practice_repo)["test_outcome"] == "passed"


def test_stub_session_can_close_without_claiming_tests_ran(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )

    assert (
        practice.finish_session(
            practice_repo, metadata, "C1 starts this free-text note"
        )
        == 0
    )

    finished = practice.current_metadata(practice_repo)
    assert finished["finish_state"] == "THINK"
    assert finished["test_outcome"] == "not_run"
    assert finished["finish_note"] == "C1 starts this free-text note"
    assert (practice_repo / ".challenges/reps.md").is_file()
    assert (practice_repo / ".challenges/progress.md").is_file()


def test_schema4_sessions_read_and_migrate_without_touching_candidate_work(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    paradigm = practice.PARADIGMS["comments"]
    candidate = practice_repo / str(metadata["source"])
    original_candidate = candidate.read_text()
    legacy_lines = [
        *paradigm.seeds[:3],
        practice.LEGACY_SCHEMA4_LOCK,
        *paradigm.seeds[3:],
    ]
    legacy_block = "".join(f"    {line}\n" for line in legacy_lines)
    legacy_candidate = original_candidate.replace(
        f"    {practice.SOURCE_COMMENT_GUIDANCE}\n",
        legacy_block,
    )
    assert legacy_candidate != original_candidate
    legacy_candidate += "\n# preserve this unfinished note\n"
    candidate.write_text(legacy_candidate)
    candidate_test = practice_repo / str(metadata["candidate_test"])
    candidate_test.write_text(
        candidate_test.read_text() + "\n# preserve this candidate test note\n"
    )
    expected_source = "".join(
        line
        for line in legacy_candidate.splitlines(keepends=True)
        if line.strip() != practice.LEGACY_SCHEMA4_LOCK
    )
    expected_test = candidate_test.read_text()
    metadata_path = practice_repo / ".challenges/workspace/session.json"
    metadata_path.write_text(
        json.dumps(_legacy_schema4_metadata(metadata), indent=2) + "\n"
    )
    legacy_receipt = (
        practice_repo / practice.WORKSPACE_REL / practice.LEGACY_COMMENT_RECEIPT_NAME
    )
    legacy_receipt.write_text('{"schema": 1, "obsolete": true}\n')
    migrated = practice.current_metadata(practice_repo)
    assert migrated["schema"] == practice.METADATA_SCHEMA
    assert {"lock", "seeds", "pre_code_labels"}.isdisjoint(migrated)
    assert json.loads(metadata_path.read_text())["schema"] == 4
    assert candidate.read_text() == legacy_candidate

    assert practice.show_next(practice_repo, migrated) == 0
    assert candidate.read_text() == expected_source
    assert candidate_test.read_text() == expected_test
    assert not legacy_receipt.exists()
    persisted = json.loads(metadata_path.read_text())
    assert persisted["schema"] == practice.METADATA_SCHEMA
    assert {"lock", "seeds", "pre_code_labels"}.isdisjoint(persisted)

    assert practice.finish_session(practice_repo, migrated, "keep notes natural") == 0
    finished = json.loads(metadata_path.read_text())
    assert finished["schema"] == practice.METADATA_SCHEMA
    assert {"lock", "seeds", "pre_code_labels"}.isdisjoint(finished)

    finished_source = candidate.read_text()
    candidate.write_text(finished_source + f"{practice.LEGACY_SCHEMA4_LOCK}\n")
    metadata_path.write_text(
        json.dumps(_legacy_schema4_metadata(finished), indent=2) + "\n"
    )
    migrated_finished = practice.current_metadata(practice_repo)
    assert migrated_finished["finished_at"] == finished["finished_at"]
    assert migrated_finished["schema"] == practice.METADATA_SCHEMA
    assert (
        practice.finish_session(practice_repo, migrated_finished, "keep notes natural")
        == 0
    )
    assert candidate.read_text() == finished_source
    assert candidate_test.read_text() == expected_test
    assert json.loads(metadata_path.read_text())["schema"] == practice.METADATA_SCHEMA


def test_schema4_migration_rejects_symlinked_legacy_comment_receipt(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(candidate.read_text() + f"\n{practice.LEGACY_SCHEMA4_LOCK}\n")
    metadata_path = practice_repo / practice.WORKSPACE_REL / practice.METADATA_NAME
    metadata_path.write_text(
        json.dumps(_legacy_schema4_metadata(metadata), indent=2) + "\n"
    )
    outside = practice_repo / "outside-receipt.json"
    outside.write_text('{"keep": true}\n')
    receipt = (
        practice_repo / practice.WORKSPACE_REL / practice.LEGACY_COMMENT_RECEIPT_NAME
    )
    receipt.symlink_to(outside)

    with pytest.raises(practice.PracticeError, match="cannot be a symlink"):
        practice.show_next(practice_repo, practice.current_metadata(practice_repo))

    assert outside.read_text() == '{"keep": true}\n'
    assert practice.LEGACY_SCHEMA4_LOCK in candidate.read_text()
    assert json.loads(metadata_path.read_text())["schema"] == 4


def test_explicit_fresh_switch_archives_then_resets_workspace(
    practice_repo: Path,
) -> None:
    first, _, _ = practice.prepare_session(practice_repo, "reacto", "arrays", "first")
    first_candidate = practice_repo / str(first["source"])
    first_candidate.write_text(first_candidate.read_text() + "\n# reacto trail\n")

    clarp, action, reacto_archive = practice.prepare_session(
        practice_repo, "clarp", "arrays", "first", fresh=True
    )

    assert action == "created"
    assert reacto_archive is not None
    assert "reacto trail" in (reacto_archive / "first.py").read_text()
    clarp_candidate = practice_repo / str(clarp["source"])
    assert "# CLARIFY:" in clarp_candidate.read_text()
    assert "# REPEAT:" not in clarp_candidate.read_text()
    assert "reacto trail" not in clarp_candidate.read_text()
    assert "THINKING GATE" not in clarp_candidate.read_text()

    clarp_candidate.write_text(clarp_candidate.read_text() + "\n# first trail\n")
    second, action, first_archive = practice.prepare_session(
        practice_repo, "clarp", "arrays", "second", fresh=True
    )

    assert action == "created"
    assert first_archive is not None
    assert "first trail" in (first_archive / "first.py").read_text()
    second_candidate = practice_repo / str(second["source"])
    assert second_candidate.name == "second.py"
    assert "first trail" not in second_candidate.read_text()
    assert not (practice_repo / ".challenges/workspace/first.py").exists()


def test_unfinished_switch_requires_finish_or_explicit_fresh_archive(
    practice_repo: Path,
) -> None:
    first, _, _ = practice.prepare_session(practice_repo, "reacto", "arrays", "first")
    candidate = practice_repo / str(first["source"])
    candidate.write_text(candidate.read_text() + "\n# Candidate work remains here.\n")

    with pytest.raises(practice.PracticeError) as raised:
        practice.prepare_session(practice_repo, "clarp", "arrays", "second")

    message = str(raised.value)
    assert "unfinished editor rep: reacto arrays/first" in message
    assert "just practice-finish" in message
    assert "just practice-new clarp arrays second" in message
    current = practice.current_metadata(practice_repo)
    assert current["session_id"] == first["session_id"]
    assert "Candidate work remains here" in candidate.read_text()
    assert not (practice_repo / ".challenges/history").exists()


@pytest.mark.parametrize("paradigm_name", tuple(practice.PARADIGMS))
def test_tests_watch_and_repl_are_not_authorized_by_prose_counts(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    paradigm_name: str,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, paradigm_name, "arrays", "first"
    )
    _implement_with_candidate_test(practice_repo, metadata)
    calls: list[tuple[str, list[str]]] = []

    def focused_run(
        _root: Path, _current: dict[str, Any], before: dict[str, str]
    ) -> practice.TestRun:
        return practice.TestRun(0, before, dict(before), completed=True)

    def fake_execvpe(executable: str, args: list[str], _env: dict[str, str]) -> None:
        calls.append((executable, args))

    monkeypatch.setattr(practice, "_execute_test_run", focused_run)
    monkeypatch.setattr(practice.shutil, "which", lambda _name: "/mock/watchexec")
    monkeypatch.setattr(practice.os, "execvpe", fake_execvpe)

    assert practice.run_tests(practice_repo, metadata) == 0
    assert practice.run_watch(practice_repo, metadata) == 1
    assert practice.run_repl(practice_repo, metadata) == 1
    assert len(calls) == 2


def test_unlocked_session_tests_candidate_instead_of_reference(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        candidate.read_text().replace(
            "raise NotImplementedError",
            "return sum(values)  # Sum once, then return the total.",
        )
        + "\nCANDIDATE_ONLY = True\n"
    )
    candidate_test = practice_repo / str(metadata["candidate_test"])
    candidate_test.write_text(
        "from algo.arrays.first import CANDIDATE_ONLY\n\n\n"
        "def test_candidate_module_is_installed() -> None:\n"
        "    assert CANDIDATE_ONLY is True\n"
    )

    assert practice.run_tests(practice_repo, metadata) == 0


@pytest.mark.parametrize(
    "candidate_tests",
    [
        "",
        "# Candidate will add tests here.\n\nimport pytest\n",
        "def candidate_example() -> None:\n    assert True\n",
        (
            "import pytest\n\n"
            "@pytest.fixture\n"
            "def test_named_fixture() -> int:\n"
            "    return 1\n"
        ),
        'import pytest\n\npytest.skip("not ready", allow_module_level=True)\n',
    ],
)
def test_test_run_reports_build_before_locked_suite_for_no_collectable_tests(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    candidate_tests: str,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _implement_with_candidate_test(practice_repo, metadata)
    (practice_repo / str(metadata["candidate_test"])).write_text(candidate_tests)

    def unexpected_prepare(*_args: object, **_kwargs: object) -> dict[str, str]:
        raise AssertionError("locked suite preparation must not run")

    monkeypatch.setattr(practice, "_prepare_test_run", unexpected_prepare)

    collection_args = practice._candidate_collection_args(practice_repo, metadata)
    assert str(metadata["candidate_test"]) in collection_args
    assert str(metadata["reference_test"]) not in collection_args
    assert set(
        practice._candidate_collection_input_digests(practice_repo, metadata)
    ) == set(practice.CANDIDATE_COLLECTION_INPUT_KEYS)
    assert "reference_test" not in practice.CANDIDATE_COLLECTION_INPUT_KEYS
    assert "reference_source" not in practice.CANDIDATE_COLLECTION_INPUT_KEYS
    assert practice.run_tests(practice_repo, metadata) == 2
    captured = capsys.readouterr()
    assert captured.out == (
        "STATE: BUILD\n"
        f"TEST: {metadata['candidate_test']}\n"
        "NEXT: Add one collectable candidate test in the open test file, save, "
        "then run just practice-test.\n"
    )
    assert captured.err == ""
    assert not practice._test_receipt_path(practice_repo).exists()
    plugin = (practice_repo / str(metadata["plugin"])).read_text()
    assert "add one collectable candidate test" in plugin
    assert "top-level test_" not in plugin


@pytest.mark.parametrize(
    "candidate_tests",
    [
        "def test_generator():\n    yield 1\n",
        ("class TestCandidate:\n    def test_generator(self):\n        yield 1\n"),
    ],
)
def test_invalid_generator_tests_relay_the_real_collection_error(
    practice_repo: Path,
    capsys: pytest.CaptureFixture[str],
    candidate_tests: str,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _implement_with_candidate_test(practice_repo, metadata)
    (practice_repo / str(metadata["candidate_test"])).write_text(candidate_tests)

    assert practice.run_tests(practice_repo, metadata) != 0
    captured = capsys.readouterr()
    assert "ERROR collecting" in captured.out
    assert "STATE: BUILD" not in captured.out
    assert not practice._test_receipt_path(practice_repo).exists()


def test_locked_source_never_launches_candidate_collection(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(candidate.read_text().replace("def solve(", "def renamed("))
    sentinel = practice_repo / "candidate-test-imported"
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "from pathlib import Path\n"
        "Path('candidate-test-imported').write_text('ran')\n\n\n"
        "def test_candidate_example() -> None:\n"
        "    assert True\n"
    )

    def unexpected_collection(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("locked source must fail before candidate collection")

    monkeypatch.setattr(
        practice, "_execute_candidate_collection", unexpected_collection
    )

    with pytest.raises(practice.PracticeError):
        practice.run_tests(practice_repo, metadata)
    assert not sentinel.exists()
    assert not practice._test_receipt_path(practice_repo).exists()


def test_attested_empty_collection_never_loads_locked_reference_inputs(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reference_source = practice_repo / "src/algo/arrays/first.py"
    reference_source.write_text(
        "if __name__.startswith('_practice_reference_'):\n"
        "    raise AssertionError('committed reference facade loaded')\n\n"
        + reference_source.read_text()
    )
    _commit_fixture(practice_repo)
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _implement_with_candidate_test(practice_repo, metadata)
    (practice_repo / str(metadata["candidate_test"])).write_text("")
    (practice_repo / str(metadata["reference_test"])).write_text(
        "raise AssertionError('locked reference tests loaded')\n"
    )

    def unexpected_prepare(*_args: object, **_kwargs: object) -> dict[str, str]:
        raise AssertionError("locked suite preparation must not run")

    monkeypatch.setattr(practice, "_prepare_test_run", unexpected_prepare)

    assert practice.run_tests(practice_repo, metadata) == 2
    assert capsys.readouterr().out.startswith("STATE: BUILD\n")
    assert not practice._test_receipt_path(practice_repo).exists()


@pytest.mark.parametrize(
    "candidate_tests",
    [
        (
            "from algo.arrays.first import solve\n\n\n"
            "def test_candidate_example() -> None:\n"
            "    assert solve([1, 2]) == 3\n"
        ),
        (
            "from algo.arrays.first import solve\n\n\n"
            "class TestCandidate:\n"
            "    def test_example(self) -> None:\n"
            "        assert solve([1, 2]) == 3\n"
        ),
        (
            "from algo.arrays.first import solve\n\n\n"
            "def test_nested_generator_is_only_a_helper() -> None:\n"
            "    def values():\n"
            "        yield 1\n"
            "        yield 2\n\n"
            "    assert solve(list(values())) == 3\n"
        ),
    ],
)
def test_test_run_accepts_collectable_functions_and_class_methods(
    practice_repo: Path,
    candidate_tests: str,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _implement_with_candidate_test(practice_repo, metadata)
    (practice_repo / str(metadata["candidate_test"])).write_text(candidate_tests)

    assert practice.run_tests(practice_repo, metadata) == 0
    assert practice._test_receipt_status(practice_repo, metadata) == "passed"


def test_runtime_collection_accepts_an_opaque_callable_preserving_decorator(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _implement_with_candidate_test(practice_repo, metadata)
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "from functools import wraps\n"
        "from algo.arrays.first import solve\n\n\n"
        "def preserve(function):\n"
        "    @wraps(function)\n"
        "    def wrapped(*args, **kwargs):\n"
        "        return function(*args, **kwargs)\n"
        "    return wrapped\n\n\n"
        "@preserve\n"
        "def test_candidate_example() -> None:\n"
        "    assert solve([1, 2]) == 3\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 0
    state, next_action = practice.next_step(practice_repo, metadata)
    assert state == "BUILD"
    assert "explicitly ask to run just practice-test" in next_action
    assert practice.run_tests(practice_repo, metadata) == 0
    assert practice._test_receipt_status(practice_repo, metadata) == "passed"
    assert practice.next_step(practice_repo, metadata)[0] == "CLOSE"


def test_attested_empty_collection_preserves_existing_receipt_bytes(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _implement_with_candidate_test(practice_repo, metadata)
    assert practice.run_tests(practice_repo, metadata) == 0
    receipt = practice._test_receipt_path(practice_repo)
    before = receipt.read_bytes()
    (practice_repo / str(metadata["candidate_test"])).write_text("")

    def unexpected_prepare(*_args: object, **_kwargs: object) -> dict[str, str]:
        raise AssertionError("locked suite preparation must not run")

    monkeypatch.setattr(practice, "_prepare_test_run", unexpected_prepare)

    assert practice.run_tests(practice_repo, metadata) == 2
    assert receipt.read_bytes() == before


def test_collection_exit_five_without_attestation_is_not_an_empty_test_result(
    practice_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _implement_with_candidate_test(practice_repo, metadata)
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "import os\n\nos._exit(5)\n"
    )

    assert practice.run_tests(practice_repo, metadata) == 3
    captured = capsys.readouterr()
    assert "ended before pytest completed" in captured.err
    assert "STATE: BUILD" not in captured.out
    assert not practice._test_receipt_path(practice_repo).exists()


def test_candidate_is_active_during_test_module_import(practice_repo: Path) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        candidate.read_text().replace(
            "raise NotImplementedError",
            "if values:\n        return sum(values)\n    return -1",
        )
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "from algo.arrays.first import solve\n\n"
        "EMPTY_RESULT = solve([])\n\n\n"
        "def test_empty_input() -> None:\n"
        "    assert EMPTY_RESULT == 0\n"
    )

    assert practice.run_tests(practice_repo, metadata) == 1


def test_ambient_pytest_options_cannot_turn_failures_into_collection_only(
    practice_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        candidate.read_text().replace("raise NotImplementedError", "return 0")
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "def test_candidate_smoke() -> None:\n    assert True\n"
    )
    monkeypatch.setenv("PYTEST_ADDOPTS", "--collect-only")
    monkeypatch.setenv("PYTEST_PLUGINS", "untrusted_plugin")

    env = practice._practice_env(practice_repo)
    assert "PYTEST_ADDOPTS" not in env
    assert "PYTEST_PLUGINS" not in env
    assert env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert practice.run_tests(practice_repo, metadata) == 1


def test_repo_pytest_config_cannot_turn_failures_into_collection_only(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        candidate.read_text().replace("raise NotImplementedError", "return 0")
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "def test_candidate_smoke() -> None:\n    assert False\n"
    )
    (practice_repo / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\naddopts = ["--collect-only"]\n'
    )

    assert practice.run_tests(practice_repo, metadata) == 1
    assert practice.next_step(practice_repo, metadata)[0] == "REFLECT"


def test_candidate_conftest_cannot_skip_locked_or_candidate_tests(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        candidate.read_text().replace("raise NotImplementedError", "return 0")
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "def test_candidate_smoke() -> None:\n    assert False\n"
    )
    workspace = practice_repo / practice.WORKSPACE_REL
    (workspace / "conftest.py").write_text(
        "import pytest\n\n"
        "def pytest_collection_modifyitems(items):\n"
        "    for item in items:\n"
        "        item.add_marker(pytest.mark.skip)\n"
    )

    assert practice.run_tests(practice_repo, metadata) == 1
    assert practice.next_step(practice_repo, metadata)[0] == "REFLECT"


@pytest.mark.parametrize("marker", ["skip", "xfail"])
def test_candidate_tests_must_really_pass(
    practice_repo: Path,
    marker: str,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        candidate.read_text().replace("raise NotImplementedError", "return sum(values)")
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "import pytest\n\n"
        f"@pytest.mark.{marker}\n"
        "def test_candidate_smoke() -> None:\n"
        "    assert False\n"
    )

    assert practice.run_tests(practice_repo, metadata) == 1
    assert practice.next_step(practice_repo, metadata)[0] == "REFLECT"


@pytest.mark.parametrize(
    "candidate_tests",
    [
        (
            "from unittest import skipIf\n"
            "from algo.arrays.first import solve\n\n\n"
            '@skipIf(False, "runs")\n'
            "def test_candidate_example() -> None:\n"
            "    assert solve([1, 2]) == 3\n"
        ),
        (
            "import unittest as unit\n"
            "from algo.arrays.first import solve\n\n\n"
            "class CandidateChecks(unit.TestCase):\n"
            '    @unit.skipUnless(True, "runs")\n'
            "    def test_example(self) -> None:\n"
            "        self.assertEqual(solve([1, 2]), 3)\n"
        ),
    ],
)
def test_unittest_conditional_decorators_run_real_tests(
    practice_repo: Path,
    candidate_tests: str,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _implement_with_candidate_test(practice_repo, metadata)
    (practice_repo / str(metadata["candidate_test"])).write_text(candidate_tests)

    assert practice._candidate_test_count(practice_repo, metadata) == 0
    assert practice.run_tests(practice_repo, metadata) == 0
    assert practice._test_receipt_status(practice_repo, metadata) == "passed"


def test_unittest_custom_run_test_runs_as_the_fallback(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _implement_with_candidate_test(practice_repo, metadata)
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "from unittest import TestCase\n"
        "from algo.arrays.first import solve\n\n\n"
        "class CandidateChecks(TestCase):\n"
        "    def runTest(self) -> None:\n"
        "        self.assertEqual(solve([1, 2]), 3)\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 0
    assert practice.run_tests(practice_repo, metadata) == 0
    assert practice._test_receipt_status(practice_repo, metadata) == "passed"


@pytest.mark.parametrize(
    "candidate_tests",
    [
        (
            "from unittest import skip\n\n\n"
            '@skip("not ready")\n'
            "def test_candidate_example() -> None:\n"
            "    assert True\n"
        ),
        (
            "from unittest import TestCase, expectedFailure\n"
            "from algo.arrays.first import solve\n\n\n"
            "class CandidateChecks(TestCase):\n"
            "    @expectedFailure\n"
            "    def test_example(self) -> None:\n"
            "        self.assertEqual(solve([1, 2]), 99)\n"
        ),
    ],
)
def test_unittest_skips_and_expected_failures_remain_open(
    practice_repo: Path,
    candidate_tests: str,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _implement_with_candidate_test(practice_repo, metadata)
    (practice_repo / str(metadata["candidate_test"])).write_text(candidate_tests)

    assert practice._candidate_test_count(practice_repo, metadata) == 0
    assert practice.run_tests(practice_repo, metadata) == 1
    assert practice._test_receipt_status(practice_repo, metadata) == "failed"
    assert practice.next_step(practice_repo, metadata)[0] == "REFLECT"


def test_candidate_target_cannot_skip_locked_tests(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        _inject_after_future(
            candidate.read_text().replace(
                "raise NotImplementedError", "pytest.skip('not ready')"
            ),
            "import pytest\n",
        )
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "def test_candidate_smoke() -> None:\n    assert True\n"
    )

    assert practice.run_tests(practice_repo, metadata) == 1
    assert practice._test_receipt_status(practice_repo, metadata) == "failed"
    assert practice.next_step(practice_repo, metadata)[0] == "REFLECT"


@pytest.mark.parametrize("exit_surface", ["candidate", "sitecustomize"])
def test_zero_exit_before_pytest_completion_is_not_a_pass(
    practice_repo: Path,
    exit_surface: str,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        _inject_after_future(
            candidate.read_text().replace(
                "raise NotImplementedError", "return sum(values)"
            ),
            "import os\nos._exit(0)\n",
        )
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "def test_candidate_smoke() -> None:\n    assert False\n"
    )
    if exit_surface == "sitecustomize":
        candidate.write_text(
            candidate.read_text().replace("import os\nos._exit(0)\n", "")
        )
        workspace = practice_repo / practice.WORKSPACE_REL
        (workspace / "sitecustomize.py").write_text("import os\nos._exit(0)\n")

    assert practice.run_tests(practice_repo, metadata) == 3
    assert practice._test_receipt_status(practice_repo, metadata) == "never"
    assert practice.next_step(practice_repo, metadata)[0] == "REFLECT"


def test_detached_completion_writer_cannot_hang_test_runner(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        _inject_after_future(
            candidate.read_text().replace(
                "raise NotImplementedError", "return sum(values)"
            ),
            "import os\n"
            "import time\n"
            "pid = os.fork()\n"
            "if pid == 0:\n"
            "    os.setsid()\n"
            "    with open('.challenges/workspace/detached.pid', 'w') as handle:\n"
            "        handle.write(str(os.getpid()))\n"
            "    time.sleep(30)\n"
            "    os._exit(0)\n"
            "deadline = time.monotonic() + 2\n"
            "while not os.path.exists('.challenges/workspace/detached.pid'):\n"
            "    if time.monotonic() >= deadline:\n"
            "        os._exit(2)\n"
            "    time.sleep(0.01)\n"
            "os._exit(0)\n",
        )
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "def test_candidate_smoke() -> None:\n    assert False\n"
    )
    pid_path = practice_repo / practice.WORKSPACE_REL / "detached.pid"

    started = time.monotonic()
    try:
        assert practice.run_tests(practice_repo, metadata) == 3
        assert time.monotonic() - started < 2
        assert pid_path.is_file()
    finally:
        if pid_path.exists():
            with suppress(ProcessLookupError):
                os.kill(int(pid_path.read_text()), signal.SIGKILL)


def test_open_session_targets_reasoning_line_and_candidate_test(
    practice_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "umpire", "arrays", "first"
    )
    calls: list[tuple[list[str], Path, bool, int]] = []

    def fake_run(
        args: list[str], *, cwd: Path, check: bool, timeout: int
    ) -> SimpleNamespace:
        calls.append((args, cwd, check, timeout))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(practice.shutil, "which", lambda _name: "/mock/code")
    monkeypatch.setattr(practice.subprocess, "run", fake_run)

    assert practice.open_session(practice_repo, metadata)
    source = str(metadata["source"])
    source_path = practice_repo / source
    first_seed = practice.PARADIGMS["umpire"].seeds[0].split(":", 1)[0]
    line = next(
        number
        for number, text in enumerate(source_path.read_text().splitlines(), start=1)
        if first_seed in text
    )
    assert calls == [
        (
            [
                "/mock/code",
                "--reuse-window",
                str(metadata["candidate_test"]),
                "--goto",
                f"{source}:{line}",
            ],
            practice_repo,
            False,
            practice.EDITOR_OPEN_TIMEOUT_SECONDS,
        )
    ]
    opened_args = calls[0][0]
    assert str(metadata["reference_test"]) not in opened_args
    assert not any(argument.startswith("src/algo/") for argument in opened_args)


def test_open_session_can_focus_candidate_tests_first(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    calls: list[list[str]] = []

    def fake_run(
        args: list[str], *, cwd: Path, check: bool, timeout: int
    ) -> SimpleNamespace:
        del cwd, check, timeout
        calls.append(args)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(practice.shutil, "which", lambda _name: "/mock/code")
    monkeypatch.setattr(practice.subprocess, "run", fake_run)

    assert practice.open_session(practice_repo, metadata, focus="test")

    assert calls == [
        [
            "/mock/code",
            "--reuse-window",
            str(metadata["source"]),
            "--goto",
            f"{metadata['candidate_test']}:1",
        ]
    ]
    output = capsys.readouterr().out
    assert f"OPENED: {metadata['candidate_test']}:1" in output
    assert "FOCUS: TEST" in output


@pytest.mark.parametrize("failure", ["missing", "timeout", "nonzero"])
def test_tests_first_open_failure_preserves_the_tests_first_retry(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    monkeypatch.setattr(
        practice.shutil,
        "which",
        lambda _name: None if failure == "missing" else "/mock/code",
    )

    def fail_run(
        _args: list[str], *, cwd: Path, check: bool, timeout: int
    ) -> SimpleNamespace:
        del cwd, check
        if failure == "timeout":
            raise subprocess.TimeoutExpired("code", timeout)
        return SimpleNamespace(returncode=9)

    monkeypatch.setattr(practice.subprocess, "run", fail_run)

    assert not practice.open_session(practice_repo, metadata, focus="test")

    output = capsys.readouterr().out
    assert "FOCUS:" not in output
    assert "NEXT: Restore the code CLI, then run " in output
    assert "just practice-start-tests arrays first" in output


def test_open_session_without_code_prints_only_safe_candidate_paths(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    metadata = practice.prepare_open_target(practice_repo, "arrays", "first")
    monkeypatch.setattr(practice.shutil, "which", lambda _name: None)

    assert not practice.open_session(practice_repo, metadata)

    output = capsys.readouterr().out
    assert str(metadata["source"]) in output
    assert str(metadata["candidate_test"]) in output
    assert str(metadata["reference_test"]) not in output
    assert "src/algo/" not in output


def test_open_session_timeout_prints_safe_candidate_paths(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    metadata = practice.prepare_open_target(practice_repo, "arrays", "first")
    monkeypatch.setattr(practice.shutil, "which", lambda _name: "/mock/code")

    def time_out(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired("code", practice.EDITOR_OPEN_TIMEOUT_SECONDS)

    monkeypatch.setattr(practice.subprocess, "run", time_out)

    assert not practice.open_session(practice_repo, metadata)
    output = capsys.readouterr().out
    assert str(metadata["source"]) in output
    assert str(metadata["candidate_test"]) in output
    assert str(metadata["reference_test"]) not in output


def test_watch_runs_guarded_recipe_for_workspace_and_reference_test(
    practice_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "reacto", "arrays", "first"
    )
    calls: list[tuple[str, list[str], dict[str, str]]] = []

    monkeypatch.setattr(practice, "_require_unlocked", lambda _root, _meta: None)
    monkeypatch.setattr(practice.shutil, "which", lambda _name: "/mock/watchexec")

    def fake_execvpe(executable: str, args: list[str], env: dict[str, str]) -> None:
        calls.append((executable, args, env))

    monkeypatch.setattr(practice.os, "execvpe", fake_execvpe)

    assert practice.run_watch(practice_repo, metadata) == 1
    assert calls[0][0] == "/mock/watchexec"
    args = calls[0][1]
    assert "--ignore-nothing" in args
    watch_paths = [args[index + 1] for index, arg in enumerate(args) if arg == "-w"]
    assert watch_paths == [
        str(practice_repo / ".challenges/workspace"),
        str(practice_repo / str(metadata["reference_test"])),
    ]
    assert args[args.index("--") + 1 :] == ["just", "practice-test"]


def test_watch_missing_optional_helper_is_actionable(
    practice_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "reacto", "arrays", "first"
    )
    monkeypatch.setattr(practice, "_require_unlocked", lambda _root, _meta: None)
    monkeypatch.setattr(practice.shutil, "which", lambda _name: None)

    with pytest.raises(practice.PracticeError, match="use `just practice-test`"):
        practice.run_watch(practice_repo, metadata)


def test_candidate_source_syntax_error_stays_in_build(practice_repo: Path) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(candidate.read_text() + "\nif (\n")

    state, next_action = practice.next_step(practice_repo, metadata)
    assert state == "BUILD"
    assert "syntax error in your source file" in next_action


def test_nested_test_function_does_not_count_as_candidate_test(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        candidate.read_text().replace("raise NotImplementedError", "return sum(values)")
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "def helper() -> None:\n"
        "    def test_nested_does_not_collect() -> None:\n"
        "        assert True\n"
    )

    assert practice.next_step(practice_repo, metadata)[0] == "BUILD"


def test_pytest_class_method_counts_as_candidate_test(practice_repo: Path) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        candidate.read_text().replace(
            "raise NotImplementedError",
            "return sum(values)  # Sum once, then return the total.",
        )
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "class TestCandidate:\n"
        "    def test_example(self) -> None:\n"
        "        assert True\n"
    )

    assert practice._candidate_test_count(practice_repo, metadata) == 1
    assert practice.next_step(practice_repo, metadata)[0] == "REFLECT"


@pytest.mark.parametrize(
    "candidate_tests",
    [
        "__test__ = False\n\n\ndef test_hidden() -> None:\n    assert True\n",
        (
            "class TestHidden:\n"
            "    __test__ = False\n\n"
            "    def test_hidden(self) -> None:\n"
            "        assert True\n"
        ),
    ],
)
def test_uncollected_tests_do_not_advance_state(
    practice_repo: Path, candidate_tests: str
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        candidate.read_text().replace("raise NotImplementedError", "return sum(values)")
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(candidate_tests)

    assert practice.next_step(practice_repo, metadata)[0] == "BUILD"


def test_candidate_helper_stub_does_not_hide_implemented_target(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        candidate.read_text().replace(
            "raise NotImplementedError",
            "return sum(values)  # Sum once, then return the total.",
            1,
        )
        + "\n\ndef optional_backend() -> None:\n    raise NotImplementedError\n"
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "def test_candidate_example() -> None:\n    assert True\n"
    )

    assert practice.next_step(practice_repo, metadata)[0] == "REFLECT"


def test_committed_private_support_is_not_injected_into_candidate_tests(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        candidate.read_text().replace(
            "raise NotImplementedError", "return _support(values)", 1
        )
    )
    (practice_repo / str(metadata["candidate_test"])).write_text(
        "def test_candidate_smoke() -> None:\n    assert True\n"
    )

    plugin = (practice_repo / str(metadata["plugin"])).read_text()
    assert "SUPPORT: tuple[str, ...] = ()" in plugin
    assert "getattr(reference, name)" not in plugin
    assert practice.run_tests(practice_repo, metadata) == 1


@pytest.mark.parametrize(
    ("topic", "problem", "target", "omitted_helper"),
    [
        ("recursion", "flatten_nested_list", "flatten_recursive", "_flatten_helper"),
        ("graphs", "number_of_islands", "num_islands", "_bfs"),
        ("graphs", "minimum_spanning_tree", "kruskal", "UnionFind"),
    ],
)
def test_real_helper_dependent_target_cannot_use_committed_implementation(
    tmp_path: Path,
    topic: str,
    problem: str,
    target: str,
    omitted_helper: str,
) -> None:
    source_rel = Path("src/algo") / topic / f"{problem}.py"
    test_rel = Path("tests") / topic / f"test_{problem}.py"
    committed = (REPO_ROOT / source_rel).read_text()
    _write(tmp_path / ".gitignore", ".challenges/\n")
    _write(tmp_path / "src/algo/__init__.py", "")
    _write(tmp_path / f"src/algo/{topic}/__init__.py", "")
    _write(tmp_path / source_rel, committed)
    _write(tmp_path / test_rel, (REPO_ROOT / test_rel).read_text())
    _commit_fixture(tmp_path)

    metadata, _, _ = practice.prepare_session(tmp_path, "comments", topic, problem)
    candidate_path = tmp_path / str(metadata["source"])
    candidate = _reference_target_only(candidate_path.read_text(), committed, target)
    candidate_path.write_text(candidate)

    assert all(
        not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        or node.name != omitted_helper
        for node in ast.parse(candidate).body
    )
    assert practice.run_tests(tmp_path, metadata) != 0


def test_repl_exposes_only_target_and_omits_committed_helpers(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(practice_repo / practice.WORKSPACE_REL),
            str(practice_repo / "src"),
        ]
    )
    code = (
        "import runpy\n"
        f"ns = runpy.run_path({str(practice_repo / str(metadata['repl']))!r})\n"
        "assert 'solve' in ns\n"
        "assert '_support' not in ns\n"
        "assert 'alternate' not in ns\n"
        "assert not hasattr(ns['candidate'], '_support')\n"
        "assert not hasattr(ns['candidate'], 'alternate')\n"
    )

    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=practice_repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr


def test_generated_repl_runs_candidate_code_in_an_actual_interactive_process(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _implement_with_candidate_test(
        practice_repo,
        metadata,
        '"""Visit the values once and return their sum."""',
    )

    proc = subprocess.run(
        [sys.executable, "-i", str(practice_repo / str(metadata["repl"]))],
        cwd=practice_repo,
        env=practice._practice_env(practice_repo),
        input="assert solve([1, 2]) == 3\nprint('REPL_OK')\nexit()\n",
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "REPL_OK" in proc.stdout


def test_pytest_args_use_the_complete_reference_module(practice_repo: Path) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )

    args = practice._pytest_args(practice_repo, metadata)
    assert args[args.index("-c") + 1] == os.devnull
    assert args[args.index("--rootdir") + 1] == str(practice_repo)
    assert "--noconftest" in args
    assert args[args.index("-p") + 1] == "practice_plugin"
    assert str(metadata["reference_test"]) in args
    assert all("::" not in arg for arg in args)


def test_modified_reference_tests_are_refused_before_pytest(
    practice_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _complete_session(practice_repo, metadata)
    reference = practice_repo / str(metadata["reference_test"])
    reference.write_text("def test_false_pass() -> None:\n    assert True\n")

    def unexpected_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("pytest must not run with edited reference tests")

    monkeypatch.setattr(practice, "_execute_test_run", unexpected_run)
    with pytest.raises(practice.PracticeError, match="differ from committed HEAD"):
        practice.run_tests(practice_repo, metadata)


def test_metadata_rejects_noncanonical_paths(practice_repo: Path) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "reacto", "arrays", "first"
    )
    metadata["source"] = "src/algo/arrays/first.py"
    (practice_repo / ".challenges/workspace/session.json").write_text(
        json.dumps(metadata) + "\n"
    )

    with pytest.raises(practice.PracticeError, match="source is not canonical"):
        practice.current_metadata(practice_repo)


def test_metadata_rejects_symlinked_workspace(practice_repo: Path) -> None:
    practice.prepare_session(practice_repo, "reacto", "arrays", "first")
    workspace = practice_repo / practice.WORKSPACE_REL
    real = workspace.with_name("workspace-real")
    workspace.rename(real)
    workspace.symlink_to(real, target_is_directory=True)

    with pytest.raises(practice.PracticeError, match="workspace cannot be a symlink"):
        practice.current_metadata(practice_repo)


@pytest.mark.parametrize("operation", ["start", "log", "complete", "finish_non_editor"])
def test_symlinked_private_state_never_writes_outside_repository(
    practice_repo: Path, operation: str
) -> None:
    outside = practice_repo.with_name(f"{practice_repo.name}-{operation}-outside")
    outside.mkdir()
    (practice_repo / practice.STATE_REL).symlink_to(outside, target_is_directory=True)

    def action() -> object:
        if operation == "start":
            return practice.prepare_session(
                practice_repo, "comments", "arrays", "first"
            )
        if operation == "log":
            return practice.log_rep(
                practice_repo,
                "talk arrays/first C1 L1 A1 R1 P1 h0 trace the edge",
            )
        if operation == "complete":
            return practice.complete_problem(practice_repo, "arrays", "first")
        return practice.finish_non_editor(
            practice_repo,
            "arrays",
            "first",
            "talk arrays/first C1 L1 A1 R1 P1 h0 trace the edge",
        )

    with pytest.raises(practice.PracticeError, match="cannot be a symlink"):
        action()

    assert list(outside.iterdir()) == []


def test_symlinked_private_log_and_lock_are_refused(practice_repo: Path) -> None:
    state = practice_repo / practice.STATE_REL
    state.mkdir()
    outside = practice_repo.with_name(f"{practice_repo.name}-state-files-outside")
    outside.mkdir()
    (state / "reps.md").symlink_to(outside / "reps.md")

    with pytest.raises(practice.PracticeError, match=r"reps\.md cannot be a symlink"):
        practice.log_rep(
            practice_repo,
            "talk arrays/first C1 L1 A1 R1 P1 h0 trace the edge",
        )
    assert not (outside / "reps.md").exists()

    (state / "reps.md").unlink()
    (state / ".practice.lock").unlink()
    (state / ".practice.lock").symlink_to(outside / "lock")
    with pytest.raises(practice.PracticeError, match="lock cannot be a symlink"):
        practice.complete_problem(practice_repo, "arrays", "first")
    assert not (outside / "lock").exists()


def test_closeout_recovery_confines_every_destination_before_replay(
    practice_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    original_replace = practice._replace_file

    class InjectedCrash(BaseException):
        pass

    def crash_after_journal(path: Path, text: str) -> None:
        original_replace(path, text)
        if path == practice_repo / practice.JOURNAL_REL:
            raise InjectedCrash

    monkeypatch.setattr(practice, "_replace_file", crash_after_journal)
    with pytest.raises(InjectedCrash):
        practice.finish_session(practice_repo, metadata, "trace the edge")
    assert (practice_repo / practice.JOURNAL_REL).is_file()
    assert not (practice_repo / ".challenges/reps.md").exists()
    assert not (practice_repo / ".challenges/progress.md").exists()

    monkeypatch.setattr(practice, "_replace_file", original_replace)
    workspace = practice_repo / practice.WORKSPACE_REL
    workspace.rename(workspace.with_name("workspace-preserved"))
    outside = practice_repo.with_name(f"{practice_repo.name}-recovery-outside")
    outside.mkdir()
    workspace.symlink_to(outside, target_is_directory=True)

    with pytest.raises(practice.PracticeError, match="workspace cannot be a symlink"):
        practice.current_metadata(practice_repo)

    assert list(outside.iterdir()) == []
    assert not (practice_repo / ".challenges/reps.md").exists()
    assert not (practice_repo / ".challenges/progress.md").exists()
    assert (practice_repo / practice.JOURNAL_REL).is_file()


@pytest.mark.parametrize("field", ["source", "plugin"])
def test_metadata_rejects_symlinked_required_file(
    practice_repo: Path, field: str
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "reacto", "arrays", "first"
    )
    path = practice_repo / str(metadata[field])
    path.unlink()
    path.symlink_to(practice_repo / "src/algo/arrays/first.py")

    with pytest.raises(
        practice.PracticeError, match="required file is missing or unconfined"
    ):
        practice.current_metadata(practice_repo)


def test_invalid_partial_workspace_is_archived_and_rebuilt(
    practice_repo: Path,
) -> None:
    workspace = practice_repo / ".challenges/workspace"
    _write(workspace / "partial.txt", "candidate work\n")

    metadata, action, archived = practice.prepare_session(
        practice_repo, "reacto", "arrays", "first"
    )

    assert action == "created"
    assert archived is not None
    assert (archived / "partial.txt").read_text() == "candidate work\n"
    assert metadata["schema"] == 5


def test_failed_build_never_replaces_the_visible_workspace(
    practice_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "reacto", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(candidate.read_text() + "\n# preserve me\n")

    def fail_candidate_test(*_args: object, **_kwargs: object) -> str:
        raise OSError("injected render failure")

    monkeypatch.setattr(practice, "_candidate_test", fail_candidate_test)
    with pytest.raises(OSError, match="injected render failure"):
        practice.prepare_session(practice_repo, "clarp", "arrays", "second", fresh=True)

    assert "preserve me" in candidate.read_text()
    assert not list((practice_repo / ".challenges").glob(".workspace-*.tmp"))


def test_finished_session_starts_a_distinct_new_rep(practice_repo: Path) -> None:
    first, _, _ = practice.prepare_session(practice_repo, "reacto", "arrays", "first")
    practice.finish_session(practice_repo, first, "trace before optimizing")

    second, action, archived = practice.prepare_session(
        practice_repo, "reacto", "arrays", "first"
    )

    assert action == "created"
    assert archived is not None
    assert second["session_id"] != first["session_id"]


def test_stale_session_cannot_close_a_new_workspace(practice_repo: Path) -> None:
    first, _, _ = practice.prepare_session(practice_repo, "reacto", "arrays", "first")
    practice.prepare_session(practice_repo, "reacto", "arrays", "second", fresh=True)

    with pytest.raises(practice.PracticeError, match="stale rep session"):
        practice.finish_session(practice_repo, first, "trace before optimizing")


def test_stale_pass_receipt_closes_as_reflect_without_claiming_a_test(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(practice_repo, "clarp", "arrays", "first")
    _complete_session(practice_repo, metadata)
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        candidate.read_text().replace("return sum(values)", "return 0")
    )

    assert practice.finish_session(practice_repo, metadata, "trace the failure") == 0

    finished = practice.current_metadata(practice_repo)
    assert finished["finish_state"] == "REFLECT"
    assert finished["test_outcome"] == "not_run"
    assert set(finished["test_inputs_before"]) == set(practice.TEST_INPUT_KEYS)
    assert set(finished["test_inputs_after"]) == set(practice.TEST_INPUT_KEYS)


@pytest.mark.parametrize("outcome", ["failed", "timeout"])
def test_fresh_nonpassing_receipt_is_preserved_on_unfinished_close(
    practice_repo: Path,
    outcome: str,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _implement_with_candidate_test(practice_repo, metadata)
    practice._write_test_receipt(
        practice_repo,
        metadata,
        outcome,
        practice._test_input_digests(practice_repo, metadata),
    )

    assert practice.finish_session(practice_repo, metadata, "trace the failure") == 0

    finished = practice.current_metadata(practice_repo)
    assert finished["finish_state"] == "REFLECT"
    assert finished["test_outcome"] == outcome


def test_distinct_sessions_keep_duplicate_human_readable_reps(
    practice_repo: Path,
) -> None:
    first, _, _ = practice.prepare_session(practice_repo, "comments", "arrays", "first")
    practice.finish_session(practice_repo, first, "trace the edge")
    second, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    practice.finish_session(practice_repo, second, "trace the edge")

    reps = (practice_repo / ".challenges/reps.md").read_text().splitlines()
    assert len(reps) == 2
    assert reps[0] == reps[1]


@pytest.mark.parametrize("crash_name", ["reps.md", "progress.md", "session.json"])
def test_closeout_journal_recovers_each_sequential_replace_exactly_once(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    crash_name: str,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    original_replace = practice._replace_file

    class InjectedCrash(BaseException):
        pass

    crashed = False

    def crash_after_replace(path: Path, text: str) -> None:
        nonlocal crashed
        original_replace(path, text)
        if path.name == crash_name and not crashed:
            crashed = True
            raise InjectedCrash

    monkeypatch.setattr(practice, "_replace_file", crash_after_replace)
    with pytest.raises(InjectedCrash):
        practice.finish_session(practice_repo, metadata, "trace the edge")
    assert (practice_repo / practice.JOURNAL_REL).is_file()

    monkeypatch.setattr(practice, "_replace_file", original_replace)
    finished = practice.current_metadata(practice_repo)
    assert finished["finished_at"]
    assert not (practice_repo / practice.JOURNAL_REL).exists()
    assert practice.finish_session(practice_repo, metadata, "trace the edge") == 0
    assert len((practice_repo / ".challenges/reps.md").read_text().splitlines()) == 1
    assert (
        len((practice_repo / ".challenges/progress.md").read_text().splitlines()) == 1
    )


@pytest.mark.parametrize("crash_name", ["reps.md", "progress.md", "session.json"])
def test_non_editor_closeout_recovers_prepared_lifecycle_exactly_once(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    crash_name: str,
) -> None:
    practice.prepare_open_target(practice_repo, "arrays", "first")
    line = "talk arrays/first C1 L1 A1 R1 P1 h0 trace the edge"
    original_replace = practice._replace_file

    class InjectedCrash(BaseException):
        pass

    crashed = False

    def crash_after_replace(path: Path, text: str) -> None:
        nonlocal crashed
        original_replace(path, text)
        if path.name == crash_name and not crashed:
            crashed = True
            raise InjectedCrash

    monkeypatch.setattr(practice, "_replace_file", crash_after_replace)
    with pytest.raises(InjectedCrash):
        practice.finish_non_editor(practice_repo, "arrays", "first", line)
    assert (practice_repo / practice.JOURNAL_REL).is_file()

    monkeypatch.setattr(practice, "_replace_file", original_replace)
    recovered = practice.current_metadata(practice_repo)
    assert recovered["prepared_only"] is True
    assert recovered["presented_at"]
    assert not (practice_repo / practice.JOURNAL_REL).exists()
    assert practice.finish_non_editor(practice_repo, "arrays", "first", line) == 0
    assert len((practice_repo / ".challenges/reps.md").read_text().splitlines()) == 1
    assert (
        len((practice_repo / ".challenges/progress.md").read_text().splitlines()) == 1
    )


@pytest.mark.parametrize("changed_key", ["reference_test", "plugin"])
def test_test_result_is_stale_when_any_non_candidate_input_changes(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_key: str,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _implement_with_candidate_test(practice_repo, metadata)

    def mutating_run(
        root: Path, current: dict[str, Any], before: dict[str, str]
    ) -> practice.TestRun:
        path = practice_repo / str(metadata[changed_key])
        path.write_text(path.read_text() + "\n# changed during test\n")
        return practice.TestRun(
            returncode=0,
            before=before,
            after=practice._test_input_digests(root, current),
            completed=True,
        )

    monkeypatch.setattr(practice, "_execute_test_run", mutating_run)

    assert practice.run_tests(practice_repo, metadata) == 3
    if changed_key == "plugin":
        assert (
            practice.current_metadata(practice_repo)["session_id"]
            == metadata["session_id"]
        )


def test_candidate_collection_input_race_aborts_without_a_receipt(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _implement_with_candidate_test(practice_repo, metadata)

    def mutating_collection(
        root: Path, current: dict[str, Any], before: dict[str, str]
    ) -> practice.CandidateCollectionRun:
        candidate_test = root / str(current["candidate_test"])
        candidate_test.write_text(candidate_test.read_text() + "\n# changed\n")
        return practice.CandidateCollectionRun(
            returncode=0,
            before=before,
            after=practice._candidate_collection_input_digests(root, current),
            collected=1,
        )

    def unexpected_prepare(*_args: object, **_kwargs: object) -> dict[str, str]:
        raise AssertionError("unstable collection must not prepare locked tests")

    monkeypatch.setattr(practice, "_execute_candidate_collection", mutating_collection)
    monkeypatch.setattr(practice, "_prepare_test_run", unexpected_prepare)

    assert practice.run_tests(practice_repo, metadata) == 3
    assert "collection inputs changed" in capsys.readouterr().err
    assert not practice._test_receipt_path(practice_repo).exists()


def test_candidate_tests_run_without_holding_the_state_lock(
    practice_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _complete_session(practice_repo, metadata)

    def nested_state_write(
        root: Path, current: dict[str, Any], before: dict[str, str]
    ) -> practice.TestRun:
        assert practice.complete_problem(root, "arrays", "second") == 0
        return practice.TestRun(
            returncode=0,
            before=before,
            after=practice._test_input_digests(root, current),
            completed=True,
        )

    monkeypatch.setattr(practice, "_execute_test_run", nested_state_write)

    assert practice.run_tests(practice_repo, metadata) == 0


def _spawn_test_process_tree(
    child_lock: Path, *, parent_returncode: int | None, child_ignores_term: bool
) -> subprocess.Popen[bytes]:
    signal_setup = (
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n" if child_ignores_term else ""
    )
    child_source = (
        "import fcntl\n"
        "import os\n"
        "import signal\n"
        "import time\n"
        "from pathlib import Path\n"
        f"{signal_setup}"
        'path = Path(os.environ["PRACTICE_CHILD_LOCK"])\n'
        'with path.open("w") as handle:\n'
        "    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)\n"
        '    handle.write(f"{os.getpid()} {os.getpgrp()}")\n'
        "    handle.flush()\n"
        "    time.sleep(30)\n"
    )
    parent_end = (
        f"raise SystemExit({parent_returncode})"
        if parent_returncode is not None
        else "time.sleep(30)"
    )
    parent_source = (
        "import os\n"
        "import subprocess\n"
        "import sys\n"
        "import time\n"
        "from pathlib import Path\n"
        f"child_source = {child_source!r}\n"
        'subprocess.Popen([sys.executable, "-c", child_source])\n'
        'path = Path(os.environ["PRACTICE_CHILD_LOCK"])\n'
        "deadline = time.monotonic() + 2\n"
        "while (not path.is_file() or not path.read_text()) "
        "and time.monotonic() < deadline:\n"
        "    time.sleep(0.01)\n"
        f"{parent_end}\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", parent_source],
        env=os.environ | {"PRACTICE_CHILD_LOCK": str(child_lock)},
        start_new_session=True,
    )
    deadline = time.monotonic() + 2
    while (not child_lock.is_file() or not child_lock.read_text()) and (
        time.monotonic() < deadline
    ):
        time.sleep(0.01)
    if not child_lock.is_file() or not child_lock.read_text():
        practice._sweep_test_process_group(proc)
        raise AssertionError("background child did not acquire its lock")
    return proc


@pytest.mark.parametrize("parent_returncode", [0, 7])
def test_completed_parent_sweeps_background_child(
    tmp_path: Path, parent_returncode: int
) -> None:
    child_lock = tmp_path / f"completed-{parent_returncode}-child.lock"
    proc = _spawn_test_process_tree(
        child_lock,
        parent_returncode=parent_returncode,
        child_ignores_term=False,
    )
    try:
        assert practice._wait_for_test_process(proc, 2)
        assert practice._sweep_test_process_group(proc) == parent_returncode
        assert _wait_for_lock_release(child_lock)
    finally:
        if proc.returncode is None:
            practice._sweep_test_process_group(proc)
        _kill_lock_holder(child_lock)


def test_timeout_sweeps_term_ignoring_background_child(tmp_path: Path) -> None:
    child_lock = tmp_path / "timeout-child.lock"
    proc = _spawn_test_process_tree(
        child_lock, parent_returncode=None, child_ignores_term=True
    )
    started = time.monotonic()
    try:
        assert not practice._wait_for_test_process(proc, 1)
        assert practice._sweep_test_process_group(proc) != 0
        assert time.monotonic() - started < 4
        assert _wait_for_lock_release(child_lock)
    finally:
        if proc.returncode is None:
            practice._sweep_test_process_group(proc)
        _kill_lock_holder(child_lock)


def test_group_sweep_never_signals_after_leader_was_reaped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = subprocess.Popen(
        [sys.executable, "-c", "pass"],
        start_new_session=True,
    )
    assert proc.wait(timeout=2) == 0

    def unexpected_signal(_group: int, _signal: int) -> None:
        pytest.fail("reaped process group must never be signaled")

    monkeypatch.setattr(os, "killpg", unexpected_signal)
    assert practice._sweep_test_process_group(proc) == 0


def test_hanging_candidate_test_is_killed_at_the_bounded_deadline(
    practice_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _complete_session(practice_repo, metadata)
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        candidate.read_text().replace("return sum(values)", "while True:\n        pass")
    )
    monkeypatch.setenv("PRACTICE_TEST_TIMEOUT_SECONDS", "1")

    started = time.monotonic()
    assert practice.run_tests(practice_repo, metadata) == 124
    assert time.monotonic() - started < 5
    assert "finished_at" not in practice.current_metadata(practice_repo)


def test_finish_does_not_claim_a_stale_previous_success(
    practice_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _complete_session(practice_repo, metadata)
    source = practice_repo / str(metadata["source"])
    source.write_text(source.read_text() + "\n# Changed since the explicit run.\n")

    def unexpected_pytest(*_args: object, **_kwargs: object) -> None:
        pytest.fail("stale closeout must not implicitly run tests")

    monkeypatch.setattr(practice, "_execute_test_run", unexpected_pytest)
    assert (
        practice.finish_session(practice_repo, metadata, "review the changed notes")
        == 0
    )
    finished = practice.current_metadata(practice_repo)
    assert finished["finish_state"] == "REFLECT"
    assert finished["test_outcome"] == "not_run"


def test_stale_test_inputs_abort_before_closeout_journal(
    practice_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    _complete_session(practice_repo, metadata)

    original_prepare = practice._prepare_test_run

    def mutate_after_preflight(
        root: Path, current: dict[str, Any], *, require_unlocked: bool
    ) -> dict[str, str]:
        before = original_prepare(root, current, require_unlocked=require_unlocked)
        reference = practice_repo / str(metadata["reference_test"])
        reference.write_text(reference.read_text() + "\n# changed during closeout\n")
        return cast("dict[str, str]", before)

    monkeypatch.setattr(practice, "_prepare_test_run", mutate_after_preflight)
    with pytest.raises(practice.PracticeError, match="inputs changed"):
        practice.finish_session(practice_repo, metadata, "trace the edge")

    assert not (practice_repo / practice.JOURNAL_REL).exists()
    assert not (practice_repo / ".challenges/reps.md").exists()
    assert not (practice_repo / ".challenges/progress.md").exists()
    assert "finished_at" not in practice.current_metadata(practice_repo)


def test_finish_non_editor_requires_exact_parsed_draw(practice_repo: Path) -> None:
    line = "talk arrays/second C1 L1 A1 R1 P1 h0 trace the edge"

    with pytest.raises(practice.PracticeError, match="slug does not match"):
        practice.finish_non_editor(practice_repo, "arrays", "first", line)
    assert not (practice_repo / ".challenges/reps.md").exists()

    assert practice.finish_non_editor(practice_repo, "arrays", "second", line) == 0
    assert "arrays/second" in (practice_repo / ".challenges/reps.md").read_text()


def test_successful_non_editor_closeout_is_retry_idempotent(
    practice_repo: Path,
) -> None:
    line = "talk arrays/second C1 L1 A1 R1 P1 h0 trace the edge"

    assert practice.finish_non_editor(practice_repo, "arrays", "second", line) == 0
    assert practice.finish_non_editor(practice_repo, "arrays", "second", line) == 0

    reps = (practice_repo / ".challenges/reps.md").read_text().splitlines()
    progress = (practice_repo / ".challenges/progress.md").read_text().splitlines()
    assert len(reps) == 1
    assert len(progress) == 1
    assert not (practice_repo / practice.NON_EDITOR_RECEIPTS_REL).exists()


def test_non_editor_recovery_is_idempotent_across_date_rollover(
    practice_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    line = "talk arrays/second C1 L1 A1 R1 P1 h0 trace the edge"
    real_date = practice.date

    class FrozenDate:
        current = real_date(2026, 7, 15)

        @classmethod
        def today(cls) -> object:
            return cls.current

    monkeypatch.setattr(practice, "date", FrozenDate)
    original_replace = practice._replace_file

    class InjectedCrash(BaseException):
        pass

    crashed = False

    def crash_after_rep(path: Path, text: str) -> None:
        nonlocal crashed
        original_replace(path, text)
        if path.name == "reps.md" and not crashed:
            crashed = True
            raise InjectedCrash

    monkeypatch.setattr(practice, "_replace_file", crash_after_rep)
    with pytest.raises(InjectedCrash):
        practice.finish_non_editor(practice_repo, "arrays", "second", line)

    FrozenDate.current = real_date(2026, 7, 16)
    monkeypatch.setattr(practice, "_replace_file", original_replace)
    # An unrelated command may be the first process to recover the journal.
    assert practice.complete_problem(practice_repo, "arrays", "first") == 0
    assert not (practice_repo / practice.JOURNAL_REL).exists()
    assert practice.finish_non_editor(practice_repo, "arrays", "second", line) == 0
    FrozenDate.current = real_date(2026, 7, 17)
    assert practice.finish_non_editor(practice_repo, "arrays", "second", line) == 0

    reps = (practice_repo / ".challenges/reps.md").read_text().splitlines()
    progress = (practice_repo / ".challenges/progress.md").read_text().splitlines()
    assert len(reps) == 1
    assert reps[0].startswith("- 2026-07-15 ")
    assert progress == [
        "- [x] arrays/second 2026-07-15",
        "- [x] arrays/first 2026-07-16",
    ]
    receipt = practice._non_editor_receipts(practice_repo)
    assert receipt == [
        {
            "fingerprint": hashlib.sha256(
                f"arrays\0second\0{line}".encode()
            ).hexdigest(),
            "recovered_on": "2026-07-16",
        }
    ]

    # Once the short recovery window expires, identical practice is a new rep.
    FrozenDate.current = real_date(2026, 7, 18)
    assert practice.finish_non_editor(practice_repo, "arrays", "second", line) == 0
    assert practice.finish_non_editor(practice_repo, "arrays", "second", line) == 0
    reps = (practice_repo / ".challenges/reps.md").read_text().splitlines()
    progress = (practice_repo / ".challenges/progress.md").read_text().splitlines()
    assert len(reps) == 2
    assert reps[1].startswith("- 2026-07-18 ")
    assert progress == [
        "- [x] arrays/first 2026-07-16",
        "- [x] arrays/second 2026-07-18",
    ]
    assert not (practice_repo / practice.JOURNAL_REL).exists()


def test_non_editor_receipts_are_bounded(practice_repo: Path) -> None:
    receipts = practice._non_editor_receipts_path(practice_repo)
    fingerprints = [
        f"{index:064x}" for index in range(practice.MAX_NON_EDITOR_RECEIPTS + 3)
    ]
    for fingerprint in fingerprints:
        practice._replace_file(
            receipts,
            practice._non_editor_receipt_text(practice_repo, fingerprint, "2026-07-15"),
        )

    assert [
        receipt["fingerprint"]
        for receipt in practice._non_editor_receipts(practice_repo)
    ] == fingerprints[-practice.MAX_NON_EDITOR_RECEIPTS :]


def test_reference_cli_without_args_uses_current_session(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    practice.prepare_session(practice_repo, "comments", "arrays", "first")
    monkeypatch.setattr(practice, "ROOT", practice_repo)
    monkeypatch.setattr(sys, "argv", ["practice_workspace.py", "reference"])

    assert practice.main() == 0
    assert "secret = _support(values)" in capsys.readouterr().out


def test_present_cli_prepares_and_opens_exact_tabs_before_printing_prompt(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    events: list[str] = []
    real_select = practice.select_problem
    real_prepare = practice.prepare_open_target
    real_mark = practice.mark_presentation_started
    real_present = practice.present_problem

    def select_once(
        root: Path, topic: str | None = None, problem: str | None = None
    ) -> tuple[str, str]:
        events.append("select")
        return cast("tuple[str, str]", real_select(root, topic, problem))

    def prepare(root: Path, topic: str, problem: str) -> dict[str, Any]:
        events.append("prepare")
        return cast("dict[str, Any]", real_prepare(root, topic, problem))

    def open_tabs(_root: Path, metadata: dict[str, Any]) -> bool:
        events.append("open")
        assert metadata["paradigm"] == "prepared"
        assert practice._is_presentation_active(metadata)
        return True

    def mark(root: Path, metadata: dict[str, Any]) -> dict[str, Any]:
        events.append("mark")
        return cast("dict[str, Any]", real_mark(root, metadata))

    def present(root: Path, topic: str, problem: str) -> str:
        events.append("present")
        return cast("str", real_present(root, topic, problem))

    monkeypatch.delenv("PRACTICE_NO_OPEN", raising=False)
    monkeypatch.setattr(practice, "ROOT", practice_repo)
    monkeypatch.setattr(practice, "select_problem", select_once)
    monkeypatch.setattr(practice, "prepare_open_target", prepare)
    monkeypatch.setattr(practice, "mark_presentation_started", mark)
    monkeypatch.setattr(practice, "open_session", open_tabs)
    monkeypatch.setattr(practice, "present_problem", present)
    monkeypatch.setattr(
        sys,
        "argv",
        ["practice_workspace.py", "present", "arrays", "first"],
    )

    assert practice.main() == 0
    assert events == ["prepare", "select", "mark", "open", "present"]
    assert "PRACTICE: arrays/first" in capsys.readouterr().out
    assert practice._is_presentation_active(practice.current_metadata(practice_repo))


def test_present_cli_does_not_print_a_cold_prompt_when_editor_open_fails(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    presented = False

    def unexpected_present(_root: Path, _topic: str, _problem: str) -> str:
        nonlocal presented
        presented = True
        return "must not print"

    monkeypatch.delenv("PRACTICE_NO_OPEN", raising=False)
    monkeypatch.setattr(practice, "ROOT", practice_repo)
    monkeypatch.setattr(practice.shutil, "which", lambda _name: None)
    monkeypatch.setattr(practice, "present_problem", unexpected_present)
    monkeypatch.setattr(
        sys,
        "argv",
        ["practice_workspace.py", "present", "arrays", "first"],
    )

    assert practice.main() == 1
    assert not presented
    output = capsys.readouterr().out
    assert "PRACTICE:" not in output
    assert "NEXT: Restore the code CLI, then run just interview arrays first." in output
    assert practice._is_presentation_active(practice.current_metadata(practice_repo))
    with pytest.raises(practice.PracticeError, match="active non-editor rep"):
        practice.prepare_study_snapshot(practice_repo, "arrays", "first")


def test_open_cli_forwards_an_exact_pair_to_the_safe_workspace(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[dict[str, Any]] = []

    def record_open(_root: Path, metadata: dict[str, Any]) -> bool:
        opened.append(metadata)
        return True

    monkeypatch.setattr(practice, "ROOT", practice_repo)
    monkeypatch.setattr(practice, "open_session", record_open)
    monkeypatch.setattr(
        sys,
        "argv",
        ["practice_workspace.py", "open", "arrays", "first"],
    )

    assert practice.main() == 0
    assert len(opened) == 1
    assert opened[0]["paradigm"] == "prepared"
    assert opened[0]["source"] == ".challenges/workspace/first.py"
    assert opened[0]["candidate_test"] == (
        ".challenges/workspace/test_first_candidate.py"
    )


def test_open_cli_reports_editor_launch_failure(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(practice, "ROOT", practice_repo)
    monkeypatch.setattr(practice, "open_session", lambda _root, _metadata: False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["practice_workspace.py", "open", "arrays", "first"],
    )

    assert practice.main() == 1


def test_study_cli_prepares_before_opening_and_forwards_the_exact_pair(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[object] = []
    manifest = {"topic": "arrays", "problem": "first"}

    def prepare(root: Path, topic: str, problem: str) -> dict[str, Any]:
        events.append(("prepare", root, topic, problem))
        return manifest

    def open_snapshot(root: Path, value: dict[str, Any]) -> bool:
        events.append(("open", root, value))
        return True

    monkeypatch.setattr(practice, "ROOT", practice_repo)
    monkeypatch.setattr(practice, "prepare_study_snapshot", prepare)
    monkeypatch.setattr(practice, "open_study_snapshot", open_snapshot)
    monkeypatch.setattr(
        sys,
        "argv",
        ["practice_workspace.py", "study", "arrays", "first"],
    )

    assert practice.main() == 0
    assert events == [
        ("prepare", practice_repo, "arrays", "first"),
        ("open", practice_repo, manifest),
    ]


def test_study_cli_returns_failure_when_editor_open_fails(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(practice, "ROOT", practice_repo)
    monkeypatch.setattr(
        practice,
        "prepare_study_snapshot",
        lambda _root, _topic, _problem: {},
    )
    monkeypatch.setattr(
        practice,
        "open_study_snapshot",
        lambda _root, _manifest: False,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["practice_workspace.py", "study", "arrays", "first"],
    )

    assert practice.main() == 1


def test_start_cli_reports_editor_launch_failure_before_presenting_state(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("PRACTICE_NO_OPEN", raising=False)
    monkeypatch.setattr(practice, "ROOT", practice_repo)
    monkeypatch.setattr(practice, "open_session", lambda _root, _metadata: False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "practice_workspace.py",
            "start",
            "comments",
            "arrays",
            "first",
        ],
    )

    assert practice.main() == 1
    assert "STATE:" not in capsys.readouterr().out
    assert practice.current_metadata(practice_repo)["topic"] == "arrays"


def test_open_session_rejects_an_unknown_focus(practice_repo: Path) -> None:
    metadata = practice.prepare_open_target(practice_repo, "arrays", "first")

    with pytest.raises(practice.PracticeError, match="unknown editor focus: other"):
        practice.open_session(practice_repo, metadata, focus="other")


def test_start_cli_forwards_tests_first_focus(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    focused: list[str] = []

    def open_tabs(
        _root: Path, _metadata: dict[str, Any], *, focus: str = "source"
    ) -> bool:
        focused.append(focus)
        return True

    monkeypatch.delenv("PRACTICE_NO_OPEN", raising=False)
    monkeypatch.setattr(practice, "ROOT", practice_repo)
    monkeypatch.setattr(practice, "open_session", open_tabs)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "practice_workspace.py",
            "start",
            "comments",
            "arrays",
            "first",
            "--focus",
            "test",
        ],
    )

    assert practice.main() == 0
    assert focused == ["test"]
    output = capsys.readouterr().out
    assert "STATE: THINK" in output
    assert "NEXT: Start in TEST with one focused candidate test." in output
    assert "do not implement yet" in output


def test_tests_first_start_holds_lock_through_exact_tab_open(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_prepare = practice.prepare_session
    replacement_started = Event()
    replacement_finished = Event()
    replacement: list[Any] = []

    def replace_workspace() -> tuple[dict[str, Any], str, Path | None]:
        replacement_started.set()
        try:
            return cast(
                "tuple[dict[str, Any], str, Path | None]",
                real_prepare(
                    practice_repo,
                    "comments",
                    "arrays",
                    "second",
                    fresh=True,
                ),
            )
        finally:
            replacement_finished.set()

    def prepare(
        root: Path,
        paradigm: str,
        topic: str | None,
        problem: str | None,
        *,
        fresh: bool = False,
    ) -> tuple[dict[str, Any], str, Path | None]:
        result = cast(
            "tuple[dict[str, Any], str, Path | None]",
            real_prepare(root, paradigm, topic, problem, fresh=fresh),
        )
        replacement.append(executor.submit(replace_workspace))
        assert replacement_started.wait(timeout=1)
        assert not replacement_finished.wait(timeout=0.2)
        return result

    def open_tabs(
        root: Path,
        metadata: dict[str, Any],
        *,
        focus: str = "source",
    ) -> bool:
        assert focus == "test"
        assert not replacement_finished.is_set()
        assert practice.current_metadata(root)["session_id"] == metadata["session_id"]
        return True

    monkeypatch.delenv("PRACTICE_NO_OPEN", raising=False)
    monkeypatch.setattr(practice, "ROOT", practice_repo)
    monkeypatch.setattr(practice, "prepare_session", prepare)
    monkeypatch.setattr(practice, "open_session", open_tabs)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "practice_workspace.py",
            "start",
            "comments",
            "arrays",
            "first",
            "--focus",
            "test",
        ],
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        assert practice.main() == 0

    assert replacement_finished.is_set()
    assert replacement[0].result()[0]["problem"] == "second"


@pytest.mark.parametrize("paradigm", tuple(practice.PARADIGMS))
def test_start_cli_opens_before_presenting_for_every_editor_paradigm(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    paradigm: str,
) -> None:
    events: list[str] = []

    def open_tabs(_root: Path, _metadata: dict[str, Any]) -> bool:
        events.append("open")
        return True

    def print_start(
        _root: Path,
        _metadata: dict[str, Any],
        _action: str,
        _archived: Path | None,
    ) -> None:
        events.append("present")

    monkeypatch.delenv("PRACTICE_NO_OPEN", raising=False)
    monkeypatch.setattr(practice, "ROOT", practice_repo)
    monkeypatch.setattr(practice, "open_session", open_tabs)
    monkeypatch.setattr(practice, "_print_start", print_start)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "practice_workspace.py",
            "start",
            paradigm,
            "arrays",
            "first",
        ],
    )

    assert practice.main() == 0
    assert events == ["open", "present"]


def test_resumed_start_does_not_present_candidate_docstring_or_derive_state(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    sentinel = "PRIVATE_CANDIDATE_DOCSTRING_SENTINEL_7E6B25C9"
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(
        candidate.read_text().replace(
            "Problem:\n",
            f"Problem:\n    {sentinel}\n",
            1,
        )
    )
    assert sentinel in candidate.read_text()
    workspace = practice_repo / practice.WORKSPACE_REL
    before = _workspace_snapshot(workspace)

    monkeypatch.setattr(practice, "ROOT", practice_repo)
    monkeypatch.setattr(practice, "open_session", lambda _root, _metadata: True)
    monkeypatch.setattr(
        practice,
        "show_next",
        lambda _root, _metadata: pytest.fail(
            "resume must wait for an explicit just practice-next boundary"
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "practice_workspace.py",
            "start",
            "comments",
            "arrays",
            "first",
        ],
    )

    assert practice.main() == 0

    output = capsys.readouterr().out
    assert "arrays / first" in output
    assert sentinel not in output
    assert "STATE:" not in output
    assert "After an explicit save, run just practice-next." in output
    assert _workspace_snapshot(workspace) == before


@pytest.mark.parametrize("command", ["next", "test"])
def test_prepared_tabs_emit_exact_activation_commands_until_a_mode_starts(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    practice.prepare_open_target(practice_repo, "arrays", "first")
    monkeypatch.setattr(practice, "ROOT", practice_repo)
    monkeypatch.setattr(sys, "argv", ["practice_workspace.py", command])

    assert practice.main() == 2
    error = capsys.readouterr().err
    assert "no editor rep is active" in error
    assert "IMPLEMENT: just practice-start comments arrays first" in error
    assert "TESTS_FIRST: just practice-start-tests arrays first" in error
    assert "NEXT: run one emitted transition when ready" in error
    assert "<paradigm>" not in error


def test_open_cli_without_args_preserves_current_reopen_behavior(
    practice_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current, _, _ = practice.prepare_session(practice_repo, "clarp", "arrays", "first")
    opened: list[dict[str, Any]] = []

    def record_open(_root: Path, metadata: dict[str, Any]) -> bool:
        opened.append(metadata)
        return True

    monkeypatch.setattr(practice, "ROOT", practice_repo)
    monkeypatch.setattr(practice, "open_session", record_open)
    monkeypatch.setattr(sys, "argv", ["practice_workspace.py", "open"])

    assert practice.main() == 0
    assert opened == [current]


def test_history_limits_refuse_without_destroying_current_workspace(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    candidate = practice_repo / str(metadata["source"])
    candidate.write_text(candidate.read_text() + "\n# preserve me\n")
    history = practice_repo / practice.HISTORY_REL
    for index in range(practice.MAX_HISTORY_ENTRIES):
        (history / f"old-{index}").mkdir(parents=True)

    with pytest.raises(practice.PracticeError, match="history has reached"):
        practice.prepare_session(
            practice_repo, "comments", "arrays", "second", fresh=True
        )
    assert "preserve me" in candidate.read_text()


def test_history_byte_limit_refuses_without_moving_current_workspace(
    practice_repo: Path,
) -> None:
    metadata, _, _ = practice.prepare_session(
        practice_repo, "comments", "arrays", "first"
    )
    history_file = practice_repo / practice.HISTORY_REL / "old" / "large.bin"
    history_file.parent.mkdir(parents=True)
    with history_file.open("wb") as handle:
        handle.truncate(practice.MAX_HISTORY_BYTES + 1)

    with pytest.raises(practice.PracticeError, match="exceed 512 MiB"):
        practice.prepare_session(
            practice_repo, "comments", "arrays", "second", fresh=True
        )
    assert (practice_repo / str(metadata["source"])).is_file()
