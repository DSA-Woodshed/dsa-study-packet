"""List every editor-practice target and resolve candidate language.

The canonical selection is always a ``topic/problem`` pair from
``PRACTICE_TARGETS``. Search reports ambiguity instead of choosing for the
candidate.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import re
import textwrap
from dataclasses import asdict, dataclass
from pathlib import Path

from core42 import CORE_42, PRACTICE_TARGETS

ROOT = Path(__file__).resolve().parent.parent
_SEPARATOR = re.compile(r"\s*(?:[,;]|\band\b)\s*", re.IGNORECASE)
_REQUEST_WORDS = {
    "a",
    "an",
    "am",
    "answer",
    "answers",
    "avoid",
    "at",
    "board",
    "begin",
    "can",
    "code",
    "coding",
    "clock",
    "comment",
    "comments",
    "could",
    "d",
    "discuss",
    "editor",
    "exclude",
    "first",
    "focus",
    "for",
    "hey",
    "implement",
    "implementation",
    "inspect",
    "iterate",
    "iteration",
    "like",
    "basic",
    "basics",
    "do",
    "i",
    "let",
    "lets",
    "look",
    "me",
    "mock",
    "my",
    "no",
    "not",
    "observed",
    "of",
    "on",
    "open",
    "please",
    "practice",
    "problem",
    "problems",
    "read",
    "ready",
    "reason",
    "reasoning",
    "rep",
    "review",
    "s",
    "show",
    "skip",
    "some",
    "solution",
    "solutions",
    "start",
    "style",
    "study",
    "studying",
    "talk",
    "take",
    "test",
    "testing",
    "tests",
    "the",
    "there",
    "through",
    "timed",
    "timeer",
    "timer",
    "to",
    "untimed",
    "us",
    "want",
    "walk",
    "we",
    "with",
    "without",
    "work",
    "would",
    "write",
    "writing",
}

_NEGATION = re.compile(
    r"\b(?:"
    r"no|not|never|without|avoid|exclude|skip|cannot|cant|couldnt|didnt|dont|"
    r"doesnt|shouldnt|wont|wouldnt"
    r")\b"
    r"|\b(?:can|couldn|didn|don|doesn|shouldn|won|wouldn)\s+t\b"
)
_MODE_NEGATION = re.compile(
    r"\b(?:"
    r"no\s+(?:clock|timeer|timer)"
    r"|not\s+(?:a\s+)?timed"
    r"|without\s+(?:a\s+)?(?:clock|timeer|timer)"
    r")\b"
)


@dataclass(frozen=True)
class CatalogEntry:
    """One canonical editor-practice selection."""

    topic: str
    problem: str
    target: str
    core: bool
    summary: str

    @property
    def key(self) -> tuple[str, str]:
        return self.topic, self.problem

    @property
    def slug(self) -> str:
        return f"{self.topic}/{self.problem}"


@dataclass(frozen=True)
class Capability:
    """A public activity derived from material already present in the packet.

    ``duration`` is a suggested number of minutes, not an enforced clock.
    Availability describes the source material; optional editors and agents
    are never prerequisites for selecting an activity.
    """

    id: str
    kind: str
    title: str
    source: str
    modes: tuple[str, ...]
    duration: int
    entrypoint: str
    availability: str


def _source_title(path: Path) -> str:
    if path.suffix == ".py":
        try:
            docstring = ast.get_docstring(ast.parse(path.read_text())) or ""
            return next(line.strip() for line in docstring.splitlines() if line.strip())
        except (OSError, SyntaxError, StopIteration):
            return path.stem.replace("_", " ")
    try:
        return next(
            line.removeprefix("# ").strip()
            for line in path.read_text().splitlines()
            if line.startswith("# ")
        )
    except (OSError, StopIteration):
        return path.stem.replace("-", " ")


def capabilities(root: Path = ROOT) -> tuple[Capability, ...]:
    """Return one inventory, deriving its corpus and counts from source files."""
    records: list[Capability] = []

    def add(
        identity: str,
        kind: str,
        source: Path,
        modes: tuple[str, ...],
        duration: int,
        title: str | None = None,
    ) -> None:
        records.append(
            Capability(
                identity,
                kind,
                title or _source_title(root / source),
                source.as_posix(),
                modes,
                duration,
                f"just session start {identity} --mode {modes[0]} --minutes {duration}",
                "available" if (root / source).is_file() else "unavailable",
            )
        )

    for entry in catalog_entries(root):
        add(
            f"algorithm/{entry.slug}",
            "algorithm",
            Path("src/algo") / entry.topic / f"{entry.problem}.py",
            ("study", "implement", "tests-first", "talk", "board", "mock"),
            30,
            entry.summary,
        )
    for source in sorted((root / "src/concepts").glob("*.py")):
        if source.name != "__init__.py":
            add(
                f"concept/{source.stem}",
                "concept",
                source.relative_to(root),
                ("read",),
                30,
            )
    for source in sorted((root / "src/practice").glob("*/*")):
        if source.suffix in {".py", ".md"} and source.name != "__init__.py":
            relative = source.relative_to(root / "src/practice").with_suffix("")
            add(
                f"advanced/{relative.as_posix()}",
                "advanced",
                source.relative_to(root),
                ("read",),
                60,
            )
    for source in sorted((root / "reference-sheets").glob("[0-9][0-9]-*.md")):
        # Sheet 10 is explicitly the method authority. Expose it once, under
        # that role, rather than creating a second curriculum registry.
        kind = "method" if source.name.startswith("10-") else "reference"
        add(f"{kind}/{source.stem}", kind, source.relative_to(root), ("read",), 15)
    add(
        "review/due",
        "review",
        Path("scripts/study_schedule.py"),
        ("review",),
        15,
        "Choose a due problem from your private spaced-review queue",
    )
    add(
        "contribution/guide",
        "contribution",
        Path("CONTRIBUTING.md"),
        ("contribute",),
        30,
    )
    return tuple(records)


def capability_inventory(root: Path = ROOT) -> dict[str, object]:
    """Stable JSON interface used by the site and optional personal adapters."""
    entries = capabilities(root)
    kinds = sorted({entry.kind for entry in entries})
    return {
        "schema": 1,
        "counts": {
            kind: sum(entry.kind == kind for entry in entries) for kind in kinds
        },
        "capabilities": [asdict(entry) for entry in entries],
    }


@dataclass(frozen=True)
class QueryGroup:
    """One requested phrase and every matching canonical selection."""

    query: str
    matches: tuple[CatalogEntry, ...]


def _topic_title(topic: str) -> str:
    return topic.replace("_", " ")


def _normalized(value: str) -> str:
    words = re.sub(r"[^a-z0-9]+", " ", value.casefold()).split()
    return " ".join(words)


def _core_keys() -> set[tuple[str, str]]:
    return {
        (topic, problem) for topic, problems in CORE_42.items() for problem in problems
    }


def _plain_punctuation(value: str) -> str:
    return value.replace("\N{EM DASH}", "-").replace("\N{EN DASH}", "-")


def _problem_summary(root: Path, topic: str, problem: str) -> str:
    """Return a compact summary derived from the module's Problem section."""
    path = root / "src" / "algo" / topic / f"{problem}.py"
    try:
        docstring = ast.get_docstring(ast.parse(path.read_text()), clean=True) or ""
    except (OSError, SyntaxError):
        return problem.replace("_", " ")
    lines = docstring.splitlines()
    try:
        start = next(
            index for index, line in enumerate(lines) if line.strip() == "Problem:"
        )
    except StopIteration:
        first = next((line.strip() for line in lines if line.strip()), problem)
        return textwrap.shorten(_plain_punctuation(first), width=150, placeholder="...")

    body: list[str] = []
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if stripped.endswith(":") and body:
            break
        if stripped:
            body.append(stripped)
    summary = _plain_punctuation(" ".join(body) or problem.replace("_", " "))
    first_sentence = re.split(r"(?<=[.!?])\s+", summary, maxsplit=1)[0]
    return textwrap.shorten(first_sentence, width=150, placeholder="...")


