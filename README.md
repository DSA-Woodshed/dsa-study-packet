# The DSA Woodshed

Company-neutral technical interview practice in a real editor. Each rep asks
you to explain the problem in comments, implement a solution, write focused
tests, and make one useful correction. Complete implementations, reference
sheets, and a printable packet remain available for explicit study.

The same material is published at
**[dsa-woodshed.space](https://dsa-woodshed.space)**. Employer-specific prep
belongs in private downstream overlays; see the
[source-of-truth contract](docs/guide/source-of-truth.md). Python is the only
runnable track. [TRACK-CONTRACT.md](TRACK-CONTRACT.md) defines its working
practice behavior. New languages require justified curriculum and runnable
acceptance evidence.

## Start in Codespaces

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/DSA-Woodshed/dsa-study-packet?quickstart=1)

When the editor opens, choose an activity from the terminal. Basic practice
needs no private credentials. Start a guided session to choose an intent,
a time budget, and an activity; optional assistants use the same commands.

```bash
just session
just practice-start comments
```

No topic is required for the practice start command. It draws the next due
problem. Choose one with `just practice-start comments arrays two_sum`.
`reacto`, `clarp`, and `umpire` are optional vocabulary choices for the same loop.

When you are ready to implement, the rep opens two gitignored files under
`.challenges/workspace/`: your source file and your test file. The committed
implementation under `src/algo/` stays unchanged.

1. Write reasoning in ordinary source comments or docstrings.
2. Save, then run `just practice-next`.
3. Implement the solution and add focused tests.
4. Save and continue again when you want the next instruction.
5. Run `just practice-test`, then close with `just practice-finish "one fix"`.

To study before starting that candidate rep, ask to read or review one named
problem:

```bash
just practice-study linked_lists lru_cache
```

The command opens read-only committed source and test snapshots. When you
are ready, choose one emitted transition:

```bash
just practice-start comments linked_lists lru_cache
just practice-start-tests linked_lists lru_cache
```

Write comments in the source file. Candidate source and tests belong to you.
Select optional agent tooling on your personal contribution fork; ordinary
practice works directly through the terminal.

The named frameworks are vocabulary choices, not grading systems. Keep their
labels, replace them, or use ordinary source comments and docstrings in your
own words. `just practice-next` reads the saved source and test files and returns one
next action. It does not grade wording; tests remain the correctness signal.

## Current-rep commands

```bash
just practice-next       # current state and one next action
just practice-test       # this problem's reference tests plus your tests
just practice-watch      # rerun the focused tests on changes
just practice-repl       # explore your implementation interactively
just practice-open       # reopen the source and test files
just practice-study linked_lists lru_cache
just practice-start-tests linked_lists lru_cache
just practice-finish "one fix"
```

Use [Practice Problems](docs/challenges/index.md) to choose a problem and
[Getting Started](docs/guide/getting-started.md) for the full loop. Untimed
conversation and timed board-style practice remain available when those are
the skills you intend to train.

## Local development

The Dev Container provides the same toolchain as Codespaces. Nix users can
enter the pinned shell with `direnv allow`.

```bash
just setup
just doctor
just test
just lint
just docs
just packet
```

`just` is the front door. `just check` runs the public maintainer graph and
runtime integration checks; `just packet` builds the printable booklet locally.
The retired Flywheel cache/profile integration has been removed. Existing
`just remote-*` names return unavailable (exit 78), even if an old profile or
cache variable is present. Remote execution needs an installed,
authenticated adopter-owned admission path and runtime evidence; neither is
supplied here. `//:booklet` is the neutral PDF composition surface for private
overlays. The tracked source also generates
local docs, algorithm pages, and reference-sheet PDFs; the reading site syncs
that content separately.

## Repository map

- `src/algo/`: tested reference implementations
- `tests/`: reference tests
- `docs/`: web docs
- `reference-sheets/`: printable method and reference material
- `.challenges/`: private, gitignored practice state
- `scripts/core42.py`: core problem catalog (historical filename)

Run `just catalog` for every exact practice pair, or search natural names with
`just catalog "anagram, 2 sum and prime"`. Run `just --list` for all recipes.
See [WELCOME.md](WELCOME.md) for the shortest first-session guide and
[CONTRIBUTING.md](CONTRIBUTING.md) for the personal-fork contribution workflow.
