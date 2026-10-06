---
title: Source of Truth
description: See which files own the current Python practice track, generated artifacts, private state, and the production reading site.
---

# Source of Truth

This project treats source code, tests, and authored notes as durable study
material. Generated docs and PDFs must be reproducible from those inputs, and
employer-specific interview prep must never enter this tree. This page is the
whole contract.

The runnable interview track is currently Python. Cross-language comparisons
in reference material are context, not runnable practice tracks.

## Authored Material

| Path | Purpose |
|------|---------|
| `src/algo/` | Algorithm implementations and docstrings |
| `tests/` | Examples and property-based correctness checks |
| `src/concepts/` | Technical concept modules |
| `src/practice/` | Code-reading and decomposition exercises |
| `reference-sheets/` | Printable notes, quick-reference sheets, and the practice method (sheets 10–11) |
| `reference-sheets/appendix-topics.json` | Structured appendix topics rendered into the booklet compile-safely |

## Generated Material

| Output | Command |
|--------|---------|
| `bazel-bin/booklet.tex` / `bazel-bin/booklet.pdf` | generated within `just packet` |
| `booklet.pdf` / `docs/assets/booklet.pdf` | copied from the Bazel output by `just packet` |
| `reference-sheets/pdf/*.pdf` | `just pdf-all` |
| local MkDocs output in `site/` | `just docs-build` |

Production reading pages use a separate static site repository. Its
`scripts/sync-content.mjs` resolves one exact public packet commit and reads
every synced source from that revision. It records the commit, source paths,
and digests in `src/content/.manifest.json`. The site verifies those digests
before it prerenders
[dsa-woodshed.space](https://dsa-woodshed.space). This repository owns the
content; the site repository owns the shell, navigation, and rendering. The
local `site/` output is a development artifact, not the production deployment.
The canonical reading site is live. The packet's legacy GitHub Pages setting
and its `gh-pages` branch are retired. No main-branch workflow deploys packet
Pages; never restore a second reading surface.

## Three Layers

| Layer | What | Where | Public? |
|-------|------|-------|---------|
| **L1: knowledge** | algorithms, tests, concepts, reference sheets 01–09 | this repo | ✅ |
| **L2: practice method** | sheets 10–11; `just practice-open`, `just practice-study`, `just practice-start`, `just practice-start-tests`, `just practice-next`, `just practice-test`, `just interview`, atomic finish commands, and spaced repetition | this repo | ✅ |
| **L3: private overlay** | employer/panel front & back matter, people, dates, tailored positioning, personal rep logs | a private downstream repo | ⛔ never here |

The distinction that keeps this publishable: L2 is a *method* ("how to reason,
code, test, and narrate under observation," a general, teachable skill); L3 is a
*dossier* (who is on Tuesday's panel). Method publishes; dossier never touches
this tree. **If a sentence only makes sense for one employer, it is L3.**

## The Graph Edge Is One-Way

```
private superset repo                    THIS REPO (public)
─────────────────────                    ──────────────────
bazel_dep + path/git override   ──────▶  module(name = "dsa_study_packet")
\includepdf{@dsa_study_packet            //:booklet  (neutral PDF)
            //:booklet}
+ private front/back matter (L3)
→ private //:study_packets
```

The private repo depends on this one; this repo knows nothing about any
downstream. Composition is **overlay, not bundle**: the neutral booklet is
compiled *here* from *this* tree (so it cannot contain employer text), and a
private lane `\includepdf`s the finished PDF between its own front and back
matter. The two bodies of text only ever meet as adjacent pages in a private
output, never in source. Delete the private repo and this SSOT is unchanged
and complete. `examples/overlay-demo/` is a self-contained, fork-me
demonstration of the pattern with placeholder content.

## The Boundary Is Enforced

`scripts/check_public_boundary.py` (`just public-boundary`) fails if any
tracked file contains secret-shaped content or secret-file paths: tracked SOPS
or dotenv files, age keys, GitHub tokens, private-key blocks, legacy secret
tripwires. Name-specific tripwires (employers, panels, private repo names) are
deliberately **not** listed here. The private downstream repo scans this tree
with its own marker list, so the public guard cannot itself disclose what it
guards against. Neutrality is a machine check, not a promise.
Personal rep scores (`.challenges/reps.md`) are gitignored by default;
publish aggregates deliberately, or not at all.

## Who Owns The Practice Method

L2 is one loop described by the following authored surfaces. Each surface owns exactly one
question about it; none restates another's answer.

| Surface | Owns | Does not own |
|---------|------|---------------|
| [Sheet 10](../reference/10-whiteboard-performance-protocol.md) | the CLARP method + self-review rubric: *how* to perform | no calendar, no daily loop |
| [Sheet 11](../reference/11-14-day-whiteboard-ramp.md) | the 14-day editor-first calendar: *when*. Its prose feeds `scripts/practice_day.py`; edit sheet 11 itself for loop changes | no method detail, no rubric |
| [Evidence page](interview-practice-evidence.md) | *why*: research citations and the video shelf | no calendar, no rubric scoring |
| `TRACK-CONTRACT.md` | observable command behavior, candidate ownership, states, and test evidence | no provider selection, no private notes |
| `just session` and the catalog | guided activity selection and routing through the product engine | no separate provider engine |
| Personal contribution-fork overlay | optional agent personas, skills, prompts, settings, and notes | no upstream product authority |

A calendar edit belongs in sheet 11; a rubric belongs in the method sheet;
a research citation belongs in the evidence page. Provider choices belong
on a personal fork and route through the canonical product commands.

## Runbook

| I want to… | Do this | Layer |
|------------|---------|-------|
| Add/extend a study or practice sheet | `reference-sheets/NN-*.md` + one-line `docs/reference/NN-*.md` wrapper; nav + PDF pick it up | L1/L2 |
| Add an algorithm | `src/algo/<topic>/<problem>.py` + tests; booklet and site regenerate | L1 |
| Prep for a specific employer/panel | Create a lane in the private downstream repo; author front/back matter there | L3 |
| Keep practice tapes / mock scripts / rep scores | Private repo or gitignored local dir, never tracked here | L3 |