def catalog_entries(root: Path = ROOT) -> tuple[CatalogEntry, ...]:
    """Return every practice target in stable registry order."""
    core = _core_keys()
    return tuple(
        CatalogEntry(
            topic=topic,
            problem=problem,
            target=target,
            core=(topic, problem) in core,
            summary=_problem_summary(root, topic, problem),
        )
        for (topic, problem), target in PRACTICE_TARGETS.items()
    )


def core_count() -> int:
    return sum(len(problems) for problems in CORE_42.values())


def practice_count() -> int:
    return len(PRACTICE_TARGETS)


def implementation_count() -> int:
    return sum(
        1
        for path in (ROOT / "src" / "algo").glob("*/*.py")
        if path.name != "__init__.py"
    )


def concept_count() -> int:
    return sum(
        1
        for path in (ROOT / "src" / "concepts").glob("*.py")
        if path.name != "__init__.py"
    )


def reference_sheet_count() -> int:
    return len(list((ROOT / "reference-sheets").glob("[0-9][0-9]-*.md")))


_EXACT_ALIASES: dict[str, tuple[tuple[str, str], ...]] = {
    "anagram": (("strings", "valid_anagram"), ("arrays", "group_anagrams")),
    "anagrams": (("strings", "valid_anagram"), ("arrays", "group_anagrams")),
    "valid anagram": (("strings", "valid_anagram"),),
    "valid anagrams": (("strings", "valid_anagram"),),
    "group anagram": (("arrays", "group_anagrams"),),
    "group anagrams": (("arrays", "group_anagrams"),),
    "valid group anagram": (
        ("strings", "valid_anagram"),
        ("arrays", "group_anagrams"),
    ),
    "2 sum": (("arrays", "two_sum"),),
    "two sum": (("arrays", "two_sum"),),
    "prime": (("math", "is_prime"), ("math", "sieve_of_eratosthenes")),
    "primes": (("math", "is_prime"), ("math", "sieve_of_eratosthenes")),
    "prime number": (("math", "is_prime"), ("math", "sieve_of_eratosthenes")),
    "prime numbers": (("math", "is_prime"), ("math", "sieve_of_eratosthenes")),
    "is prime": (("math", "is_prime"),),
    "is a number prime": (("math", "is_prime"),),
    "is number prime": (("math", "is_prime"),),
    "check prime": (("math", "is_prime"),),
    "check if prime": (("math", "is_prime"),),
    "check if a number is prime": (("math", "is_prime"),),
    "check if number is prime": (("math", "is_prime"),),
    "check whether a number is prime": (("math", "is_prime"),),
    "check whether number is prime": (("math", "is_prime"),),
    "prime check": (("math", "is_prime"),),
    "primality": (("math", "is_prime"),),
    "sieve": (("math", "sieve_of_eratosthenes"),),
    "prime sieve": (("math", "sieve_of_eratosthenes"),),
    "list primes": (("math", "sieve_of_eratosthenes"),),
    "all primes": (("math", "sieve_of_eratosthenes"),),
}


