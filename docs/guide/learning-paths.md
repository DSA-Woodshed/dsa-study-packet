---
title: Learning Paths
description: Follow curated problem sequences that build pattern recognition through the same comments, code, tests, and reflection loop.
---

# Learning Paths

These four sequences order existing problems so each one reuses an idea from
the previous one. The [decision tree](when-to-use-what.md) helps you identify a
pattern; this page tells you what to learn next.

## Use the same loop for every problem

Start from a table entry with your preferred reasoning vocabulary:

```bash
just practice-start reacto arrays two_sum
# write source comments, save, continue, implement, and add tests
just practice-next
just practice-test
just practice-finish "one fix"
```

You can choose ordinary comments with `just practice-start comments arrays two_sum`. Replace `reacto`
with `clarp`, `umpire`, or `comments` without changing the save-and-continue
loop.

## Choose a path

| Path | What you build | Prerequisites | Core problems |
|------|----------------|---------------|-------------|
| **1: Foundations** | Scanning a sequence with auxiliary state | Python fluency, [Big-O basics](../reference/04-big-o-complexity.md) | 11 |
| **2: Graphs & Trees** | Traversal, ordering, weighted and heuristic search | Path 1, [data-structure sheet](../reference/02-data-structures.md) | 16 |
| **3: DP & Backtracking** | Recursion trees, then memoized optimization | Path 1, recursion comfort | 16 |
| **4: Systems & CS Fundamentals** | Building-block structures and their theory | Path 1, [system-design sheet](../reference/06-system-design.md) | 15 plus appendix |

Start with Foundations. Paths 2 and 3 can follow in either order. Use Path 4
after the basic sequence patterns feel familiar.

## Path 1: Foundations

Carry just enough state through one pass: first a map, then pointers, a window,
and a stack.

| # | Problem | What it teaches |
|---|---------|-----------------|
| 1 | [`arrays/two_sum`](../algorithms/arrays/two_sum.md) | Trade space for time with a hash map |
| 2 | [`arrays/group_anagrams`](../algorithms/arrays/group_anagrams.md) | Hash a *canonical key*, not the value |
| 3 | [`arrays/product_except_self`](../algorithms/arrays/product_except_self.md) | Prefix/suffix passes without division |
| 4 | [`two_pointers/three_sum`](../algorithms/two_pointers/three_sum.md) | Sort, then converge two pointers |
| 5 | [`two_pointers/container_with_most_water`](../algorithms/two_pointers/container_with_most_water.md) | Move the pointer that can only help |
| 6 | [`two_pointers/trapping_rain_water`](../algorithms/two_pointers/trapping_rain_water.md) | Pointers plus running maxima |
| 7 | [`sliding_window/longest_substring_no_repeat`](../algorithms/sliding_window/longest_substring_no_repeat.md) | Variable window plus a seen-set |
| 8 | [`sliding_window/min_window_substring`](../algorithms/sliding_window/min_window_substring.md) | Window with need/have counts |
| 9 | [`stacks_queues/valid_parentheses`](../algorithms/stacks_queues/valid_parentheses.md) | LIFO matching |
| 10 | [`stacks_queues/daily_temperatures`](../algorithms/stacks_queues/daily_temperatures.md) | Monotonic stack for next greater |
| 11 | [`stacks_queues/min_stack`](../algorithms/stacks_queues/min_stack.md) | O(1) minimum with an auxiliary stack |

Extensions: [`strings/valid_anagram`](../algorithms/strings/valid_anagram.md),
[`strings/valid_palindrome`](../algorithms/strings/valid_palindrome.md), and
[`arrays/top_k_frequent`](../algorithms/arrays/top_k_frequent.md).

## Path 2: Graphs & Trees

Master traversal on trees, generalize it to graphs, then add ordering, weights,
heuristics, and global structure.

