"""Generate a challenge progress page for mkdocs.

Reads .challenges/progress.md and the full list of core-42 problems,
then renders a checklist page showing completed vs remaining problems.

Run automatically by mkdocs-gen-files during `mkdocs build`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import mkdocs_gen_files

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core42 import CORE_42
from study_schedule import _completed

ROOT = Path(__file__).resolve().parent.parent
PROGRESS_FILE = ROOT / ".challenges" / "progress.md"


def _parse_progress() -> dict[str, str]:
    """Parse .challenges/progress.md into {topic/problem: date} map."""
    return _completed(PROGRESS_FILE)


def _title(name: str) -> str:
    return name.replace("_", " ").title()


def _topic_title(topic: str) -> str:
    special = {
        "dp": "Dynamic Programming",
        "stacks_queues": "Stacks & Queues",
        "math": "Math & Number Theory",
    }
    return special.get(topic, _title(topic))


def main() -> None:
    completed = _parse_progress()
    total = sum(len(ps) for ps in CORE_42.values())
    done = sum(1 for t, ps in CORE_42.items() for p in ps if f"{t}/{p}" in completed)

    lines = [
        "---",
        "title: Practice Progress",
        "---",
        "",
        "# Practice Progress",
        "",
        f"**{done} / {total}** core problems completed.",
        "",
    ]

    if total > 0:
        pct = int(done / total * 100)
        bar_filled = pct // 5
        bar_empty = 20 - bar_filled
        lines.append(f"`{'█' * bar_filled}{'░' * bar_empty}` {pct}%")
        lines.append("")

    # Per-topic summary table
    lines.append("| Topic | Done | Progress |")
    lines.append("|-------|------|----------|")
    for topic, problems in CORE_42.items():
        topic_done = sum(1 for p in problems if f"{topic}/{p}" in completed)
        topic_pct = int(topic_done / len(problems) * 100)
        filled = topic_pct // 10
        bar = "█" * filled + "░" * (10 - filled)
        lines.append(
            f"| {_topic_title(topic)} | {topic_done}/{len(problems)} | `{bar}` {topic_pct}% |"
        )
    lines.append("")

    lines.append("---")
    lines.append("")

    for topic in CORE_42:
        problems = CORE_42[topic]
        topic_done = sum(1 for p in problems if f"{topic}/{p}" in completed)
        lines.append(f"### {_topic_title(topic)} ({topic_done}/{len(problems)})")
        lines.append("")
        for problem in problems:
            key = f"{topic}/{problem}"
            if key in completed:
                date = completed[key]
                date_str = f" ({date})" if date else ""
                lines.append(f"- [x] {_title(problem)}{date_str}")
            else:
                lines.append(f"- [ ] {_title(problem)}")
        lines.append("")

    # Suggest the first few problems not yet completed.
    remaining = [
        f"{topic}/{problem}"
        for topic, problems in CORE_42.items()
        for problem in problems
        if f"{topic}/{problem}" not in completed
    ]
    if remaining:
        lines.append("## Suggested next")
        lines.append("")
        for key in remaining[:5]:
            topic, problem = key.split("/")
            lines.append(
                f"- `just practice-start comments {topic} {problem}`: {_title(problem)}"
            )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("Run `just study-spaced` to see the next problems due for review.")
    lines.append("")

    with mkdocs_gen_files.open("challenges/progress.md", "w") as f:
        f.write("\n".join(lines))


main()
