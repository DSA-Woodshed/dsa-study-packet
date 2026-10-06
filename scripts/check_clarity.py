"""Guard concise, low-ambiguity product and onboarding surfaces.

Run with the repository root by default, or pass another root to inspect a
fixture or checkout::

    python scripts/check_clarity.py [ROOT]
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SURFACE_BUDGETS: dict[str, int] = {
    "llms.txt": 300,
    "agent-map.md": 300,
    "TRACK-CONTRACT.md": 800,
    ".devcontainer/welcome.sh": 300,
    "README.md": 650,
    "WELCOME.md": 300,
    "docs/index.md": 400,
    "docs/guide/getting-started.md": 1050,
    "docs/challenges/index.md": 900,
    "docs/guide/local-practice.md": 500,
    "docs/guide/learning-paths.md": 1500,
    "docs/guide/source-of-truth.md": 1500,
    "reference-sheets/11-14-day-whiteboard-ramp.md": 1000,
}

DESCRIPTION_MAX_CHARS = 160
DESCRIPTION_SURFACES: tuple[str, ...] = (
    "docs/guide/getting-started.md",
    "docs/challenges/index.md",
    "docs/printables.md",
    "docs/guide/source-of-truth.md",
    "docs/guide/local-practice.md",
    "docs/guide/learning-paths.md",
    "docs/guide/when-to-use-what.md",
    "docs/guide/interview-practice-evidence.md",
    "docs/reference/index.md",
    "docs/reference/01-python-stdlib.md",
    "docs/reference/02-data-structures.md",
    "docs/reference/03-algorithm-templates.md",
    "docs/reference/04-big-o-complexity.md",
    "docs/reference/05-common-patterns.md",
    "docs/reference/06-system-design.md",
    "docs/reference/07-interview-day-guide.md",
    "docs/reference/08-cross-reference-guide.md",
    "docs/reference/09-python-314-and-modern-patterns.md",
    "docs/reference/10-whiteboard-performance-protocol.md",
    "docs/reference/11-14-day-whiteboard-ramp.md",
)

EM_DASH = "\u2014"
UNRESOLVED_STRINGS: dict[str, str] = {
    "study-spaced N": "replace N with a concrete draw count or a command that draws internally",
    "C_ L_ A_ R_ P_": "replace score blanks with concrete input or an atomic closeout command",
}


def word_count(text: str) -> int:
    """Count whitespace-delimited words, matching the guard's documented budgets."""
    return len(text.split())


def frontmatter_description(text: str) -> str | None:
    """Return a single-line Markdown frontmatter description when present."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("description:"):
            return line.removeprefix("description:").strip()
    return None


def check(root: Path) -> list[str]:
    """Return one actionable failure per clarity contract violation."""
    failures: list[str] = []
    for relative, budget in SURFACE_BUDGETS.items():
        path = root / relative
        if not path.is_file():
            failures.append(f"{relative}: missing clarity-guarded surface")
            continue

        text = path.read_text()
        words = word_count(text)
        if words > budget:
            failures.append(
                f"{relative}: {words} words exceeds the {budget}-word budget; "
                f"cut at least {words - budget} word(s)"
            )

        em_dash_count = text.count(EM_DASH)
        if em_dash_count:
            failures.append(
                f"{relative}: contains {em_dash_count} U+2014 em dash character(s); "
                "replace them with commas, colons, parentheses, or hyphens"
            )

        for unresolved, remedy in UNRESOLVED_STRINGS.items():
            if unresolved in text:
                failures.append(
                    f'{relative}: contains unresolved instruction "{unresolved}"; {remedy}'
                )

    for relative in DESCRIPTION_SURFACES:
        path = root / relative
        if not path.is_file():
            if relative not in SURFACE_BUDGETS:
                failures.append(f"{relative}: missing clarity-guarded surface")
            continue

        description = frontmatter_description(path.read_text())
        if not description:
            failures.append(
                f"{relative}: add a concise frontmatter description for cards and metadata"
            )
        elif len(description) > DESCRIPTION_MAX_CHARS:
            failures.append(
                f"{relative}: frontmatter description is {len(description)} characters; "
                f"keep it at or below {DESCRIPTION_MAX_CHARS}"
            )

    return failures


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    failures = check(args.root.resolve())
    if failures:
        print("Clarity guard failed:")
        for failure in failures:
            print(f"  {failure}")
        return 1

    print(
        f"Clarity guard passed; {len(SURFACE_BUDGETS)} surfaces are within "
        "their word budgets, required descriptions are present, and control "
        "text is unambiguous."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
