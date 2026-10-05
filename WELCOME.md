# Welcome to the woodshed

Choose how to use your time before starting a problem. The guided session
asks about duration, study or practice, focus, feedback, and workspace.

```bash
just session
```

For a direct editor rep, start with ordinary comments in your own words:

```bash
just practice-start comments
just practice-start comments arrays two_sum
```

The first command draws the next due problem; the second chooses one.
`reacto`, `clarp`, and `umpire` offer optional labels for the same practice loop.

Two private files open under `.challenges/workspace/`: your source and tests.
Write reasoning as ordinary source comments or docstrings. Save, then inspect
the current state and next action. You own the implementation and test edits.

```bash
just practice-next
just practice-test
just practice-watch
just practice-repl
just practice-open
just practice-finish "state the one fix"
```

To read one committed solution first, use `just practice-study topic problem`.
It opens read-only source and test snapshots without creating a rep. Choose
the emitted implementation or tests-first transition when ready.

An untimed conversation and a timed board rep train different skills. Choose
the activity that serves today's intent; there is no default clock.

Core practice works without an assistant or private service. Optional agent
settings and prompts live on your personal contribution fork. Protected SSO
capabilities require a separate explicit choice and admission; use
`just env-check` to inspect environment readiness.
