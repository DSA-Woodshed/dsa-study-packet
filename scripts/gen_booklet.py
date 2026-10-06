"""Generate a printable LaTeX booklet from algo sources + decision trees.

Reads every src/algo/{topic}/{problem}.py, extracts the module docstring
and source code, then emits a .tex file with:

  1. Title page
  2. Table of contents
  3. Decision tree / pattern recognition pages (from reference sheets)
  4. One page per algorithm (docstring + code listing)

Usage:
    python scripts/gen_booklet.py            # writes booklet.tex
    tectonic booklet.tex                     # compiles to booklet.pdf
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALGO_SRC = ROOT / "src" / "algo"
REF_SHEETS = ROOT / "reference-sheets"

# Topic display order and titles
TOPIC_ORDER: list[tuple[str, str]] = [
    ("arrays", "Arrays \\& Hashing"),
    ("two_pointers", "Two Pointers"),
    ("sliding_window", "Sliding Window"),
    ("stacks_queues", "Stacks \\& Queues"),
    ("searching", "Searching"),
    ("sorting", "Sorting"),
    ("linked_lists", "Linked Lists"),
    ("trees", "Trees"),
    ("graphs", "Graphs"),
    ("dp", "Dynamic Programming"),
    ("heaps", "Heaps"),
    ("backtracking", "Backtracking"),
    ("greedy", "Greedy"),
    ("strings", "Strings"),
    ("recursion", "Recursion"),
    ("bit_manipulation", "Bit Manipulation"),
    ("math", "Math \\& Number Theory"),
    ("patterns", "Patterns"),
]

TOPIC_TITLES = dict(TOPIC_ORDER)

# Appendix: interview topics that round out whiteboard coverage beyond the
# Core 42 (concurrency, hashing internals, amortized analysis, recursion ->
# iteration, fixed-width numeric pitfalls). Authored as structured data in
# reference-sheets/appendix-topics.json so the LaTeX is generated compile-safely
# (every field escaped); rendered by _gen_appendix_pages().
APPENDIX_DATA = REF_SHEETS / "appendix-topics.json"


def _load_appendix_topics(path: Path = APPENDIX_DATA) -> list[dict]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


# ── Helpers ──────────────────────────────────────────────────────────


def _tex_escape(text: str) -> str:
    """Escape special LaTeX characters in plain text."""
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
        ("\u2014", "---"),  # em-dash
        ("\u2013", "--"),  # en-dash
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _title_from_filename(name: str) -> str:
    """two_sum -> Two Sum."""
    return name.replace("_", " ").title()


def _extract_module_docstring(source: str) -> str:
    """Extract the module-level docstring from Python source."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""
    return ast.get_docstring(tree) or ""


