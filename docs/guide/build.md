# Public build graph

The maintainer graph uses Bazel 9.0.1, a downloaded Python 3.14.3 interpreter,
and public registries. It requires no virtual environment, private cache,
credential helper, or remote executor. Use the repository's Just entrypoints
for normal work. Focused learner tests, watch, and REPL remain uv workflows.

`//tools:check` runs the algorithm and concept suites, pure Python tooling
tests, Ruff, and mypy. It installs every concept dependency, so optional
imports cannot hide missing coverage. Editor, git, installation, and command
integration tests run once in uv's separate integration lane. Both runners
consume the literal lists in `tools/test_lanes.bzl`; a tracked test must belong
to exactly one lane, with the public booklet smoke check kept separate.
`tools/run_integration.py --check-only` validates that partition without running
tests; invoking it without that flag runs only the integration files. The
learner's full uv test command still runs every Python test when requested.
The Bazel runner copies only
declared files into its writable test directory; resolving a test's filename
cannot expose an ambient checkout. Property tests use 200 deterministic
examples, no persisted database, and no host-timing oracle.

`//:booklet` generates `//:booklet.tex` from committed algorithm sources and
the appendix JSON before compiling. Generated files never belong in a release
source archive. A downstream private module depends on the neutral PDF and
composes its own material; public compilation never reads the private overlay.

The compiler reads a deterministic ZIP assembled from
`build_support/tex-resources.lock.json`. Each resource specifies an official
TeXLive URL, byte range, and SHA-256 digest. Only 15 MB of resource data is
fetched from the 2.68 GB source tar. The target supplies Tectonic's deterministic
mode, and the booklet omits a wall-clock date. Missing or changed resources
fail the build. TeX resources retain their upstream licensing; the lock does
not redistribute a TeX distribution.

Update `tools/requirements.lock.txt` with a locked uv export whenever the
dependency lock changes:

```sh
uv export --extra dev --extra concepts --no-dev --no-emit-project --no-header \
  --locked --output-file tools/requirements.lock.txt
```

For a deliberate TeX resource update, compile the generated TeX once using
Tectonic 0.16.9 and an empty task-owned `TECTONIC_CACHE_DIR`, specifying the
official versioned bundle URL. Then record that cache using
`build_support/lock_tex_resources.py --cache CACHE --bundle-digest DIGEST
--url URL --output build_support/tex-resources.lock.json`. Validate the updated
lock through an offline bundle compile and a detached archive consumer before
publishing. Never silently fall back to an unpinned network bundle.

A detached consumer pins the public registry revision containing packet 0.2.0
and declares `bazel_dep(name = "dsa_study_packet", version = "0.2.0")`.
Building `@dsa_study_packet//:booklet` needs only the published source archive
and declared public toolchain/resource downloads.

Packet module 0.2.0 repairs the missing generated-source input in 0.1.0.
Existing published versions remain immutable; the broken version is yanked
with its failure reason. The source repository registry pin supplies its
toolchains and need not contain its own subsequently published module.
