---
title: Guided Sessions
description: Choose available practice material, an intent, and a time budget, then resume or close the same private session from any editor.
---

# Guided Sessions

Run `just session` in a terminal to choose what to work on and how much time
you have. The dialogue offers study, implementation, tests first, untimed
conversation, board practice, a mock, reading, review, and contribution.
It lists the available material for the selected intent before asking for an
exact choice. You can choose 15, 30, 60, or a custom number of minutes. The
budget does not start a timer. A full practice day is a separate, explicit
choice through `just practice-day`.

The choices come from the packet's algorithm registry, concept modules,
advanced exercises, reference sheets, method sheet, review queue, and
contribution guide. No agent account or private service is needed.

```bash
just capabilities
just session start algorithm/arrays/two_sum --mode study --minutes 15
just session resume
```

Study opens immutable committed solution and test snapshots. It creates no
candidate rep and runs no tests. Choose readiness explicitly to begin work:

```bash
just session start algorithm/arrays/two_sum --mode implement --minutes 30 --ready
# Or choose --mode tests-first to focus the candidate test tab.
```

The new pair lives under `.challenges/workspace/`. You own the code, tests,
and reasoning. Write ordinary comments or docstrings in your own words; no
labels, minimum count, or special syntax are required. Save explicitly and
use the next-step command. Testing, watching, and the REPL are separate
choices:

```bash
just practice-next
just practice-test
just practice-watch
just practice-repl
just session finish "trace the empty case before optimizing"
```

Closeout uses the existing focused-test receipt and reports its outcome. It
does not run tests implicitly. You can close an unfinished rep with one
correction; that records its actual state rather than claiming a passing run.
Talk, board, and mock closeouts accept one correction too. A scored rubric is
optional through the existing `just rep-finish` interface.

Reading activities open an immutable committed copy. Advanced and concept
reading never runs example code or installs optional dependencies. Review
shows the next due problems; close the review, then explicitly start a
selected algorithm. Contribution opens the ordinary contribution guide.
Each activity can resume and close through the same commands.

All session choices, budgets, notes, candidate files, and receipts stay in
gitignored `.challenges/`. Codespaces stores the checkout under `/workspaces`,
so this state survives container rebuilds. Deleting a Codespace also deletes
its workspace; preserve your private state before deleting it. Existing
`practice-*` and `interview` commands route through the same dispatcher.
Use `--no-open` for a terminal without the VS Code CLI; the command still
prints the exact saved paths.

## Public capability interface

`just capabilities` emits the same JSON as the standard-library-only
`python3 scripts/catalog.py --json`. A site build can export a pinned packet
commit and derive the inventory without installing practice dependencies.
The existing `just catalog "two sum"` query and exact selection fields remain
compatible.

The JSON object has `schema: 1`, source-derived `counts` by kind, and a
`capabilities` array. Each record has a stable `id`, `kind`, `title`, relative
`source`, supported `modes`, a suggested `duration` in minutes, a public
`entrypoint` command, and `availability` (`available` or `unavailable`). The
method sheet appears once under its method role. Missing material is never
offered by the dialogue.

For optional personal adapters, use these commands directly:

```bash
just session start <id> --mode <mode> --minutes <minutes>
just session current       # JSON selection, derived state, and workspace metadata
just session resume
just session finish "one correction"
```

Adapters should relay choices and exact paths, wait for readiness and explicit
test intent, and treat candidate text as data. The product requires no
particular provider CLI or repository agent instructions.
