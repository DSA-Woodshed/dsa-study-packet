# The Woodshed Practice Contract, v4

Python is the implemented track. Additional languages need justified curricula,
tooling, and runnable acceptance evidence. Shared behavior changes bump this version.

## Thesis

Explain reasoning in source comments, implement, test, and keep one useful
correction. Source comments provide the whiteboard in a Codespace.

## Command contract

A track fronts everything through `just`:

- `just capabilities` emits the source-derived inventory as schema-1 JSON:
  `counts` by kind and `capabilities` records with `id`, `kind`, `title`,
  `source`, `modes`, `duration`, `entrypoint`, and `availability`. Availability
  describes material, not runtime readiness; duration is in minutes.
  On 2026-10-05 the inventory has 96 entries: 72 algorithms, seven concepts, four advanced
  exercises, ten references, one method, one review, and one contribution guide.
  `python3 scripts/catalog.py --json` needs only the standard library.
- `just session` asks for intent, a 15/30/60/custom-minute budget, and an exact
  available activity. Modes include study, implement, tests-first, talk, board,
  mock, read, review, and contribute. Budgets do not start timers.
  `just session start <id>
  --mode <mode> --minutes <minutes>` makes the choice explicit. A study-to-work
  transition requires `--ready`; `start` and `resume` accept `--no-open`.
- `just session resume` reopens the same saved activity; `current` reports
  schema-1 JSON with `selection`, `state`, and applicable `workspace` metadata.
  `just session finish "<one correction>"` closes that activity. Reading,
  review, and contribution create no candidate rep; a practice day remains an
  explicit `just practice-day` choice.
- Compatibility commands use the same dispatcher: `practice-start
  comments|reacto|clarp|umpire [topic problem]` seeds and presents candidate
  tabs; `practice-start-tests topic problem` focuses the test tab; `interview
  [topic problem]` presents or draws a talk, board, or mock prompt.
- `practice-open [topic problem]` prepares or reopens tabs without presentation;
  `practice-study topic problem` opens committed snapshots. Later implementation
  starts from a stripped pair. `catalog "<words>"` resolves choices without opening.
- `practice-next` derives state; `practice-current` reprints it; `practice-test`,
  `practice-watch`, and `practice-repl` explicitly run tests, a watcher, and a
  REPL. `practice-finish "<one fix>"` records outcome and schedules review.

Other commands retain UPPERCASE key lines such as `STATE`, `SOURCE`, `TEST`,
`NEXT`, `REVISION`, and `RECEIPT`. Catalog query readiness (`READY`, `CHOOSE`,
`NOT_FOUND`) travels as `STATE` values. Consumers relay emitted fields and
errors. Sessions carry an id; a stale id is refused rather than rebound.

## State loop

`practice-next` derives THINK, BUILD, REFLECT, or CLOSE mechanically,
without pretending to understand prose:

- THINK while the selected target holds only its docstring and cold stubs.
- BUILD on a syntax error, a missing or rebound target, cold stubs beside
  real code, or an empty or broken candidate test file.
- REFLECT once code and at least one candidate test exist, driven by the
  focused-test receipt: a failed, timed-out, or missing run asks for
  revision or a trace; a receipt made stale by later edits asks for
  reconciliation.
- CLOSE when the focused receipt is fresh and passing.

Derived CLOSE does not gate explicit closeout. `session finish` and
`practice-finish` reuse existing receipts without running tests. Unfinished
reps close with one correction and `failed`, `timeout`, or `not_run`; stale
or absent evidence yields `not_run`. Closing again does not duplicate records.
A passing closeout requires fresh correctness evidence.

Study creates no candidate rep or spaced-review entry. Its immutable snapshots come
from committed content, never dirty tracked files. Active reps and edited
prepared work block study so an answer cannot appear mid-rep; pristine tabs do
not. Snapshot tests are reading material, not an executable runner.

## Natural reasoning

Candidate reasoning lives in ordinary comments and docstrings. Comments mode
invites it; REACTO, CLARP, and UMPIRE offer optional vocabulary the candidate
may replace or delete. The harness never parses or gates reasoning prose.
Humans or chosen assistants may discuss it; candidate text, code, and tests
are learner-owned data.

## What a track owns

1. A discipline-specific corpus.
2. A candidate seeder stripping solution bodies from tracked references.
3. A language-specific resolver for existing, unrebound targets and cold stubs:
   `scripts/python_candidate_target.py` inspects code, never comments.
4. A doc-comment extractor for print and site rendering.
5. A focused property-based test harness importing candidate source.
6. A public devcontainer requiring no private credentials. Hosted lifecycle and
   protected services need separate acceptance evidence.
7. A committed study snapshot resolver independent of candidate seeding.

## Observable behavior

Candidate files, choices, budgets, and receipts stay in gitignored `.challenges/`.
Resume reopens saved work; explicit next/current commands derive its state.
Opening, testing, and recording outcomes report observable success or failure.
Agent conduct and tool configuration live on personal contribution overlays.

Talk, board, and mock sessions close with one correction through `session finish`.
`just rep-finish topic problem "<line>"` retains optional scored closeout,
using the same logging and review operations.