| # | Problem | What it teaches |
|---|---------|-----------------|
| 1 | [`trees/max_depth`](../algorithms/trees/max_depth.md) | Recursion baseline on a tree |
| 2 | [`trees/invert_tree`](../algorithms/trees/invert_tree.md) | Structural recursion |
| 3 | [`trees/level_order_traversal`](../algorithms/trees/level_order_traversal.md) | BFS with a queue |
| 4 | [`trees/validate_bst`](../algorithms/trees/validate_bst.md) | DFS carrying bounds or inorder state |
| 5 | [`trees/trie`](../algorithms/trees/trie.md) | Design a multiway prefix tree |
| 6 | [`graphs/number_of_islands`](../algorithms/graphs/number_of_islands.md) | Grid DFS/BFS flood fill |
| 7 | [`graphs/clone_graph`](../algorithms/graphs/clone_graph.md) | Traversal plus a visited map |
| 8 | [`graphs/course_schedule`](../algorithms/graphs/course_schedule.md) | Cycle detection in a DAG |
| 9 | [`graphs/topological_sort`](../algorithms/graphs/topological_sort.md) | Dependency ordering with Kahn or DFS |
| 10 | [`graphs/word_ladder`](../algorithms/graphs/word_ladder.md) | BFS shortest path on an implicit graph |
| 11 | [`graphs/dijkstra`](../algorithms/graphs/dijkstra.md) | Weighted shortest path with non-negative edges |
| 12 | [`graphs/network_delay_time`](../algorithms/graphs/network_delay_time.md) | Apply Dijkstra to a prompt |
| 13 | [`graphs/bellman_ford`](../algorithms/graphs/bellman_ford.md) | Negative edges and relaxation |
| 14 | [`graphs/a_star_search`](../algorithms/graphs/a_star_search.md) | Heuristic-guided search |
| 15 | [`graphs/minimum_spanning_tree`](../algorithms/graphs/minimum_spanning_tree.md) | Global structure plus union-find |
| 16 | [`graphs/network_flow`](../algorithms/graphs/network_flow.md) | Max flow and min cut |

Spatial extensions: [`graphs/geohash_grid`](../algorithms/graphs/geohash_grid.md)
and [`graphs/kd_tree`](../algorithms/graphs/kd_tree.md).

## Path 3: DP & Backtracking

Trace the recursion tree first. Then recognize repeated subproblems and cache
them.

| # | Problem | What it teaches |
|---|---------|-----------------|
| 1 | [`recursion/pow_x_n`](../algorithms/recursion/pow_x_n.md) | Divide-and-conquer recursion |
| 2 | [`recursion/tower_of_hanoi`](../algorithms/recursion/tower_of_hanoi.md) | Recursive decomposition |
| 3 | [`recursion/generate_parentheses`](../algorithms/recursion/generate_parentheses.md) | Recursion under a constraint |
| 4 | [`backtracking/subsets`](../algorithms/backtracking/subsets.md) | Choose, explore, unchoose |
| 5 | [`backtracking/permutations`](../algorithms/backtracking/permutations.md) | Used-set bookkeeping |
| 6 | [`backtracking/combination_sum`](../algorithms/backtracking/combination_sum.md) | Reuse elements plus pruning |
| 7 | [`recursion/letter_combinations_phone`](../algorithms/recursion/letter_combinations_phone.md) | Cartesian-product backtracking |
| 8 | [`backtracking/n_queens`](../algorithms/backtracking/n_queens.md) | Constraint pruning at scale |
| 9 | [`dp/climbing_stairs`](../algorithms/dp/climbing_stairs.md) | Turn a recurrence into 1D DP |
| 10 | [`dp/coin_change`](../algorithms/dp/coin_change.md) | Unbounded DP that minimizes cost |
| 11 | [`dp/knapsack`](../algorithms/dp/knapsack.md) | 0/1 DP with space optimization |
| 12 | [`dp/longest_increasing_subseq`](../algorithms/dp/longest_increasing_subseq.md) | DP plus binary search |
| 13 | [`dp/longest_common_subseq`](../algorithms/dp/longest_common_subseq.md) | 2D DP over two strings |
| 14 | [`dp/edit_distance`](../algorithms/dp/edit_distance.md) | 2D DP with three transitions |
| 15 | [`dp/constraint_satisfaction`](../algorithms/dp/constraint_satisfaction.md) | DP under explicit constraints |
| 16 | [`dp/traveling_salesman_dp`](../algorithms/dp/traveling_salesman_dp.md) | Bitmask DP |

