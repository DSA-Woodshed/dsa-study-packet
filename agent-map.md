# Woodshed command map

This map describes the product interface for humans and optional assistants.
Read `TRACK-CONTRACT.md`, `docs/guide/getting-started.md`, and
`docs/guide/source-of-truth.md`. Personal provider directives live on the
contribution fork, outside the organization product.

## Activity selection

`just session` guides time, study or practice, focus, feedback, and workspace.
`just catalog "<words>"` resolves natural names to exact topic/problem pairs.

## Practice commands

- `just practice-start comments|reacto|clarp|umpire [topic problem]`
- `just practice-next`
- `just practice-test`, `just practice-watch`, `just practice-repl`
- `just practice-open [topic problem]`
- `just practice-study topic problem`
- `just practice-start-tests topic problem`
- `just practice-finish "<one fix>"`
- `just interview [topic problem]`
- `just rep-finish topic problem "<line>"`

Study emits `IMPLEMENT` and `TESTS_FIRST` transitions for the selected pair.
Commands report `STATE`, `SOURCE`, `TEST`, `NEXT`, `OPENED`, `OPEN_FAILED`,
`REVISION`, and outcome fields. The practice contract defines the interface.

## Development

`just setup`, `just check`, `just env-check`, `just doctor`, `just packet`,
`just docs`, and `just pdf-all` cover environment, contribution gates, and
publishing. The reading site consumes an exact packet revision.

Candidate files and practice history are private and gitignored. Reference
solutions are tracked. Employer-specific prep remains downstream.
