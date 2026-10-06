"""Validate the extended rep-log line convention (non-blocking by design).

The session dispatcher and `just rep-finish` atomically pair a non-editor
rep log with its review update. The optional scored convention is:

    <mode> <topic>/<problem> C<0-2> L<0-2> A<0-2> R<0-2> P<0-2> h<0-5> <one fix>

`mode` is one of talk|comment|cold|reacto|mock (the rung the rep was run at).
`C L A R P` are the sheet-10 SS5 rubric rows, each scored 0-2. `h<n>` is the
highest hint level used (0-5). The trailing free text is the one fix to carry
into the next rep.

Every explicit mode also accepts `<mode> <topic>/<problem> fix: <one fix>`.
That compact form leaves scores and hint level absent; it never invents them.

Lines logged before this convention existed may omit the leading `mode`
token, the trailing `h<n>` token, or both; those still parse as valid
("legacy"). Nothing here ever blocks a practice session: run with no
arguments to lint `.challenges/reps.md` (silently skipped if absent because it is
gitignored personal state and may not exist) and print warnings only, exit 0.
Pass a single line to validate just that line. Pass --strict to exit 1 if any
checked line is invalid.

CLI:
    python scripts/rep_schema.py "<line>"     # validate one line
    python scripts/rep_schema.py              # lint .challenges/reps.md
    python scripts/rep_schema.py --strict ... # exit 1 on any invalid line
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPS_LOG = ROOT / ".challenges" / "reps.md"

MODES = ("talk", "comment", "comments", "cold", "reacto", "clarp", "umpire", "mock")
EDITOR_MODES = ("comment", "comments", "reacto", "clarp", "umpire")
SCORE_LETTERS = ("C", "L", "A", "R", "P")

_SLUG_RE = re.compile(r"[a-z][a-z0-9_]*")
_HINT_TOKEN_RE = re.compile(r"h\d+")
_LOG_PREFIX_RE = re.compile(r"^-\s+\d{4}-\d{2}-\d{2}\s+(?P<rest>.+)$")


class RepLineError(ValueError):
    """A rep-log line violates the extended (or legacy) convention."""


@dataclass(frozen=True)
class RepLine:
    """One successfully parsed rep-log line."""

    mode: str | None
    topic: str
    problem: str
    scores: dict[str, int]
    hint_level: int | None
    fix: str
    is_legacy: bool
    is_compact: bool = False


def _parse_scored_token(letter: str, token: str, low: int, high: int) -> int:
    match = re.fullmatch(rf"{re.escape(letter)}(\d+)", token)
    if match is None:
        raise RepLineError(f"expected {letter}<{low}-{high}> score, got {token!r}")
    value = int(match.group(1))
    if not low <= value <= high:
        raise RepLineError(f"{letter} score {value} is outside {low}-{high}")
    return value


def parse_rep_line(line: str) -> RepLine:
    """Parse one rep-log line, raising RepLineError on any convention violation."""
    tokens = line.strip().split()
    if not tokens:
        raise RepLineError("empty line")

    mode: str | None = None
    if tokens[0] in MODES:
        mode = tokens.pop(0)

    if not tokens or "/" not in tokens[0]:
        raise RepLineError("missing '<topic>/<problem>' slug")

    slug = tokens.pop(0)
    topic, _, problem = slug.partition("/")
    if not _SLUG_RE.fullmatch(topic) or not _SLUG_RE.fullmatch(problem):
        raise RepLineError(f"malformed topic/problem slug: {slug!r}")

    # A closeout asks for one fix. A scored rubric remains optional for any
    # mode; a compact line records no scores or hints that were not supplied.
    if tokens and re.fullmatch(r"C\d+", tokens[0]) is None:
        if mode not in MODES:
            raise RepLineError("compact lines require an explicit practice mode")
        return RepLine(
            mode=mode,
            topic=topic,
            problem=problem,
            scores={},
            hint_level=None,
            fix=" ".join(tokens),
            is_legacy=False,
            is_compact=True,
        )

    scores: dict[str, int] = {}
    for letter in SCORE_LETTERS:
        if not tokens:
            raise RepLineError(f"missing {letter} score")
        scores[letter] = _parse_scored_token(letter, tokens.pop(0), 0, 2)

    hint_level: int | None = None
    if tokens and _HINT_TOKEN_RE.fullmatch(tokens[0]):
        hint_level = _parse_scored_token("h", tokens.pop(0), 0, 5)

    if not tokens:
        raise RepLineError("missing free-text fix")
    fix = " ".join(tokens)

    return RepLine(
        mode=mode,
        topic=topic,
        problem=problem,
        scores=scores,
        hint_level=hint_level,
        fix=fix,
        is_legacy=mode is None or hint_level is None,
    )


def _log_lines(path: Path) -> list[str]:
    """Return each reps.md entry with its `- YYYY-MM-DD ` log prefix stripped."""
    lines: list[str] = []
    for raw in path.read_text().splitlines():
        if not raw.strip():
            continue
        match = _LOG_PREFIX_RE.match(raw)
        lines.append(match.group("rest") if match else raw)
    return lines


def check_lines(lines: list[str], source: str) -> list[str]:
    """Return one warning string per invalid line; empty if every line is valid."""
    warnings: list[str] = []
    for line in lines:
        try:
            parse_rep_line(line)
        except RepLineError as exc:
            warnings.append(f"{source}: {exc} ({line.strip()!r})")
    return warnings


def _run(argv: list[str], *, reps_log: Path = REPS_LOG) -> int:
    strict = "--strict" in argv
    positional = [a for a in argv if a != "--strict"]

    if positional:
        warnings = check_lines([" ".join(positional)], source="<line>")
    else:
        if not reps_log.exists():
            return 0
        warnings = check_lines(_log_lines(reps_log), source=".challenges/reps.md")

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)

    return 1 if warnings and strict else 0


def main() -> int:
    return _run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
