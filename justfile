# dsa-study-packet: algorithm practice
set dotenv-load := false

default:
    @just --list

# ──────────────────────────────────────────────
# Testing
# ──────────────────────────────────────────────

# Run all tests
test *args:
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

# Run ruff linter + mypy type checker + repo guards
lint:
    uv run ruff check src/ tests/ scripts/
    uv run mypy
    uv run python scripts/check_public_boundary.py
    uv run python scripts/check_doc_counts.py
    uv run python scripts/check_agent_instructions.py
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
codespaces-acceptance-plan branch:
    uv run python scripts/codespaces_acceptance.py plan --branch {{ quote(branch) }}

# Assert the exact repo and SHA from inside a genuinely new Codespace
codespaces-acceptance-verify expected_sha:
    uv run python scripts/codespaces_acceptance.py verify --expected-sha {{ quote(expected_sha) }}

# Regenerate agent instruction surfaces from the AGENTS.md persona region
gen-agents:
    uv run python scripts/gen_agent_instructions.py

# Format code with ruff
fmt:
    uv run ruff format src/ tests/
    uv run ruff check --fix src/ tests/

# Check formatting without modifying files
fmt-check:
    uv run ruff format --check src/ tests/

# ──────────────────────────────────────────────
# Agent skills (standalone; not wired into lint)
# ──────────────────────────────────────────────

# List each .claude skill's frontmatter name and description
skills-list:
    @for s in .claude/skills/*/SKILL.md; do \
      name=$(awk '/^name:/ {print $2; exit}' "$s"); \
      desc=$(awk '/^description:/ {sub(/^description:[[:space:]]*/, ""); print; exit}' "$s"); \
      printf "%-16s %s\n" "$name" "$desc" | cut -c1-200; \
    done

