#!/usr/bin/env bash
# Explicit, offline orientation. Agent tooling is a personal choice.
set -euo pipefail
cat <<'WELCOME'

The DSA Woodshed

Start with `just session`: choose how to use the time you have.
Check your environment with `just env-check`; see every command with `just`.

Practice runs locally with Python. Your work stays in gitignored .challenges/.
An assistant is optional; bring the tools you prefer on your personal fork.
Protected services are optional: `just protected-capability` reports whether
the installed seat adapter validates local runtime bindings. Current issuer
authorization is not checked; public practice remains independent.

WELCOME
