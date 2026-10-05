---
title: Practice Problems
description: Choose an isolated problem and complete one focused rep with reasoning comments, candidate-owned code, and real tests.
---

# Practice Problems

Let the review queue choose the next problem, or select one when you know the
skill you want to isolate. One rep should produce one useful correction, not a
larger solve count.

## Start in the editor

Choose your activity through `just session`, or start a comments-mode rep:

```bash
just practice-start comments
just practice-start comments graphs dijkstra
```

No labels or prefixes are required. The first command draws the next problem;
the second selects an exact pair. Optional `reacto`, `clarp`, and `umpire`
labels offer scaffolding for the same loop.

To study a named problem before a rep, open read-only snapshots of its
committed solution and reference tests:

```bash
just practice-study topic problem
```

Study creates no rep or log. When you are ready, run the exact `IMPLEMENT` or
`TESTS_FIRST` transition it emits. Either one starts a fresh isolated candidate
pair.

Write your comments in the file, save, then run `just
practice-next` for one next instruction. Then implement and add cases in your
test file.

```bash
just practice-test
just practice-repl
just practice-finish "one fix"
```

## Core 43

The core set covers common patterns across sessions. `just catalog` prints all
editor-practice targets and marks each Core or Extra. Add natural names to
search; ambiguous words such as `anagram` and `prime` keep every valid choice.

| Topic | Problems |
|-------|----------|
| Arrays | `two_sum`, `group_anagrams`, `product_except_self`, `top_k_frequent` |
| Two pointers | `three_sum`, `trapping_rain_water` |
| Sliding window | `min_window_substring`, `longest_substring_no_repeat` |
| Stacks and queues | `valid_parentheses`, `daily_temperatures` |
| Searching | `binary_search`, `search_rotated_array` |
| Linked lists | `reverse_linked_list`, `lru_cache` |
| Trees | `validate_bst`, `level_order_traversal`, `trie` |
| Graphs | `number_of_islands`, `topological_sort`, `course_schedule`, `dijkstra`, `a_star_search`, `bellman_ford`, `minimum_spanning_tree` |
| Dynamic programming | `coin_change`, `edit_distance`, `knapsack`, `longest_increasing_subseq`, `longest_common_subseq` |
| Heaps | `kth_largest`, `merge_k_sorted_lists` |
| Backtracking | `subsets`, `combination_sum`, `n_queens` |
| Greedy | `merge_intervals`, `jump_game` |
| Strings | `valid_palindrome`, `longest_palindromic_substring` |
| Recursion | `generate_parentheses`, `flatten_nested_list` |
| Bit manipulation | `single_number` |
| Sorting | `quickselect` |
| Math | `sieve_of_eratosthenes` |

Choose by the signal you want to improve: restating the problem, selecting an
example, recognizing a pattern, implementing cleanly, testing, or explaining
complexity. The [decision tree](../guide/when-to-use-what.md) helps with
pattern selection. Inspect the [algorithm library](../algorithms/index.md)
after the rep reaches a natural stopping point.

## More practice

The repository includes additional problems in the same topic directories.
Any entry from `just catalog` can start with `just practice-start`. Use the
[learning paths](../guide/learning-paths.md) when you want a curated order, or
[extended problems](#extended-problems) for code reading and open-ended
decomposition.

Untimed conversation and timed board-style reps can use the same catalog. The
editor workspace is the default surface, not the only valid one.

## Extended problems

Use these after ordinary editor reps when you want to practice reading
unfamiliar code, finding operational risks, or decomposing an open-ended
system. They supplement the problems above; they do not replace the
comments, code, and tests loop.

### Code reading

The Python files are intentionally buggy or inefficient. For each exercise:

1. Read signatures and docstrings.
2. Trace one execution path.
3. Test empty, large, malformed, and concurrent inputs where relevant.
4. Estimate the time and space cost of the hot path.
5. Propose two or three fixes, ordered by impact.

| Exercise | File | Focus |
|----------|------|-------|
| Caching Service | `src/practice/code_reading/ex01_caching_service.py` | eviction, thread safety |
| Flight Data Pipeline | `src/practice/code_reading/ex02_flight_data_pipeline.py` | streaming, batching, failures |
| Rate Limiter | `src/practice/code_reading/ex03_rate_limiter.py` | token buckets, windows, concurrency |

Check for unbounded memory, nested work on the hot path, missing validation,
shared mutable state, blocking I/O, and calls inside loops. Explain the impact
before proposing a change.

### Problem decomposition

The open-ended prompts train scope, interfaces, tradeoffs, and test strategy.

| Exercise | File | Focus |
|----------|------|-------|
| Vehicle Tracking | `src/practice/decomposition/ex02_vehicle_tracking.md` | geospatial indexing, live updates |

State assumptions, split the system into parts, identify the riskiest seam,
and describe how you would verify it. An untimed conversational rep works well
for a first pass; use an observed mock when concise narration is the target.

For a longer scheduled block, run `just practice-day 12` and follow the
printed stop conditions. Use the daily conductor only when you intend to run
the full block.