def _extract_code_after_docstring(source: str) -> str:
    """Extract everything after the module docstring (imports + functions)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    if not tree.body:
        return source

    first = tree.body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
        # Module docstring ends at this line
        start_line = first.end_lineno or 0
        lines = source.splitlines()
        # Skip blank lines after docstring
        while start_line < len(lines) and not lines[start_line].strip():
            start_line += 1
        return "\n".join(lines[start_line:])

    return source


def _parse_docstring_sections(docstring: str) -> dict[str, str]:
    """Parse a structured docstring into sections.

    Returns dict with keys like 'title', 'problem', 'approach',
    'when to use', 'complexity'.
    """
    sections: dict[str, str] = {}

    lines = docstring.strip().splitlines()
    if not lines:
        return sections

    # First line is the title
    sections["title"] = lines[0].strip().rstrip(".")

    current_key = ""
    current_lines: list[str] = []

    for line in lines[1:]:
        stripped = line.strip()
        # Check for section header like "Problem:" or "When to use:"
        match = re.match(
            r"^(Problem|Approach|When to use|Complexity|When To Use):\s*$",
            stripped,
            re.IGNORECASE,
        )
        if match:
            if current_key:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = match.group(1).lower()
            if current_key == "when to use":
                current_key = "when_to_use"
            current_lines = []
        elif current_key:
            current_lines.append(line.rstrip())

    if current_key:
        sections[current_key] = "\n".join(current_lines).strip()

    return sections


def _format_section_text(text: str) -> str:
    """Clean up indented docstring text for LaTeX."""
    return textwrap.dedent(text).strip()


# ── Decision tree pages ──────────────────────────────────────────────


def _gen_decision_tree_pages() -> str:
    """Generate LaTeX for decision tree / pattern recognition pages."""
    parts: list[str] = []

    parts.append(r"\chapter{Decision Trees \& Patterns}")
    parts.append("")

    # Master decision tree as structured text (mermaid won't render in LaTeX)
    parts.append(r"\section{Master Decision Tree}")
    parts.append(r"\begin{small}")
    parts.append(r"\begin{verbatim}")
    parts.append(
        textwrap.dedent("""\
    What does the problem ask for?
    |
    +-- FIND / SEARCH
    |   +-- Input sorted?
    |   |   +-- YES --> Binary Search
    |   |   +-- Rotated? --> Search Rotated Array
    |   |   +-- NO --> Hash Map O(n) lookup
    |   +-- Find in a graph?
    |       +-- Unweighted --> BFS
    |       +-- Weighted (positive) --> Dijkstra
    |       +-- Weighted (negative) --> Bellman-Ford
    |       +-- With heuristic --> A* Search
    |
    +-- OPTIMIZE (min cost, max profit, count ways)
    |   +-- Overlapping subproblems?
    |   |   +-- YES --> Dynamic Programming
    |   |   |   +-- 1D: climbing_stairs, coin_change
    |   |   |   +-- 2D: edit_distance, longest_common_subseq
    |   |   |   +-- Bitmask: traveling_salesman_dp
    |   |   +-- NO --> Greedy (merge_intervals, jump_game)
    |   +-- Top-K or priority ordering?
    |       +-- Kth element --> Min-heap of size k
    |       +-- Merge K sorted --> Heap merge
    |
    +-- GENERATE ALL / ENUMERATE
    |   +-- All subsets --> backtracking/subsets
    |   +-- All permutations --> backtracking/permutations
    |   +-- Combinations to sum --> backtracking/combination_sum
    |   +-- Placement with rules --> backtracking/n_queens
    |
    +-- PROCESS A SEQUENCE (subarray, substring)
    |   +-- Contiguous?
    |   |   +-- YES --> Sliding Window
    |   |   |   +-- Fixed size: standard pattern
    |   |   |   +-- Variable: min_window_substring
    |   |   +-- NO --> Subsequence DP (LIS, LCS)
    |   +-- Next greater/smaller? --> Monotonic Stack
    |   +-- Valid nesting? --> Stack (valid_parentheses)
    |
    +-- GRAPH STRUCTURE
    |   +-- Connected components --> DFS/BFS / Union-Find
    |   +-- Dependency ordering --> Topological Sort
    |   +-- Cycle detection --> DFS coloring / course_schedule
    |   +-- Min spanning tree --> Kruskal's MST
    |   +-- Maximum flow --> Edmonds-Karp
    |
    +-- DESIGN A DATA STRUCTURE
        +-- O(1) access + eviction --> LRU Cache
        +-- O(1) min/max retrieval --> Min Stack
        +-- Sorted insert + search --> bisect / SortedList""")
    )
    parts.append(r"\end{verbatim}")
    parts.append(r"\end{small}")

    # Pattern recognition keywords
    parts.append(r"\newpage")
    parts.append(r"\section{Pattern Recognition Keywords}")
    parts.append(r"\begin{small}")
    parts.append(r"\begin{tabular}{l l l}")
    parts.append(r"\textbf{Keyword} & \textbf{First Try} & \textbf{Fallback} \\")
    parts.append(r"\hline")

    keywords = [
        ("sorted", "Binary search, two pointers", "--"),
        ("contiguous subarray", "Sliding window", "Prefix sums, Kadane's"),
        ("substring", "Sliding window + hash map", "DP"),
        ("parentheses / brackets", "Stack", "--"),
        ("next greater / warmer", "Monotonic stack", "--"),
        ("shortest path", "BFS / Dijkstra", "Bellman-Ford, A*"),
        ("connected / island", "DFS/BFS flood fill", "Union-Find"),
        ("dependency / prerequisite", "Topological sort", "--"),
        ("cycle", "DFS coloring / Union-Find", "--"),
        ("minimum cost / count ways", "Dynamic programming", "--"),
        ("all subsets / combinations", "Backtracking", "Bitmask"),
        ("merge / overlapping intervals", "Sort + greedy sweep", "--"),
        ("kth largest / top k", "Heap of size k", "Quickselect"),
        ("design / implement", "Choose data structures", "--"),
        ("cache / eviction", "Hash map + linked list", "--"),
        ("stream / online", "Heap, sliding window", "--"),
        ("frequency / how many", "Counter / hash map", "--"),
        ("edit distance / transform", "2D DP", "BFS (word ladder)"),
        ("knapsack / subset sum", "DP (1D or 2D)", "--"),
        ("XOR / single unique", "Bit manipulation", "--"),
        ("nearest point / proximity", "KD-tree, geohash", "--"),
        ("visit all cities/nodes", "TSP bitmask DP", "--"),
    ]

    for kw, first, fallback in keywords:
        parts.append(
            f"  {_tex_escape(kw)} & {_tex_escape(first)} & {_tex_escape(fallback)} \\\\"
        )

    parts.append(r"\end{tabular}")
    parts.append(r"\end{small}")

    # Data structure selection
    parts.append(r"\vspace{1em}")
    parts.append(r"\section{Data Structure Selection}")
    parts.append(r"\begin{small}")
    parts.append(r"\begin{verbatim}")
    parts.append(
        textwrap.dedent("""\
    Need key -> value?          --> dict
    Need "is X in the set?"     --> set
    Need min/max repeatedly?    --> heapq
    Need FIFO?                  --> collections.deque
    Need LIFO?                  --> list (append/pop)
    Need sorted insert+search?  --> bisect / SortedList
    Need merge/find groups?     --> Union-Find
    Need nearest in 2D/3D?      --> KD-tree or geohash""")
    )
    parts.append(r"\end{verbatim}")
    parts.append(r"\end{small}")

    # Decision framework when stuck
    parts.append(r"\section{When Stuck}")
    parts.append(r"\begin{small}")
    parts.append(r"\begin{verbatim}")
    parts.append(
        textwrap.dedent("""\
    1. INPUT SIZE? --> Determines max acceptable complexity
    2. OUTPUT? --> Boolean=search, Value=optimize, All=backtrack
    3. Can I SORT? --> Unlocks two pointers, binary search, greedy
    4. HASH MAP? --> Trade space for O(1) lookup
    5. OPTIMAL SUBSTRUCTURE + OVERLAPPING? --> DP
       Optimal substructure only? --> Greedy
    6. GRAPH STRUCTURE? --> BFS/DFS/Dijkstra
    7. INTERVALS / EVENTS? --> Sort by end (schedule) or start (merge)""")
    )
    parts.append(r"\end{verbatim}")
    parts.append(r"\end{small}")

    # Gotchas
    parts.append(r"\newpage")
    parts.append(r"\section{Common Mistakes}")
    parts.append(r"\begin{small}")
    parts.append(r"\begin{tabular}{l l}")
    parts.append(r"\textbf{Mistake} & \textbf{Fix} \\")
    parts.append(r"\hline")

    gotchas = [
        ("list.pop(0) in a loop", "Use deque.popleft() -- O(1)"),
        ("s += char in a loop", "parts.append(char); ''.join(parts)"),
        ("Mutable default arg def f(a=[])", "Use a=None; a = a or []"),
        ("Modifying list while iterating", "Iterate over a copy"),
        ("Off-by-one in binary search", "Check lo <= hi vs lo < hi"),
        ("Forgetting to copy in backtrack", "result.append(path[:])"),
        ("@lru_cache with mutable args", "Convert lists to tuples first"),
        ("DFS hitting recursion limit", "setrecursionlimit or iterative"),
        ("Dijkstra with negative weights", "Use Bellman-Ford instead"),
        ("BFS: mark visited late", "Mark when ENQUEUING, not dequeuing"),
        ("// with negatives", "-7 // 2 = -4; use int(-7/2) = -3"),
    ]

    for mistake, fix in gotchas:
        parts.append(f"  {_tex_escape(mistake)} & {_tex_escape(fix)} \\\\")

    parts.append(r"\end{tabular}")
    parts.append(r"\end{small}")

    return "\n".join(parts)


# ── Algorithm pages ──────────────────────────────────────────────────


def _gen_algo_page(source_path: Path) -> str:
    """Generate LaTeX for a single algorithm page."""
    source = source_path.read_text()
    docstring = _extract_module_docstring(source)
    code = _extract_code_after_docstring(source)
    sections = _parse_docstring_sections(docstring)

    title = sections.get("title", _title_from_filename(source_path.stem))
    parts: list[str] = []

    parts.append(r"\newpage")
    parts.append(f"\\section{{{_tex_escape(title)}}}")

    # Problem
    if "problem" in sections:
        text = _format_section_text(sections["problem"])
        parts.append(r"\subsection*{Problem}")
        parts.append(_tex_escape(text))
        parts.append("")

    # Approach
    if "approach" in sections:
        text = _format_section_text(sections["approach"])
        parts.append(r"\subsection*{Approach}")
        parts.append(_tex_escape(text))
        parts.append("")

    # When to use
    if "when_to_use" in sections:
        text = _format_section_text(sections["when_to_use"])
        parts.append(r"\subsection*{When to Use}")
        parts.append(_tex_escape(text))
        parts.append("")

    # Complexity — extract just Time/Space lines
    if "complexity" in sections:
        text = _format_section_text(sections["complexity"])
        # Pull only "Time:" and "Space:" lines
        time_line = ""
        space_line = ""
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("time:"):
                time_line = stripped
            elif stripped.lower().startswith("space:"):
                space_line = stripped
        if time_line or space_line:
            parts.append(r"\subsection*{Complexity}")
            if time_line:
                parts.append(f"\\texttt{{{_tex_escape(time_line)}}}")
                parts.append(r"\\")
            if space_line:
                parts.append(f"\\texttt{{{_tex_escape(space_line)}}}")
            parts.append("")

    # Code listing — replace unicode chars that T1 fonts can't render in verbatim
    safe_code = code.rstrip().replace("\u2014", "--").replace("\u2013", "-")
    parts.append(r"\subsection*{Implementation}")
    parts.append(r"\begin{small}")
    parts.append(r"\begin{verbatim}")
    parts.append(safe_code)
    parts.append(r"\end{verbatim}")
    parts.append(r"\end{small}")

    return "\n".join(parts)


# ── Appendix pages (structured -> LaTeX, compile-safe) ───────────────


def _gen_appendix_pages(topics: list[dict]) -> str:
    """Render the structured appendix topics into LaTeX.

    Every string is escaped except code blocks (emitted verbatim with unicode
    stripped), so arbitrary authored content cannot break the build.
    """
    if not topics:
        return ""

    parts: list[str] = [r"\newpage", r"\chapter{Appendix: Interview Topics}", ""]

    for t in topics:
        parts.append(r"\newpage")
        parts.append(f"\\section{{{_tex_escape(t.get('section_title', ''))}}}")

        summary = (t.get("summary") or "").strip()
        if summary:
            parts.append(_tex_escape(summary))
            parts.append("")

        key_points = t.get("key_points") or []
        if key_points:
            parts.append(r"\subsection*{Key Points}")
            parts.append(r"\begin{itemize}[leftmargin=1.2em,itemsep=1pt,topsep=2pt]")
            for kp in key_points:
                parts.append(f"  \\item {_tex_escape(kp)}")
            parts.append(r"\end{itemize}")
            parts.append("")

        for tbl in t.get("tables") or []:
            header = tbl.get("header") or []
            rows = tbl.get("rows") or []
            if not header or not rows:
                continue
            ncol = len(header)
            colspec = " ".join(["X"] * ncol)
            title = (tbl.get("title") or "").strip()
            if title:
                parts.append(f"\\subsection*{{{_tex_escape(title)}}}")
            parts.append(r"\begin{small}")
            parts.append(f"\\begin{{tabularx}}{{\\linewidth}}{{{colspec}}}")
            parts.append(
                " & ".join(f"\\textbf{{{_tex_escape(h)}}}" for h in header) + r" \\"
            )
            parts.append(r"\hline")
            for row in rows:
                cells = (list(row) + [""] * ncol)[:ncol]
                parts.append(" & ".join(_tex_escape(c) for c in cells) + r" \\")
            parts.append(r"\end{tabularx}")
            parts.append(r"\end{small}")
            parts.append("")

        for cb in t.get("code_blocks") or []:
            caption = (cb.get("caption") or "").strip()
            if caption:
                parts.append(f"\\subsection*{{{_tex_escape(caption)}}}")
            code = (cb.get("code") or "").replace("\u2014", "--").replace("\u2013", "-")
            parts.append(r"\begin{small}")
            parts.append(r"\begin{verbatim}")
            parts.append(code.rstrip())
            parts.append(r"\end{verbatim}")
            parts.append(r"\end{small}")
            parts.append("")

        pitfalls = t.get("pitfalls") or []
        if pitfalls:
            parts.append(r"\subsection*{Pitfalls}")
            parts.append(r"\begin{itemize}[leftmargin=1.2em,itemsep=1pt,topsep=2pt]")
            for pf in pitfalls:
                parts.append(f"  \\item {_tex_escape(pf)}")
            parts.append(r"\end{itemize}")
            parts.append("")

    return "\n".join(parts)


# ── Document assembly ────────────────────────────────────────────────


def _gen_preamble() -> str:
    return textwrap.dedent(r"""
    \documentclass[10pt, letterpaper]{report}
    \usepackage[margin=0.6in, top=0.75in, bottom=0.75in]{geometry}
    \usepackage[T1]{fontenc}
    \usepackage{lmodern}
    \usepackage{microtype}
    \usepackage{hyperref}
    \usepackage{xcolor}
    \usepackage{fancyhdr}
    \usepackage{titlesec}
    \usepackage{tabularx}
    \usepackage{enumitem}

    \hypersetup{
        colorlinks=true,
        linkcolor=violet,
        urlcolor=teal,
    }

    % Compact chapter/section headings
    \titleformat{\chapter}[hang]{\LARGE\bfseries}{}{0pt}{}
    \titlespacing*{\chapter}{0pt}{-10pt}{10pt}
    \titleformat{\section}[hang]{\large\bfseries}{}{0pt}{}
    \titlespacing*{\section}{0pt}{8pt}{4pt}
    \titleformat{\subsection}[hang]{\normalsize\bfseries}{}{0pt}{}
    \titlespacing*{\subsection}{0pt}{4pt}{2pt}

    % Header/footer
    \pagestyle{fancy}
    \fancyhf{}
    \fancyhead[L]{\small\leftmark}
    \fancyhead[R]{\small\thepage}
    \renewcommand{\headrulewidth}{0.4pt}

    % Tight verbatim spacing
    \usepackage{etoolbox}
    \makeatletter
    \preto{\@verbatim}{\topsep=2pt \partopsep=0pt}
    \makeatother

    \setlength{\parindent}{0pt}
    \setlength{\parskip}{4pt}
    """).strip()


def render_booklet(
    algo_src: Path = ALGO_SRC, appendix_data: Path = APPENDIX_DATA
) -> str:
    """Render only declared source inputs, independently of the output directory."""
    parts: list[str] = []

    # Preamble
    parts.append(_gen_preamble())
    parts.append("")

    # Title
    parts.append(
        r"\title{\textbf{The DSA Woodshed}\\[0.5em]\large Printable Reference Packet}"
    )
    parts.append(r"\author{}")
    parts.append(r"\date{}")
    parts.append("")
    parts.append(r"\begin{document}")
    parts.append(r"\maketitle")
    parts.append(r"\tableofcontents")
    parts.append(r"\newpage")

    # Decision trees & patterns
    parts.append(_gen_decision_tree_pages())

    # Algorithm pages by topic
    for topic_dir, topic_title in TOPIC_ORDER:
        topic_path = algo_src / topic_dir
        if not topic_path.is_dir():
            continue

        source_files = sorted(
            f for f in topic_path.glob("*.py") if f.name != "__init__.py"
        )
        if not source_files:
            continue

        parts.append(r"\newpage")
        parts.append(f"\\chapter{{{topic_title}}}")

        for src_file in source_files:
            parts.append(_gen_algo_page(src_file))

    # Appendix: interview topics that round out whiteboard coverage.
    appendix = _gen_appendix_pages(_load_appendix_topics(appendix_data))
    if appendix:
        parts.append(appendix)

    parts.append(r"\end{document}")
    parts.append("")

    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--algo-src", type=Path, default=ALGO_SRC)
    parser.add_argument("--appendix-data", type=Path, default=APPENDIX_DATA)
    parser.add_argument("--output", type=Path, default=ROOT / "booklet.tex")
    args = parser.parse_args()
    rendered = render_booklet(args.algo_src, args.appendix_data)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Generated {args.output} ({len(rendered.splitlines())} lines)")


if __name__ == "__main__":
    main()