# Fail if any .claude skill is missing a name or description frontmatter field
skills-validate:
    #!/usr/bin/env bash
    set -euo pipefail
    fail=0
    for s in .claude/skills/*/SKILL.md; do
        name=$(awk '/^name:/ {print $2; exit}' "$s")
        desc=$(awk '/^description:/ {print $0; exit}' "$s")
        if [ -z "$name" ]; then
            printf 'FAIL %s: missing frontmatter name\n' "$s"
            fail=1
        fi
        if [ -z "$desc" ]; then
            printf 'FAIL %s: missing frontmatter description\n' "$s"
            fail=1
        fi
    done
    if [ "$fail" -ne 0 ]; then
        exit 1
    fi
    echo "skills-validate passed"

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

# Generate printable PDF booklet (decision trees + 1 algo per page)
pdf-booklet:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Generating booklet.tex..."
    uv run python scripts/gen_booklet.py
    echo "Compiling booklet.pdf with tectonic..."
    tectonic booklet.tex
    mkdir -p docs/assets
    cp booklet.pdf docs/assets/booklet.pdf
    echo "Done -> booklet.pdf and docs/assets/booklet.pdf"

# Build the latest printable study packet from source code and notes
packet: pdf-booklet

# --------------------------------------------------
# GloriousFlywheel cache-first Bazel (sole entrypoint)
# --------------------------------------------------
# `import? "justfile.flywheel"` (added by `flywheel-frontdoor-kit --patch-justfile`)
# provides flywheel-doctor/verify/enroll/consumer-env + the gloriousflywheel-bazel
# wrapper recipes. The recipes below are the repo-local cache-first front door:
# they delegate to the wrapper when BAZEL_REMOTE_CACHE is attached and degrade to
# a local disk_cache build otherwise. Never call raw bazel -- always `just remote-*`.

_remote-prepare:
    @echo "Generating booklet.tex..."
    @uv run python scripts/gen_booklet.py

# Cache-first compile of a target set (default //:booklet, the neutral packet).
remote-compile *targets: _remote-prepare
    #!/usr/bin/env bash
    set -euo pipefail
    set -a; [ -f .env.flywheel.local ] && . ./.env.flywheel.local; set +a
    targets="{{ targets }}"; [ -n "$targets" ] || targets="//:booklet"
    if [ -n "${BAZEL_REMOTE_CACHE:-}" ]; then
        exec just flywheel-build $targets
    fi
    echo "compatibility-local-only (BAZEL_REMOTE_CACHE unset) -> local disk_cache build: $targets"
    exec "${BAZEL_BIN:-bazelisk}" build $targets

# Cache-first build (default //:booklet).
remote-build *targets:
    #!/usr/bin/env bash
    set -euo pipefail
    targets="{{ targets }}"
    exec just remote-compile $targets

# Cache-first bazel test (default //...). `just test` runs the real uv/pytest suite.
remote-test *targets: _remote-prepare
    #!/usr/bin/env bash
    set -euo pipefail
    set -a; [ -f .env.flywheel.local ] && . ./.env.flywheel.local; set +a
    targets="{{ targets }}"; [ -n "$targets" ] || targets="//..."
    if [ -n "${BAZEL_REMOTE_CACHE:-}" ]; then
        exec just flywheel-test $targets
    fi
    echo "compatibility-local-only (BAZEL_REMOTE_CACHE unset) -> local bazel test: $targets"
    exec "${BAZEL_BIN:-bazelisk}" test $targets

# GloriousFlywheel attachment/contract gate (no build). Exits 0 when unattached.
remote-check:
    #!/usr/bin/env bash
    set -euo pipefail
    set -a; [ -f .env.flywheel.local ] && . ./.env.flywheel.local; set +a
    if [ -z "${BAZEL_REMOTE_CACHE:-}" ]; then
        echo "compatibility-local-only: BAZEL_REMOTE_CACHE unset; nothing to verify (ok)."
        exit 0
    fi
    just flywheel-doctor
    just flywheel-verify

# Build the overlay-pattern demo (examples/overlay-demo) -> wrapped PDF
# Cache-first via remote-build (no raw bazel); its front door prepares booklet.tex.
overlay-demo:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Composing overlay demo via the cache-first front door..."
    just remote-build //examples/overlay-demo:study_packet_example
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
    @uv run python scripts/practice_workspace.py complete {{ quote(topic) }} {{ quote(problem) }}

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

# Print one sheet-11 practice day as a timed block.
practice-day day="12":
    @uv run python scripts/practice_day.py {{ quote(day) }}

# Tonight's productionized Day 12 block.
study-tonight:
    @uv run python scripts/practice_day.py 12

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
        exec uv run python scripts/practice_workspace.py start "$paradigm"
    fi
    exec uv run python scripts/practice_workspace.py start "$paradigm" "$topic" "$problem"

# Start a normal comments rep with the candidate test tab focused.
practice-start-tests topic problem:
    @uv run python scripts/practice_workspace.py start comments {{ quote(topic) }} {{ quote(problem) }} --focus test

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
        exec uv run python scripts/practice_workspace.py start "$paradigm" --fresh
    fi
    exec uv run python scripts/practice_workspace.py start "$paradigm" "$topic" "$problem" --fresh

# Show target, candidate-test, and focused-test receipt status for the current rep.
practice-status:
    @uv run python scripts/practice_workspace.py status

# Print one machine-readable state and one next action for the current rep.
practice-next:
    @uv run python scripts/practice_workspace.py next

# Run only the current problem's reference tests plus candidate-owned tests.
practice-test:
    @uv run python scripts/practice_workspace.py test

# Re-run the current rep's focused tests whenever its workspace changes.
practice-watch:
    @uv run python scripts/practice_workspace.py watch

# Load the current candidate implementation in an interactive Python prompt.
practice-repl:
    @uv run python scripts/practice_workspace.py repl

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
        exec uv run python scripts/practice_workspace.py open
    fi
    exec uv run python scripts/practice_workspace.py open "$topic" "$problem"

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
    exec uv run python scripts/practice_workspace.py study "$topic" "$problem"

# Print the current rep metadata (agent/tooling interface).
practice-current:
    @uv run python scripts/practice_workspace.py current

# Pair the private rep note and spaced-review update for the current workspace.
practice-finish note:
    @uv run python scripts/practice_workspace.py finish {{ quote(note) }}

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
        exec uv run python scripts/practice_workspace.py present
    fi
    exec uv run python scripts/practice_workspace.py present "$topic" "$problem"

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
        exec uv run python scripts/practice_workspace.py reference
    fi
    exec uv run python scripts/practice_workspace.py reference "$topic" "$problem"

# Board/talk entry point: prepare/open safe candidate files, then present cold.
interview topic="" problem="":
    #!/usr/bin/env bash
    set -euo pipefail
    topic={{ quote(topic) }}
    problem={{ quote(problem) }}
    if [ -z "$topic" ] && [ -z "$problem" ]; then
        just practice-present
    else
        just practice-present "$topic" "$problem"
    fi
    echo "Interview (cold): reason out loud first; the safe candidate tabs stay visible."

# Compatibility entry point: plain comment-driven isolated editor rep.
interview-comment topic problem:
    @just practice-start comments {{ quote(topic) }} {{ quote(problem) }}

# Log one practice rep (appends to gitignored .challenges/reps.md)
rep line:
    @uv run python scripts/practice_workspace.py log {{ quote(line) }}

# Atomically log and schedule one non-editor rep.
rep-finish topic problem line:
    @uv run python scripts/practice_workspace.py finish-non-editor {{ quote(topic) }} {{ quote(problem) }} {{ quote(line) }}

import? "justfile.flywheel"
