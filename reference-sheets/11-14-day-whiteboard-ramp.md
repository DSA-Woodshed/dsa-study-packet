# 14-Day Interview Practice Ramp

This is the day-by-day calendar for the two weeks before a live-coding
interview. The default is editor-first practice with comments, working code,
focused tests, and one correction. Timed board or observed work appears only
when pressure is the skill being trained. The broader method and rubric live
in [sheet 10](10-whiteboard-performance-protocol.md).

## Keep nearby

- **The booklet** (`booklet.pdf`): decision trees and one algorithm per page.
- **Sheets 01, 03, 05**: standard library, templates, and pattern triggers.
- **Sheet 10**: interview method and optional pressure protocol.
- **Sheet 07**: interview-day logistics for Week 2.

## The daily editor loop

1. **Pick**: run `just study-spaced 1` and use its printed editor command.
2. **Think**: write ordinary source comments or docstrings in your own words,
   then save and explicitly continue.
3. **Build**: implement in the isolated source and add cases in your test tab.
4. **Check**: use `just practice-next`, then run `just
   practice-test` or `just practice-repl`.
5. **Reflect**: trace one example and reconcile comments with the code.
6. **Close**: name one win and one fix, then run `just practice-finish "one
   specific fix"`. This saves the note and schedules review together.

## Four-hour allocation

| Time | Work |
|------|------|
| 0:00-0:10 | Arrival ritual: breathing + worry dump + reappraisal + choose first draw |
| 0:10-1:40 | One or two cold editor reps with comments, code, and focused tests |
| 1:40-1:55 | Real break |
| 1:55-2:55 | Trace, REPL, and test work on the single largest miss |
| 2:55-3:40 | Optional observed or timed rep; otherwise another editor rep |
| 3:40-4:00 | One-fix closeout and tomorrow's first draw |

## Example cycle (fill in your own dates)

> This run: **Day 1 = Sun Jul 5, 2026**, interviews ≈ Jul 20. Adjust the anchor;
> the shape holds for any two-week window.

## Week 1: build the editor reflex

| Day | Focus | Problems | Sheets open | Observer |
|-----|-------|---------------------------|-------------|----------|
| **1** | Read sheet 10, then easy arrays | `arrays two_sum`, `arrays group_anagrams` | 10, 03, 01 | none |
| **2** | Arrays + stacks/queues | `arrays product_except_self`, `stacks_queues valid_parentheses`, `stacks_queues daily_temperatures` | 03, 05, 01 | none |
| **3** | Sliding window + binary search; narrate one recovery from a blank | `sliding_window longest_substring_no_repeat`, `searching binary_search`, `searching search_rotated_array` | 03, 05 | none |
| **4** | BFS/DFS + linked lists | `graphs number_of_islands`, `graphs course_schedule`, `linked_lists reverse_linked_list` | 03, 02 | none |
| **5** | Trees + heaps; first optional human-observed editor rep | `trees validate_bst`, `trees level_order_traversal`, `heaps kth_largest` | 02, 03 | person |
| **6** | Trees/trie + shore up your weakest rubric row | `trees trie`, 2 review draws | 08, 02 | person |
| **7** | **Rest** (or one light review rep). Rest is training. | none | none | none |

## Week 2: breadth plus optional pressure

| Day | Focus | Problems | Sheets open | Observer |
|-----|-------|---------------------------|-------------|----------|
| **8** | Graphs, the heaviest topic | `graphs dijkstra`, `graphs topological_sort`, `graphs bellman_ford` | 03, 06 | optional person |
| **9** | Dynamic programming | `dp coin_change`, `dp edit_distance`, `dp knapsack`, `dp longest_increasing_subseq` | 03 | person interrupts |
| **10** | Mixed cold draws; optionally time one editor rep at 35 minutes | `just study-spaced 3` | 07, 05 | optional person |
| **11** | Backtracking + greedy + strings | `backtracking subsets`, `backtracking n_queens`, `greedy merge_intervals`, `strings valid_palindrome` | 03, 05 | person |
| **12** | **Observed live-coding mock** with back-to-back editor problems | 3 cold draws | 07, 10 (§7 card) | **person** |
| **13** | Taper. Review your best rep notes and run one light editor rep. | 1 easy draw | 10 (§7) | none |
| **14** | Rest. Read the sheet-10 §7 card and sheet 07. | none | 10 (§7), 07 | none |

The target is one improved signal per day, not a perfect score or a completed
row count.