def _matching_entries_normalized(
    normalized: str,
    entries: tuple[CatalogEntry, ...],
    by_key: dict[tuple[str, str], CatalogEntry],
) -> tuple[CatalogEntry, ...]:
    """Match one already-normalized phrase without conversational recovery."""
    if normalized in _EXACT_ALIASES:
        return tuple(by_key[key] for key in _EXACT_ALIASES[normalized])

    query_words = set(normalized.split())
    if not query_words:
        return ()
    matches = []
    for entry in entries:
        searchable = _normalized(
            f"{entry.topic} {entry.problem} {_topic_title(entry.topic)} "
            f"{entry.problem.replace('_', ' ')} {entry.summary}"
        )
        if query_words <= set(searchable.split()):
            matches.append(entry)
    return tuple(matches)


def _has_substantive_negation(normalized: str) -> bool:
    """Distinguish a declined problem from an untimed-mode qualifier."""
    without_mode_qualifiers = _MODE_NEGATION.sub(" ", normalized)
    return _NEGATION.search(without_mode_qualifiers) is not None


def matching_entries(query: str, root: Path = ROOT) -> tuple[CatalogEntry, ...]:
    """Return every match for one phrase without resolving ambiguity."""
    normalized = _normalized(query)
    if _has_substantive_negation(normalized):
        return ()
    entries = catalog_entries(root)
    by_key = {entry.key: entry for entry in entries}
    direct = _matching_entries_normalized(normalized, entries, by_key)
    if direct or len(normalized.split()) < 2:
        return direct

    words = normalized.split()
    name_vocabulary = {
        word
        for entry in entries
        for word in _normalized(f"{entry.topic} {entry.problem}").split()
    }
    for width in range(len(words) - 1, 0, -1):
        recovered: list[CatalogEntry] = []
        for start in range(len(words) - width + 1):
            omitted = words[:start] + words[start + width :]
            if any(word in name_vocabulary for word in omitted):
                continue
            span = " ".join(words[start : start + width])
            matches = _matching_entries_normalized(span, entries, by_key)
            if len(matches) == 1:
                recovered.append(matches[0])
        if recovered:
            keys = {entry.key for entry in recovered}
            return (recovered[0],) if len(keys) == 1 else ()
    return ()


def _query_phrases(query: str) -> tuple[str, ...]:
    phrases = tuple(part.strip() for part in _SEPARATOR.split(query) if part.strip())
    cleaned = []
    for phrase in phrases:
        normalized = _normalized(phrase)
        words = [word for word in normalized.split() if word not in _REQUEST_WORDS]
        if words:
            cleaned.append(
                normalized if _has_substantive_negation(normalized) else " ".join(words)
            )
    return tuple(cleaned)


def search_catalog(query: str, root: Path = ROOT) -> tuple[QueryGroup, ...]:
    """Search each comma/and-separated phrase in the candidate's order."""
    return tuple(
        QueryGroup(phrase, matching_entries(phrase, root))
        for phrase in _query_phrases(query)
    )


