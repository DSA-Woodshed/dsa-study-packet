# dsa-study-packet: algorithm practice
set dotenv-load := false

bazel := env_var_or_default("BAZEL_BIN", "bazelisk")
export USE_BAZEL_VERSION := `cat .bazelversion`

hook_mirror := "https://raw.githubusercontent.com/DSA-Woodshed/.github/83f555ca5cb0ee01fa35cb6947f1b0e80228d332/githooks"

default:
    @just --list

# Locked product dependencies; never loads optional agent tooling.
deps-sync:
    uv sync --extra dev --locked

# Prepare a fork checkout and the locked product environment.
setup: hooks-install deps-sync env-setup

# Install the organization mirror while keeping the global hook layer chained.
hooks-install:
    git config core.hooksPath .githooks
    git config remote.pushDefault origin
    @if git remote | grep -qx upstream; then git remote set-url --push upstream DISABLED-fork-first; fi
    @if [ "$(git config --get commit.gpgsign || true)" != true ]; then printf 'Configure signed commits before contributing; see CONTRIBUTING.md\n'; fi

# Compare exact bytes with the organization mirror; a file:// fixture works offline.
hooks-check mirror=hook_mirror:
    #!/usr/bin/env bash
    set -euo pipefail
    hook_fixture=$(mktemp -d)
    trap 'rm -rf "$hook_fixture"' EXIT
    for hook_name in _lib.sh pre-commit commit-msg pre-push test.sh; do
        curl --fail --silent --show-error --location {{ quote(mirror) }}/"$hook_name" -o "$hook_fixture/$hook_name"
        if ! cmp -s ".githooks/$hook_name" "$hook_fixture/$hook_name"; then
            printf 'Hook drift: .githooks/%s differs from the organization mirror\n' "$hook_name" >&2
            exit 1
        fi
    done
    printf 'Shared hook mirror parity passed\n'

hooks-test:
    bash .githooks/test.sh

# Maintainer gate, with one declared environment dependency through lint/test.
check mirror=hook_mirror: (hooks-check mirror) hooks-test maintainer-check source-contracts integration-test

# Public environment and explicitly selected protected capabilities.
env-setup: deps-sync
    .venv/bin/python scripts/environment.py setup

env-check:
    .venv/bin/python scripts/environment.py check

protected-capability:
    .venv/bin/python scripts/environment.py protected

env-test: deps-sync
    .venv/bin/python -m pytest -q tests/test_environment.py

# ──────────────────────────────────────────────
# Testing
# ──────────────────────────────────────────────

# Run all tests
test *args: deps-sync
    uv run pytest {{ args }}

# Run tests for a specific topic
test-topic topic:
    uv run pytest tests/{{ topic }}/ -v

# Run tests in watch mode (re-runs on file change)
test-watch *args:
    watchexec -e py -- uv run pytest {{ args }}

# Study a topic: run tests in watch mode for a specific topic
study topic:
    watchexec -e py -w src/algo/{{ topic }} -w tests/{{ topic }} -- uv run pytest tests/{{ topic }}/ -v

# Run concept module tests (installs optional deps)
test-concepts *args:
    uv run --extra concepts pytest tests/concepts/ -v {{ args }}

# Study a concept: run concept tests in watch mode
study-concept:
    watchexec -e py -w src/concepts -w tests/concepts -- uv run --extra concepts pytest tests/concepts/ -v

# Run benchmark suite
bench *args:
    uv run pytest -m bench --benchmark-enable --benchmark-sort=fullname {{ args }}

# Run tests with coverage (statement + branch) over the algo + concept sources
cov *args:
    uv run pytest --cov=src/algo --cov=src/concepts --cov-branch --cov-report=term-missing {{ args }}

# ──────────────────────────────────────────────
# Code quality
# ──────────────────────────────────────────────

# Maintainer lint uses the same graph as the full gate.
maintainer-lint:
    {{ quote(bazel) }} test //tools:lint //tools:typecheck

lint: maintainer-lint source-contracts

# The public maintained graph: unit tests, Ruff and mypy.
maintainer-check:
    {{ quote(bazel) }} test //tools:check

