# A portable practice environment

Open a Codespace on your personal fork or use the development container locally.
The same public Python practice commands run without an identity service. Start
with `just session` to choose how much time to spend and how to practice.

Container lifecycle commands prepare `.challenges/` automatically. In a native
checkout, run `just env-setup` once. Use `just env-check` to check Python 3.14,
pytest, uv and Just. Container lifecycle commands install the pinned
public toolchain and sync `uv.lock`. Local contributors can use the public Nix
shell for build and publication tools when needed; practice itself uses Python.

Your candidate code, tests and session state stay in regular, gitignored
`.challenges/`. In Codespaces the entire checkout is on persistent `/workspaces`
storage. A rebuild keeps this directory; a deleted Codespace does not. Keep
private exports outside Git and push intended source changes to your own fork.

Protected services are optional. `just protected-capability` calls only an
independently installed `portable-seat-attach` adapter. Success reports
`protected_capabilities: local-runtime-validated`: local runtime bindings
passed, with `issuer_authorization: not-checked`. This does not authenticate a
learner, establish a current issuer grant, or check server-side withdrawal.
Missing, untrusted, refused or hung adapters report `unavailable` and exit78;
public practice remains independent. The
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

On 2026-10-06, source `224cdb0fcf6f6693eed4ee8f142fc3c3722c4abb` passed
automatic cold startup in a new GitHub Codespace created from the true personal
contribution fork. The digest-only base reference, public OpenSSH package and
normal Codespaces runtime completed every configured lifecycle phase as UID1000.
No manual bootstrap was used. A terminal dialogue selected implementation,
30 minutes and Two Sum; candidate-owned source and four focused tests completed
11 reference and candidate tests, followed by explicit, idempotent session finish.
All 13 private practice files retained identical hashes after a confirmed
stop/start and an official full rebuild. Startup regenerated this container's
machine keys, and public readiness passed after both operations. The absent
protected adapter still returned exit78.

This hosted run selected headless mode explicitly. The platform's `code` wrapper
reported that an editor was not installed before a native browser or desktop
attachment. Candidate-tab opening and native Codespaces editor authorization
remain unverified by this run. These public lifecycle results do not commission
an identity issuer or an optional feedback provider. GitHub CLI SSH automation
uses a login shell (`bash -l`) so it loads the normal user tool paths.

On 2026-10-06, source `b939b85a62a2b41e705ac3bb87c52716dd851322`, whose
tree matches canonical `a45986322db556f383b99ab227f90779096b71ef`, passed a
separate native editor check in VS Code 1.140.0 with the official Codespaces
extension. After supported GitHub sign-in and a user window reload,
`just practice-open` opened the existing Two Sum candidate source and candidate
test. Both files were verified in the connected editor. All 13 private practice
files retained identical hashes, and tracked source remained unchanged. Opening
the files ran no tests and started no new session. This result covers native
editor attachment and candidate-tab opening; protected identity and feedback
services still require separate commissioning.