Contrast DP with greedy choices in
[`greedy/merge_intervals`](../algorithms/greedy/merge_intervals.md),
[`greedy/jump_game`](../algorithms/greedy/jump_game.md), and
[`greedy/interval_scheduling`](../algorithms/greedy/interval_scheduling.md).

## Path 4: Systems & CS Fundamentals

Build common structures, then connect them to the theory that explains their
costs and failure modes.

| # | Problem | What it teaches |
|---|---------|-----------------|
| 1 | [`searching/binary_search`](../algorithms/searching/binary_search.md) | Loop-invariant discipline |
| 2 | [`searching/find_minimum_rotated`](../algorithms/searching/find_minimum_rotated.md) | Binary search on a pivot |
| 3 | [`searching/search_rotated_array`](../algorithms/searching/search_rotated_array.md) | Binary search on transformed input |
| 4 | [`sorting/quickselect`](../algorithms/sorting/quickselect.md) | Partition-based expected O(n) selection |
| 5 | [`sorting/merge_sort_inversions`](../algorithms/sorting/merge_sort_inversions.md) | Divide-and-conquer plus counting |
| 6 | [`heaps/kth_largest`](../algorithms/heaps/kth_largest.md) | Heap of size k |
| 7 | [`heaps/merge_k_sorted_lists`](../algorithms/heaps/merge_k_sorted_lists.md) | k-way merge with a heap |
| 8 | [`heaps/task_scheduler`](../algorithms/heaps/task_scheduler.md) | Heap plus greedy scheduling |
| 9 | [`linked_lists/reverse_linked_list`](../algorithms/linked_lists/reverse_linked_list.md) | Pointer updates |
| 10 | [`linked_lists/merge_two_sorted`](../algorithms/linked_lists/merge_two_sorted.md) | Merge on linked nodes |
| 11 | [`linked_lists/lru_cache`](../algorithms/linked_lists/lru_cache.md) | Hash map plus doubly linked list |
| 12 | [`bit_manipulation/single_number`](../algorithms/bit_manipulation/single_number.md) | XOR identities |
| 13 | [`bit_manipulation/counting_bits`](../algorithms/bit_manipulation/counting_bits.md) | DP over bit patterns |
| 14 | [`bit_manipulation/reverse_bits`](../algorithms/bit_manipulation/reverse_bits.md) | Fixed-width bit operations |
| 15 | [`math/sieve_of_eratosthenes`](../algorithms/math/sieve_of_eratosthenes.md) | Precompute primes once, amortize over many queries |

### Appendix reading

| Appendix topic | Read it alongside |
|----------------|-------------------|
| Hash Table Internals | `arrays/two_sum`, `arrays/group_anagrams`, `linked_lists/lru_cache` |
| Amortized Analysis | `stacks_queues/daily_temperatures`, `sorting/quickselect`, dynamic arrays |
| Concurrency & Parallelism Primitives | `heaps/task_scheduler` |
| Recursion to Iteration Conversion | `recursion/tower_of_hanoi`, `recursion/pow_x_n`, `recursion/flatten_nested_list` |
| Fixed-Width & Numeric Pitfalls | `bit_manipulation/reverse_bits`, `bit_manipulation/single_number`, `strings/string_to_integer_atoi` |

## Pace the work

- **Two weeks:** finish Foundations, choose Path 2 or 3, then sample the other
  and Path 4.
- **Four weeks:** give each path one week and use extensions for weak signals.
- **Maintenance:** let `just practice-start reacto` draw due problems across
  topics.

Move forward when you can explain and trace the pattern, not when every row is
checked. Revisit due problems through the queue. Use full
[algorithm pages](../algorithms/index.md) after the rep when you need a worked
reference.