# Git/editor/container/command integration tests share one explicit lane list.
integration-test: deps-sync
    uv run python tools/run_integration.py

# Source contracts need tracked checkout facts; they do not rerun unit tests.
source-contracts: deps-sync
    uv run python scripts/check_public_boundary.py
    uv run python scripts/check_doc_counts.py
    uv run python scripts/check_contribution_boundary.py
    uv run python scripts/check_onboarding.py
    uv run python scripts/check_migration_readiness.py
    uv run python scripts/check_clarity.py
    uv run python scripts/check_no_stubs.py
    uv run python scripts/validate_appendix_schema.py

# Check that private prep material has not entered the public packet tree
public-boundary:
    uv run python scripts/check_public_boundary.py
    uv run python scripts/check_doc_counts.py

# Check owner-sensitive links and the retired packet Pages boundary
migration-readiness:
    uv run python scripts/check_migration_readiness.py

# Resolve an already-pushed disposable branch to an exact Codespaces URL/SHA
codespaces-acceptance-plan branch repository="":
    uv run python scripts/codespaces_acceptance.py plan --branch {{ quote(branch) }} --repository {{ quote(repository) }}

# Assert the exact repo and SHA from inside a genuinely new Codespace
codespaces-acceptance-verify expected_sha repository:
    uv run python scripts/codespaces_acceptance.py verify --expected-sha {{ quote(expected_sha) }} --repository {{ quote(repository) }}

# Format code with ruff
fmt *paths="src/ tests/": deps-sync
    uv run ruff format {{ paths }}
    uv run ruff check --fix {{ paths }}

# Check formatting without modifying files
fmt-check *paths="src/ tests/": deps-sync
    uv run ruff format --check {{ paths }}

# ──────────────────────────────────────────────
# Scaffolding
# ──────────────────────────────────────────────

# Scaffold a new problem: just new <topic> <problem_name>
new topic problem:
    #!/usr/bin/env bash
    set -euo pipefail

    src_dir="src/algo/{{ topic }}"
    test_dir="tests/{{ topic }}"
    src_file="${src_dir}/{{ problem }}.py"
    test_file="${test_dir}/test_{{ problem }}.py"

    mkdir -p "$src_dir" "$test_dir"

    # Ensure __init__.py files exist
    touch "src/algo/__init__.py"
    [ -f "${src_dir}/__init__.py" ] || touch "${src_dir}/__init__.py"
    [ -f "tests/__init__.py" ] || touch "tests/__init__.py"
    [ -f "${test_dir}/__init__.py" ] || touch "${test_dir}/__init__.py"

    if [ -f "$src_file" ]; then
        echo "Already exists: $src_file"
        exit 1
    fi

    # Source file
    cat > "$src_file" << 'PYEOF'
    """{{ topic }} / {{ problem }}

    Problem:
        TODO: describe the problem

    Approach:
        TODO: describe your approach

    Complexity:
        Time:  O(?)
        Space: O(?)
    """


    def solve() -> None:
        raise NotImplementedError
    PYEOF
    # Remove leading whitespace from heredoc
    sed -i '' 's/^    //' "$src_file" 2>/dev/null || sed -i 's/^    //' "$src_file"

    # Test file
    cat > "$test_file" << 'PYEOF'
    """Tests for {{ topic }} / {{ problem }}."""

    from algo.{{ topic }}.{{ problem }} import solve


    class TestSolve:
        def test_placeholder(self) -> None:
            """TODO: replace with real tests."""
            assert True
    PYEOF
    sed -i '' 's/^    //' "$test_file" 2>/dev/null || sed -i 's/^    //' "$test_file"

    echo "Created:"
    echo "  $src_file"
    echo "  $test_file"

# ──────────────────────────────────────────────
# PDF generation
# ──────────────────────────────────────────────

# Convert a single reference sheet to PDF
pdf file:
    pandoc "{{ file }}" -o "{{ without_extension(file) }}.pdf" \
        --pdf-engine=tectonic \
        -V geometry:margin=0.75in \
        -V fontsize=10pt \
        -V colorlinks=true

