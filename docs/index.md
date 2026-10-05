---
title: The DSA Woodshed
---

# The DSA Woodshed

Practice technical interviews in a real editor: explain the problem in
comments, implement a solution, write focused tests, and keep one correction.

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Start**

    ---

    Open Codespaces and begin an editor rep.

    [:octicons-mark-github-24: Open in Codespaces](https://codespaces.new/DSA-Woodshed/dsa-study-packet?quickstart=1)

-   :material-code-braces:{ .lg .middle } **Practice Problems**

    ---

    Choose from the 43 core problems and the extended set.

    [:octicons-arrow-right-24: Choose a Problem](challenges/index.md)

-   :material-account-voice:{ .lg .middle } **Method**

    ---

    Learn the comment-first loop and its practice modes.

    [:octicons-arrow-right-24: Getting Started](guide/getting-started.md)

-   :material-book-open-variant:{ .lg .middle } **Library**

    ---

    Review complete solutions, concepts, and printable sheets.

    [:octicons-arrow-right-24: Browse Reference](reference/index.md)

</div>

## Your first rep

Start with `just session` to choose time, activity, feedback, and workspace.
For a direct rep, run `just practice-start comments`; no topic is required.
Choose a pair with `just practice-start comments arrays two_sum`.
Basic practice needs no private credential or assistant subscription.

Your source and test file open under `.challenges/workspace/`. Write ordinary
comments or docstrings in the source file, save, then run `just practice-next`.
Implement and add focused tests. Optional named modes offer scaffolding for
the same loop; chosen assistant tools use the same product commands.

```bash
just practice-next
just practice-test
just practice-repl
just practice-finish "one fix"
```

The committed solutions under `src/algo/` stay unchanged. Your workspace and
rep history remain private and gitignored.

Use the [decision tree](guide/when-to-use-what.md) when pattern selection is
the gap, or browse [complete implementations](algorithms/index.md) after a rep.
The [practice evidence](guide/interview-practice-evidence.md) explains the
larger method. A printable packet is also available for offline review.

[:material-map: Read the Full Loop](guide/getting-started.md){ .md-button .md-button--primary }
[:material-download: Download PDF](assets/booklet.pdf){ .md-button }
