# `.devcontainer/` notes

## Copilot Chat-only Codespaces contract

The supported repository declaration is `GitHub.copilot-chat` only. A
genuinely new Codespace accepted that contract at exact signed packet SHA
`9c5ad455ae791d68e71bbe254c043acd11f3cca0` on 2026-07-25:

- VS Code was `1.131.0-insider` at commit
  `b9ebf999d312fa4a308b624eef68731c6057459a`;
- Copilot Chat was built in, account sign-in succeeded, and the Interviewer
  completed `/comments arrays two_sum` through immediate candidate tabs,
  ordinary saved Python comments, 9 passing tests, the REPL, `STATE: CLOSE`,
  and two identical finish commands that left one matching rep-log record; and
- no migration or extension-install popup was visible during the rep.

The [VS Code 1.109 release notes](https://code.visualstudio.com/updates/v1_109)
state that VS Code deprecated `GitHub.copilot`, automatically uninstalls it,
and serves the complete experience through Copilot Chat. The
[VS Code 1.116 release notes](https://code.visualstudio.com/updates/v1_116)
make Copilot Chat built in. However, GitHub's current
[Codespaces Copilot guide](https://docs.github.com/en/codespaces/reference/using-github-copilot-in-github-codespaces?tool=vscode)
still tells repositories to declare `GitHub.copilot`. The exact-head live rep
is the deciding evidence for this repository. Six `PendingMigrationError`
entries rooted in built-in `GitHub.codespaces` 1.18.15 did not prevent this
rep and remain a separate upstream lane, documented below. Repeated command
confirmations under VS Code's `Default approvals` are tracked separately in
[packet issue #107](https://github.com/Jesssullivan/dsa-study-packet/issues/107).

### Repeat the exact-head acceptance

Repository automation can verify the declared extension list and the portable
practice loop. It cannot prove account state, entitlement, extension-host
health, editor tabs, or the absence of migration popups. Those require one
new Codespace:

1. Point a uniquely named disposable branch at the commit under test and push
   that branch. Use the `codespaces-acceptance-` prefix so it cannot be
   mistaken for a product branch:

   ```bash
   BRANCH="codespaces-acceptance-<unique-suffix>"
   git branch "$BRANCH" <commit-under-test>
   git push origin "$BRANCH"
   just codespaces-acceptance-plan "$BRANCH"
   ```

   The command resolves the remote branch through the GitHub API, prints its
   exact `EXPECTED_SHA`, and proves repository API authentication. That local
   GitHub authentication is separate from Copilot account state.
2. Use the emitted `CREATE_URL`. Its shape is
   `https://codespaces.new/Jesssullivan/dsa-study-packet/tree/<disposable-branch>`.
   It has no quickstart query because acceptance must create a new workspace,
   not resume a matching one.
3. After the browser editor attaches, use its integrated terminal to assert
   the exact checkout:

   ```bash
   just codespaces-acceptance-verify <EXPECTED_SHA>
   ```

   The verifier fails on a non-Codespaces environment, wrong repository, wrong
   SHA, tracked mutation, or unexpected untracked input. Gitignored private
   practice state does not invalidate the commit proof. It records VS Code and
   extension versions, but deliberately
   reports Copilot sign-in and entitlement as manual UI checks. A branch name,
   repository access, or a successful checkout proves none of those.
4. In the VS Code UI, separately confirm Copilot Chat sign-in, entitlement,
   the Interviewer agent, and that no extension migration/install popup
   appeared. Repository and GitHub CLI authentication do not prove Copilot
   access.
5. Run `/comments arrays two_sum`. Record that the exact candidate source and
   test tabs open, then use ordinary saved Python comments or a docstring,
   `/continue`, focused tests, the REPL, `STATE: CLOSE`, and an idempotent
   finish.
6. Stop or delete the test Codespace when evidence is captured. Remove the
   disposable branch through the separately reviewed remote-ref cleanup.

Do not describe a resumed Codespace, a local devcontainer, or the headless
smoke workflow as this acceptance. If the live check fails, preserve the exact
VS Code and extension logs before changing the extension list again.

## Known upstream Codespaces blocker: `PendingMigrationError`

**Status:** unresolved upstream; there is no known working repository
workaround.

A fresh Codespace at exact packet SHA
`534fca42b4df9acc028bae6257f80763d4678e51` disproved the former
container-wide `NODE_OPTIONS` preload:

- the VS Code server process inherited `NODE_OPTIONS`;
- the remote extension-host process had `NODE_OPTIONS` unset because VS
  Code's `extensionHostProcess.js` removes it before extension startup; and
- `remoteexthost.log` still recorded repeated `PendingMigrationError` stacks
  rooted in the built-in `GitHub.codespaces` 1.18.15 extension.

The preload therefore never reached the process where the observed failure
occurred. It also changed every ordinary Node process in the container, and
a missing preload file could make those processes fail before VS Code
attached. The file and wiring were removed under
[packet issue #105](https://github.com/Jesssullivan/dsa-study-packet/issues/105).

Removal does **not** mean the upstream problem is fixed. Track
[microsoft/vscode#312110](https://github.com/microsoft/vscode/issues/312110)
as a related upstream `PendingMigrationError` report, not proof of an
identical root cause. Its published stack is rooted in bundled Copilot; this
exact-head Codespace's observed stack was rooted in built-in
`GitHub.codespaces` 1.18.15. Require a new exact-head Codespace acceptance
run before changing status. Copilot Chat-only extension selection was accepted
under
[packet issue #94](https://github.com/Jesssullivan/dsa-study-packet/issues/94);
future changes to that declaration require repeating the acceptance above.

### Operator-safe evidence

For a new reproduction:

1. Create a new branch-specific Codespace and record its checkout SHA, VS
   Code version, and extension versions.
2. Verify Copilot sign-in and entitlement in the editor UI. Do not use
   repository `gh` authentication as a proxy.
3. Compare only the presence or absence of `NODE_OPTIONS` in the VS Code
   server and remote extension-host processes. Do not publish full process
   environments, settings sync data, or complete logs.
4. Extract only the relevant `PendingMigrationError` stack and extension
   identifier from `remoteexthost.log`. Redact tokens, user paths, and
   unrelated extension data.
5. Run the source-native practice acceptance separately, then stop or delete
   the disposable Codespace.

The practice acceptance remains the product signal. Process and log evidence
only establishes where the upstream editor failure occurs; it must not be
used to infer that the learner workflow passed.