def nearby_entries(
    topic: str, problem: str, root: Path = ROOT
) -> tuple[CatalogEntry, ...]:
    """Suggest likely intended targets for an invalid explicit pair."""
    direct = matching_entries(problem.replace("_", " "), root)
    if direct:
        return direct

    entries = catalog_entries(root)
    query = _normalized(f"{topic} {problem}")
    choices: dict[str, CatalogEntry] = {}
    for entry in entries:
        choices[_normalized(f"{entry.topic} {entry.problem}")] = entry
        choices[_normalized(entry.problem)] = entry
    close = difflib.get_close_matches(query, choices, n=4, cutoff=0.42)
    if not close:
        close = difflib.get_close_matches(
            _normalized(problem), choices, n=4, cutoff=0.42
        )
    seen: set[tuple[str, str]] = set()
    suggested: list[CatalogEntry] = []
    for value in close:
        entry = choices[value]
        if entry.key not in seen:
            seen.add(entry.key)
            suggested.append(entry)
    return tuple(suggested)


def _entry_line(prefix: str, entry: CatalogEntry) -> str:
    status = "Core" if entry.core else "Extra"
    return f"{prefix}: {entry.slug} | {status} | {entry.summary}"


def selection_error(topic: str, problem: str, root: Path = ROOT) -> str:
    """Return an actionable error for one non-canonical explicit pair."""
    lines = [f"unknown practice target: {topic}/{problem}"]
    suggestions = nearby_entries(topic, problem, root)
    if suggestions:
        lines.extend(_entry_line("MATCH", entry) for entry in suggestions)
    else:
        lines.append("MATCH: no nearby canonical pair")
    query = problem.replace("_", " ") or topic.replace("_", " ")
    lines.append(
        f'NEXT: run `just catalog "{query}"`, then use one exact topic/problem pair.'
    )
    return "\n".join(lines)


def render_catalog(root: Path = ROOT) -> str:
    lines = [
        "# Study packet catalog",
        "",
        f"- Core set: {core_count()} problems",
        f"- Editor-practice targets: {practice_count()} problems",
        f"- Algorithm implementations: {implementation_count()}",
        f"- Concept modules: {concept_count()}",
        f"- Reference sheets: {reference_sheet_count()}",
        "",
        "## Editor-practice targets",
        "",
    ]
    lines.extend(
        f"- {entry.slug} | {'Core' if entry.core else 'Extra'} | {entry.summary}"
        for entry in catalog_entries(root)
    )
    return "\n".join(lines)


def render_query(query: str, root: Path = ROOT) -> str:
    groups = search_catalog(query, root)
    ready = bool(groups) and all(len(group.matches) == 1 for group in groups)
    not_found = not groups or any(not group.matches for group in groups)
    state = "READY" if ready else "NOT_FOUND" if not_found else "CHOOSE"
    lines = [
        "# Practice catalog matches",
        f"STATE: {state}",
    ]
    if not groups:
        return "\n".join(
            [
                *lines,
                "MATCH: no search words supplied",
                "NEXT: run `just catalog` to list every exact topic/problem pair.",
            ]
        )

    if ready:
        selections = list(dict.fromkeys(group.matches[0].slug for group in groups))
        lines.append(f"START: {selections[0]}")
        lines.extend(f"QUEUE: {selection}" for selection in selections[1:])

    for group in groups:
        lines.extend(["", f"QUERY: {group.query}"])
        if not group.matches:
            lines.append("MATCH: no canonical practice target")
            lines.extend(
                _entry_line("SUGGEST", entry)
                for entry in nearby_entries("", group.query, root)
            )
        elif len(group.matches) == 1:
            entry = group.matches[0]
            lines.append(_entry_line("MATCH", entry))
        else:
            lines.extend(_entry_line("CHOOSE", entry) for entry in group.matches)
    if ready:
        lines.append(
            "\nNEXT: start START with the selected mode; finish it before each "
            "QUEUE item in order."
        )
    elif not_found:
        lines.append(
            "\nNEXT: revise each unmatched name using SUGGEST, or run `just catalog` "
            "for every exact pair."
        )
    else:
        lines.append(
            "\nNEXT: choose one exact pair for every CHOOSE query, then rerun "
            "`just catalog` with those names."
        )
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", help="natural problem name or list")
    parser.add_argument(
        "--json", action="store_true", help="emit the complete capability inventory"
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.json:
        if args.query is not None:
            _parser().error("--json lists the inventory; omit the problem query")
        print(json.dumps(capability_inventory(), indent=2))
        return 0
    print(render_query(args.query) if args.query is not None else render_catalog())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