# Convert all reference sheets to PDF
pdf-all:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p reference-sheets/pdf
    for f in reference-sheets/*.md; do
        name="$(basename "${f%.md}")"
        echo "Converting $f → reference-sheets/pdf/${name}.pdf"
        pandoc "$f" -o "reference-sheets/pdf/${name}.pdf" \
            --pdf-engine=tectonic \
            -V geometry:margin=0.75in \
            -V fontsize=10pt \
            -V colorlinks=true
    done
    echo "Done. PDFs in reference-sheets/pdf/"

# Generate and compile the public packet from declared inputs.
packet:
    {{ quote(bazel) }} build //:booklet
    mkdir -p docs/assets
    cp bazel-bin/booklet.pdf booklet.pdf
    cp bazel-bin/booklet.pdf docs/assets/booklet.pdf

# Compatibility name routes to the sole booklet graph.
pdf-booklet: packet

# Explicitly selected remote capability. Missing attachment is unavailable.
remote-compile *targets:
    #!/usr/bin/env bash
    set -euo pipefail
    set -a; [ -f .env.flywheel.local ] && . ./.env.flywheel.local; set +a
    if [ -z "${BAZEL_REMOTE_CACHE:-}" ]; then
        echo "Remote build unavailable: select a protected cache capability first. Use just packet for a public local build." >&2
        exit 78
    fi
    targets={{ quote(targets) }}; [ -n "$targets" ] || targets="//:booklet"
    exec just flywheel-build $targets

remote-build *targets:
    #!/usr/bin/env bash
    set -euo pipefail
    exec just remote-compile {{ quote(targets) }}

remote-test *targets:
    #!/usr/bin/env bash
    set -euo pipefail
    set -a; [ -f .env.flywheel.local ] && . ./.env.flywheel.local; set +a
    if [ -z "${BAZEL_REMOTE_CACHE:-}" ]; then
        echo "Remote tests unavailable: select a protected cache capability first. Use just maintainer-check for public local validation." >&2
        exit 78
    fi
    targets={{ quote(targets) }}; [ -n "$targets" ] || targets="//tools:check"
    exec just flywheel-test $targets

remote-check:
    #!/usr/bin/env bash
    set -euo pipefail
    set -a; [ -f .env.flywheel.local ] && . ./.env.flywheel.local; set +a
    if [ -z "${BAZEL_REMOTE_CACHE:-}" ]; then
        echo "Remote capability unavailable: no cache attachment selected." >&2
        exit 78
    fi
    just flywheel-doctor
    just flywheel-verify

# Build the overlay-pattern demo (examples/overlay-demo) -> wrapped PDF
# Its source is generated in the same declared public graph.
overlay-demo:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Composing overlay demo via the cache-first front door..."
    {{ quote(bazel) }} build //examples/overlay-demo:study_packet_example
    echo "-> bazel-bin/examples/overlay-demo/study_packet_example.pdf"

# ──────────────────────────────────────────────
# Documentation (MkDocs)
# ──────────────────────────────────────────────

# Generate algorithm-visualizer traces (SSOT frame data)
traces:
    uv run python scripts/gen_traces.py

# Serve docs locally with live reload
docs: traces
    uv run --extra docs mkdocs serve

# Build docs site
docs-build: traces
    uv run --extra docs mkdocs build

# ──────────────────────────────────────────────
# Practice tracking
# ──────────────────────────────────────────────

# Mark a challenge as completed
challenge-done topic problem:
    @uv run python scripts/session.py workspace complete {{ quote(topic) }} {{ quote(problem) }}

# Show challenge progress
challenge-progress:
    @cat .challenges/progress.md 2>/dev/null || echo "No challenges completed yet."

# Spaced-repetition: show the next problems due for review (default 5)
study-spaced n="5":
    @uv run python scripts/study_schedule.py {{ quote(n) }}

# List exact practice pairs, optionally matching natural problem names.
catalog query="":
    #!/usr/bin/env bash
    set -euo pipefail
    query={{ quote(query) }}
    if [ -z "$query" ]; then
        exec uv run python scripts/catalog.py
    fi
    exec uv run python scripts/catalog.py "$query"

# Machine-readable capabilities derived from the packet sources.
capabilities:
    @uv run python scripts/catalog.py --json

# Choose intent and time interactively, or start/resume/finish one exact activity.
[positional-arguments]
session *args:
    @uv run python scripts/session.py "$@"

# Print one sheet-11 practice day as a timed block.
practice-day day="12":
    @uv run python scripts/practice_day.py {{ quote(day) }}

# Compatibility alias for an explicitly selected Day 12 block.
study-tonight: (practice-day "12")

# Preflight: check the practice toolchain and optional editor/agent helpers.
doctor:
    @python3 scripts/doctor.py

# Start or resume an editor-first rep (reacto, clarp, umpire, or comments).
# Omit topic/problem to draw the next spaced-repetition problem.
practice-start paradigm topic="" problem="":
    #!/usr/bin/env bash
    set -euo pipefail
    paradigm={{ quote(paradigm) }}
    topic={{ quote(topic) }}
    problem={{ quote(problem) }}
    if { [ -n "$topic" ] && [ -z "$problem" ]; } || { [ -z "$topic" ] && [ -n "$problem" ]; }; then
        supplied=${topic:-$problem}
        printf 'practice: provide both topic and problem, or omit both for a draw\n'
        printf 'MATCH: one natural name, %s, is not an exact pair\n' "$supplied"
        printf 'NEXT: just catalog "%s"\n' "$supplied"
        exit 2
    fi
    if [ -z "$topic" ] && [ -z "$problem" ]; then
        exec uv run python scripts/session.py workspace start "$paradigm"
    fi
    exec uv run python scripts/session.py workspace start "$paradigm" "$topic" "$problem"

# Start a normal comments rep with the candidate test tab focused.
practice-start-tests topic problem:
    @uv run python scripts/session.py workspace start comments {{ quote(topic) }} {{ quote(problem) }} --focus test

# Start a fresh rep and archive any current workspace.
practice-new paradigm topic="" problem="":
    #!/usr/bin/env bash
    set -euo pipefail
    paradigm={{ quote(paradigm) }}
    topic={{ quote(topic) }}
    problem={{ quote(problem) }}
    if { [ -n "$topic" ] && [ -z "$problem" ]; } || { [ -z "$topic" ] && [ -n "$problem" ]; }; then
        supplied=${topic:-$problem}
        printf 'practice: provide both topic and problem, or omit both for a draw\n'
        printf 'MATCH: one natural name, %s, is not an exact pair\n' "$supplied"
        printf 'NEXT: just catalog "%s"\n' "$supplied"
        exit 2
    fi
    if [ -z "$topic" ] && [ -z "$problem" ]; then
        exec uv run python scripts/session.py workspace start "$paradigm" --fresh
    fi
    exec uv run python scripts/session.py workspace start "$paradigm" "$topic" "$problem" --fresh

# Show target, candidate-test, and focused-test receipt status for the current rep.
practice-status:
    @uv run python scripts/session.py workspace status

# Print one machine-readable state and one next action for the current rep.
practice-next:
    @uv run python scripts/session.py workspace next

# Run only the current problem's reference tests plus candidate-owned tests.
practice-test:
    @uv run python scripts/session.py workspace test

# Re-run the current rep's focused tests whenever its workspace changes.
practice-watch:
    @uv run python scripts/session.py workspace watch

# Load the current candidate implementation in an interactive Python prompt.
practice-repl:
    @uv run python scripts/session.py workspace repl

# Open current candidate tabs, or prepare and open one exact safe pair.
practice-open topic="" problem="":
    #!/usr/bin/env bash
    set -euo pipefail
    topic={{ quote(topic) }}
    problem={{ quote(problem) }}
    if { [ -n "$topic" ] && [ -z "$problem" ]; } || { [ -z "$topic" ] && [ -n "$problem" ]; }; then
        supplied=${topic:-$problem}
        printf 'practice: provide both topic and problem, or omit both for the current rep\n'
        printf 'MATCH: one natural name, %s, is not an exact pair\n' "$supplied"
        printf 'NEXT: just catalog "%s"\n' "$supplied"
        exit 2
    fi
    if [ -z "$topic" ] && [ -z "$problem" ]; then
        exec uv run python scripts/session.py workspace open
    fi
    exec uv run python scripts/session.py workspace open "$topic" "$problem"

# Open immutable committed source and test snapshots without starting a rep.
practice-study topic="" problem="":
    #!/usr/bin/env bash
    set -euo pipefail
    topic={{ quote(topic) }}
    problem={{ quote(problem) }}
    if { [ -n "$topic" ] && [ -z "$problem" ]; } || { [ -z "$topic" ] && [ -n "$problem" ]; }; then
        supplied=${topic:-$problem}
        printf 'practice: practice-study requires one exact topic/problem pair\n'
        printf 'MATCH: one natural name, %s, is not an exact pair\n' "$supplied"
        printf 'NEXT: just catalog "%s"\n' "$supplied"
        exit 2
    fi
    if [ -z "$topic" ] && [ -z "$problem" ]; then
        printf 'practice: practice-study requires one exact topic/problem pair\n'
        printf 'NEXT: just catalog\n'
        exit 2
    fi
    exec uv run python scripts/session.py workspace study "$topic" "$problem"

# Print the current workspace metadata for public integrations.
practice-current:
    @uv run python scripts/session.py workspace current

# Pair the private rep note and spaced-review update for the current workspace.
practice-finish note:
    @uv run python scripts/session.py workspace finish {{ quote(note) }}

# Open safe candidate tabs, then print a cold statement. Omit both values to draw.
practice-present topic="" problem="":
    #!/usr/bin/env bash
    set -euo pipefail
    topic={{ quote(topic) }}
    problem={{ quote(problem) }}
    if { [ -n "$topic" ] && [ -z "$problem" ]; } || { [ -z "$topic" ] && [ -n "$problem" ]; }; then
        supplied=${topic:-$problem}
        printf 'practice: provide both topic and problem, or omit both for a draw\n'
        printf 'MATCH: one natural name, %s, is not an exact pair\n' "$supplied"
        printf 'NEXT: just catalog "%s"\n' "$supplied"
        exit 2
    fi
    if [ -z "$topic" ] && [ -z "$problem" ]; then
        exec uv run python scripts/session.py workspace present
    fi
    exec uv run python scripts/session.py workspace present "$topic" "$problem"

# Print the current or explicitly selected committed reference implementation.
practice-reference topic="" problem="":
    #!/usr/bin/env bash
    set -euo pipefail
    topic={{ quote(topic) }}
    problem={{ quote(problem) }}
    if { [ -n "$topic" ] && [ -z "$problem" ]; } || { [ -z "$topic" ] && [ -n "$problem" ]; }; then
        supplied=${topic:-$problem}
        printf 'practice: provide both topic and problem, or omit both for a draw\n'
        printf 'MATCH: one natural name, %s, is not an exact pair\n' "$supplied"
        printf 'NEXT: just catalog "%s"\n' "$supplied"
        exit 2
    fi
    if [ -z "$topic" ] && [ -z "$problem" ]; then
        exec uv run python scripts/session.py workspace reference
    fi
    exec uv run python scripts/session.py workspace reference "$topic" "$problem"

# Board/talk compatibility entry point through the public session dispatcher.
interview topic="" problem="":
    #!/usr/bin/env bash
    set -euo pipefail
    topic={{ quote(topic) }}
    problem={{ quote(problem) }}
    if [ -z "$topic" ] && [ -z "$problem" ]; then
        exec uv run python scripts/session.py workspace present
    fi
    exec uv run python scripts/session.py workspace present "$topic" "$problem"

# Compatibility entry point: plain comment-driven isolated editor rep.
interview-comment topic problem:
    @uv run python scripts/session.py workspace start comments {{ quote(topic) }} {{ quote(problem) }}

# Log one practice rep (appends to gitignored .challenges/reps.md)
rep line:
    @uv run python scripts/session.py workspace log {{ quote(line) }}

# Atomically log and schedule one non-editor rep.
rep-finish topic problem line:
    @uv run python scripts/session.py workspace finish-non-editor {{ quote(topic) }} {{ quote(problem) }} {{ quote(line) }}

import? "justfile.flywheel"
