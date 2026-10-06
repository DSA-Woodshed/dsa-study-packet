# The DSA Woodshed development container

The public practice environment needs Python and Just. It installs no agent
client and requests no credentials. Use an assistant of your choice from your
personal fork, or use the command line directly.

`onCreateCommand` installs checksum-pinned uv and Just, plus optional watchexec.
`updateContentCommand` syncs the committed dependency lock with CPython 3.14.6.
These phases are safe for credential-free prebuilds. `postCreateCommand`
prepares private practice storage; `postStartCommand` checks readiness without
starting a practice session. Repeating setup preserves candidate work.

The base image is pinned by digest, and practice commands run as `vscode`.
The small Dockerfile adds a pinned public OpenSSH server for the official
Codespaces CLI tunnel. Machine host keys are generated during `postStartCommand`,
not included in the image; Codespaces manages SSH authentication. This server
does not install assistant extensions or instructions.
The configuration mounts no host Docker socket, age key, signing key, or provider
credential. Local development can use rootless Podman; Codespaces owns its own
container runtime and platform setup. Runtime capability flags belong to a
qualified local launch rather than the portable hosted configuration.

After startup, run `just session` to choose how to use your time, or `just` to
list commands. `just env-check` reports the installed public tools and practice
storage. `just protected-capability` only delegates to an independently installed
and trusted `portable-seat-attach` adapter. Missing or unadmitted identity support
returns an explicit unavailable result and nonzero exit; public practice remains
usable. The repository creates no OpenBao role or token and reads no seat secret.

In Codespaces, the checkout and its regular, gitignored `.challenges/` directory
live under `/workspaces`, which survives stop/start and container rebuilds.
Deletion of a Codespace has a different lifecycle: preserve intended source work
on your fork and explicitly export any private practice data you want to retain.
Never commit private practice state or use a symlink to bypass workspace checks.

Local checks do not prove cloud readiness. Acceptance of a new Codespace requires
its exact source SHA, cold setup, a complete practice session, editor opening,
stop/resume and rebuild readback of candidate files. Protected capabilities also
require independently commissioned identity and an actual adapter acceptance.
