---
title: Local VS Code
description: Run the editor-first practice loop locally with the VS Code Dev Container or a small uv and just toolchain.
---

# Local VS Code

Run the same editor-first loop on your machine. The Dev Container matches
Codespaces; a native install needs only `uv` and `just` for the core flow.

## Set up

```bash
git clone https://github.com/DSA-Woodshed/dsa-study-packet.git
cd dsa-study-packet
```

Choose one lane:

=== "Dev Container"

    Open the folder in VS Code and choose **Dev Containers: Reopen in
    Container**. The container provides `uv`, `just`, and `watchexec`.

=== "Native tools"

    Install Python 3.14+, [uv](https://docs.astral.sh/uv/), and
    [just](https://just.systems/), then run:

    ```bash
    just setup
    just doctor
    ```

    `watchexec` is optional and only needed for `just practice-watch`. Nix
    users can run `direnv allow` for the pinned toolchain. Do not run
    `.devcontainer/setup.sh` directly on a local machine.

## Start a rep

Choose an intent, a time budget, and an activity through the guided session,
or start one rep directly. Basic practice needs no private service:

```bash
just session
just practice-start comments
just practice-start comments arrays two_sum
```

Optional `reacto`, `clarp`, and `umpire` labels support the same loop.

To study one exact pair without starting a rep, open its committed snapshot:

```bash
just practice-study linked_lists lru_cache
```

When ready, start a candidate pair with source or test focus.

```bash
just practice-start comments linked_lists lru_cache
just practice-start-tests linked_lists lru_cache
```

Your source and test file open under `.challenges/workspace/`. Write ordinary
source comments or docstrings in your own words, save, then run
`just practice-next`. The comments belong in the source file and
need no prefixes, minimum count, or gate deletion. Implement the solution and
add focused tests. If the tabs do not open, the command prints their paths;
`just practice-open` tries again.

## Continue and close

```bash
just practice-next       # state and one next action
just practice-test       # reference tests plus your tests
just practice-watch      # rerun on workspace changes
just practice-repl       # interactive exploration
just practice-open       # reopen both files
just practice-finish "one fix"
```

The committed solution under `src/algo/` remains unchanged, and your workspace
stays gitignored. Run `just doctor` when the toolchain looks wrong.

Candidate tests are not sandboxed. The runner bounds test time and cleans the
pytest process group. Do not launch background daemons. Receipts detect
ordinary staleness and incomplete runs; they are workflow evidence, not a
tamper-resistant boundary.

Optional agent providers and their settings belong on the personal
contribution fork. Restore only the tools you choose; they route through the
same canonical session commands. A terminal session works without an agent.
