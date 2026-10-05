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

On 2026-10-05, source `057cfa99cd1a7d4e074bbbe1a59105a9aeb505fb` passed
cold setup, repeated setup and recreated-container setup on a rootless Linux
Podman runtime as UID1000 with all capabilities dropped and no new privileges.
The pinned base image was used with one isolated public workspace mount. All
33 focused environment/configuration tests passed, a real practice rep started,
and all seven practice-state file hashes survived recreation unchanged. The
absent protected adapter returned exit78. This acceptance covers the local
container; real Codespaces lifecycle, editor tabs and identity commissioning
remain separate checks.
