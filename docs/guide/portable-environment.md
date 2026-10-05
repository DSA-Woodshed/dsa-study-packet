# A portable practice environment

Open a Codespace on your personal fork or use the development container locally.
The same public Python practice commands run without an identity service. Start
with `just session` to choose how much time to spend and how to practice.

Run `just env-setup` once to prepare `.challenges/`, then `just env-check` to check
Python 3.14, pytest, uv and Just. Container lifecycle commands install the pinned
public toolchain and sync `uv.lock`. Local contributors can use the public Nix
shell for build and publication tools when needed; practice itself uses Python.

Your candidate code, tests and session state stay in regular, gitignored
`.challenges/`. In Codespaces the entire checkout is on persistent `/workspaces`
storage. A rebuild keeps this directory; a deleted Codespace does not. Keep
private exports outside Git and push intended source changes to your own fork.

Protected services are optional. `just protected-capability` calls only an
independently installed `portable-seat-attach` adapter, which validates its own
admitted runtime. If unavailable, the command says so and exits nonzero. The
public packet supplies no identity endpoint, wrapping token or age identity.
Authenticate only through the owning service's supported seat workflow after
startup. Short-lived wrapping tokens must be minted after the environment is
ready and handed off privately; they do not belong in prebuilds or source files.
