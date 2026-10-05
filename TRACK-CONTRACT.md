# The Woodshed Practice Contract, v3

Python is the implemented practice track. This contract describes its public
commands and behavior. Additional languages require a justified corpus, tooling,
and runnable acceptance evidence. Shared behavior changes bump the version.

## Thesis

Each language needs its own curriculum. The shared flow is to explain your
reasoning in the source file, implement, test, and keep one useful correction.
Source comments provide the whiteboard in a Codespace.

## Command contract

A track fronts everything through `just`:

- `just practice-start comments|reacto|clarp|umpire [topic problem]` seeds
  an isolated candidate source and test pair under a gitignored workspace
  and atomically opens and presents it.
- `just interview [topic problem]` presents, or draws, a talk, board, or
  mock prompt and prepares the same candidate tabs.
- `just practice-open [topic problem]` prepares or reopens the selected
  pair without presentation; `just catalog "<words>"` resolves free words
  to one canonical pair and never opens.
- `just practice-study topic problem` opens read-only snapshots of the
  committed source and tests at one full revision. It creates no rep or
  practice record. A later implementation starts from a fresh stripped pair.
- `just practice-start-tests topic problem` starts the normal comments rep
  with its candidate test tab focused; it is not a separate test exercise.
- `just practice-next` reads the saved files and reports state; `just
  practice-current` reprints the active session; `just practice-test`,
  `practice-watch`, and `practice-repl` run focused candidate tests, a
  watcher, and a REPL; `just practice-finish "<one fix>"` records the
  outcome, closes private logs, and schedules spaced review.

Machine-readable output is UPPERCASE key lines (`STATE`, `SOURCE`, `TEST`,
`NEXT`, `START`, `QUEUE`, `QUERY`, `MATCH`, `CHOOSE`, `SUGGEST`, `OPENED`,
`OPEN_FAILED`, `STUDY_SOURCE`, `STUDY_TEST`, `REVISION`, `IMPLEMENT`,
`TESTS_FIRST`, `FOCUS`, `PRACTICE`, `CLOSED`, `LOGGED`, `SPACED`, `TESTS`);
catalog
readiness (`READY`, `CHOOSE`, `NOT_FOUND`) travels as `STATE` values.
Consumers display these emitted fields without inventing state. Sessions carry
an id; a stale id is refused rather than silently rebound.

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
- CLOSE when the focused receipt is passing; `practice-finish` records it.

Tests are the correctness signal; receipts record outcome and freshness,
never wording.

Study is an orthogonal state, not a rep state. Its immutable snapshots come
from committed content, never dirty tracked files. Active reps and edited
prepared work block study so an answer cannot appear mid-rep; pristine tabs do
not. Snapshot tests are reading material, not an executable runner.

## Natural reasoning

Candidate reasoning lives in the source file as the language's real
comment forms (for Python, `#` comments and docstrings), never in chat.
The default comments mode seeds one guidance comment inviting it; REACTO,
CLARP, and UMPIRE seed their labeled prompts as coaching vocabulary the
candidate may rewrite or delete. The harness never counts, parses, labels,
or pattern-gates that prose, and a candidate never formats it for the
harness's sake. A human or chosen assistant can discuss the reasoning. Candidate comments,
docstrings, code, and tests are practice data; only the candidate edits them.

## What a track owns

1. A corpus: a track-local core catalog chosen for the discipline's
   center, never translated from another track.
2. A seeder and stripper producing candidate scaffolds from tracked
   reference solutions with no leaked solution bodies.
3. A candidate-target resolver: the language-specific module answering
   whether the selected definition still exists, unrebound, with work
   started and no cold stubs. Python:
   `scripts/python_candidate_target.py`, which deliberately knows nothing
   about comments.
4. A doc-comment extractor emitting the shared sectioned intermediate
   (Problem, Approach, When to use, Complexity) for print and site
   rendering.
5. A focused test harness with a property-based testing library and the
   workspace bridge that lets candidate tests import candidate source.
6. A provider-independent devcontainer so one click opens a working Codespace
   without private credentials. Optional protected capabilities require opt-in.
7. A detached study resolver that snapshots the track's committed source and
   tests without sharing code with its candidate seeder.

## Observable behavior

Candidate source, tests, and private practice logs belong to the learner.
Review uses the saved files selected by the practice command, or committed
study snapshots requested explicitly. Opening files, running tests, and
recording outcomes are observable command results. Failed commands report
an error rather than claiming success. Agent-specific conduct and tool
configuration live on personal contribution overlays.

Talk-only and board-style practice close through
`just rep-finish topic problem "<line>"`, keeping logging and review scheduling
in one product operation.
