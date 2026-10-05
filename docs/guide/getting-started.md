---
title: Getting Started
description: Start an editor-first interview rep with source comments or docstrings, candidate-owned code, focused tests, and one concrete correction.
---

# Getting Started

The practice workspace holds your comments, code, and tests. The site and
packet hold solutions and references. Default reps are cold; explicit study
opens a committed solution first. Practice work is never committed.

!!! tip "The loop"
    Start with ordinary source comments or docstrings, or choose a named
    framework. Save and continue explicitly, implement and test, then keep one
    correction.

## Your first ten minutes

1. Open Codespaces or your local Dev Container. Basic practice needs no
   private credential or assistant subscription.
2. Run `just session`. Choose how much time you have, study or practice,
   your focus, feedback, and where to work.
3. There is no clock unless you choose one. An untimed conversation and
   a timed board rep train different skills.
4. Stop with one useful correction; the next review remains in your queue.

## 1. Start a rep

[:octicons-mark-github-24: Open in GitHub Codespaces](https://codespaces.new/DSA-Woodshed/dsa-study-packet?quickstart=1){ .md-button .md-button--primary }

Use the guided session or start a comments-mode rep directly:

```bash
just session
just practice-start comments
just practice-start comments arrays two_sum
```

Without a topic, the direct practice command draws the next due problem.
Ordinary source comments and docstrings need no required labels. Optional
`reacto`, `clarp`, and `umpire` modes offer named scaffolding for the same loop.
An assistant selected on your contribution fork can use these public commands.
It has no separate practice engine or product authority.

To study first, open read-only source and test snapshots. Start a candidate
pair only when ready to implement or write tests. Snapshot tests are reading
material, not the focused runner.

```bash
just practice-study linked_lists lru_cache
just practice-start comments linked_lists lru_cache
just practice-start-tests linked_lists lru_cache
```

## 2. Write before code

Starting a rep opens:

```text
.challenges/workspace/<problem>.py
.challenges/workspace/test_<problem>_candidate.py
```

In the source file:

1. Restate the problem and note any questions.
2. Write one example and one edge case.
3. Name an approach and its expected time and space cost.
4. Save, then run `just practice-next`.
5. Implement the solution, using comments alongside code where they help.
6. Add focused tests, trace one example, and update comments that no longer
   match the code.

Write your comments in the source file. `just practice-next` reads saved work
and reports one current state and next action. You own source and test edits;
chosen feedback tools can discuss that work.

The workspace is gitignored. Starting a different rep archives the previous
workspace under `.challenges/history/`. Starting the same unfinished rep
resumes it; starting after closeout creates a new rep. The complete
implementation under `src/algo/` remains unchanged.

## 3. Use focused feedback

```bash
just practice-next       # current state and one next action
just practice-test       # this problem's reference tests plus your tests
just practice-watch      # rerun the focused tests on changes
just practice-repl       # load your implementation interactively
just practice-open       # reopen both files
```

Test, watch, and REPL follow the saved practice state. The explicit
save-and-continue boundary keeps you in control of when the interviewer reads
your work.

## 4. Stop cleanly

Name one win and the one fix you want next time.
Then close the private log and spaced-review update together:

```bash
just practice-finish "trace the example before running tests"
```

The goal is a useful correction, not a solve count. An unfinished
implementation or failing test can still produce a good rep. `just practice-test` is the explicit test action. Finish records the existing
receipt without silently running tests. Missing or stale evidence remains
visible in the closeout; an earlier closeout can record `not_run`.

For a talk-only or board rep, use one atomic closeout with the exact draw:

```bash
just rep-finish arrays two_sum \
  "talk arrays/two_sum C2 L2 A1 R0 P0 h1 trace before optimizing"
```

Change the values to match the rep. The command logs it and schedules review
together.

## 5. Run locally

Clone the repository and reopen it in the supplied VS Code Dev Container for
the closest match to Codespaces. Nix users can run `direnv allow`. With Python
3.14+, `uv`, and `just` already installed, use `uv sync --extra dev`.

```bash
just doctor
just test
just lint
```

See [Local VS Code](local-practice.md) for setup details.

## Choose the right surface

| Goal | Surface |
|------|---------|
| Reason, code, and test | editor rep |
| Read a complete implementation and its tests | explicit study snapshot |
| Form a plan without editor pressure | untimed conversation |
| Practice narration under a clock | timed board or observed mock |
| Select a pattern | [decision tree](when-to-use-what.md) |
| Review a finished technique | [algorithm library](../algorithms/index.md) |
| Work a curated sequence | [learning paths](learning-paths.md) |
