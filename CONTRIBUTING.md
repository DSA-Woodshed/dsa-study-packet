# Contributing

The DSA Woodshed packet owns tested Python reference implementations, the
practice engine, authored study material, and generated print inputs. The
reading site consumes an exact packet revision. Shared contribution policy
lives in [DSA-Woodshed/.github](https://github.com/DSA-Woodshed/.github/blob/main/CONTRIBUTING.md),
following the [GFTB contribution model](https://github.com/Great-Falls-Tool-Bus/.github/blob/main/CONTRIBUTING.md).

## Fork first

Contribute from a personal fork, conventionally named `dsa-study-packet-contrib`.
`origin` is your fork; `upstream` is the organization product. Preserve that
relationship when syncing or opening a pull request. Organization membership
does not change the contribution path.

```bash
git clone https://github.com/YOUR-USER/dsa-study-packet-contrib.git
cd dsa-study-packet-contrib
git remote add upstream "$(python3 -c 'import json; print("https://github.com/" + json.load(open("tinyland.repo.json"))["repo"]["github"] + ".git")')"
git switch -c feat/describe-the-change
just setup
```

`tinyland.repo.json` names the canonical upstream; owner changes update that
authority once. GitHub preserves redirects from historical owner links.
Do not create another product repository. `just setup` installs the shared hooks and locked dependencies.
`just env-setup` prepares the public environment; `just env-check` diagnoses it.
Core practice requires no repository API key or private service. Advanced
protected capabilities are explicitly selected through `just protected-capability`.

`just hooks-install` sets the local hook path, chains any global hook layer,
sets pushes to `origin`, and disables the `upstream` push URL. Keep signed
commits enabled (`git config commit.gpgsign true`) with your own signing key.
Use semantic branches such as `feat/short-name` and conventional subjects such
as `fix: preserve candidate test selection`. Hooks refuse organization pushes,
unsigned new commits, and tool attribution in commit messages. They warn about
unconventional names and em dashes. GitHub-created merge commits are exempt
from the authored-commit signature check.

## Product changes

Add a problem to `scripts/core42.py`, then run `just new topic problem`.
Implement reference source and focused tests together. Candidate exercises
remain isolated under gitignored `.challenges`; do not solve a learner's files
as part of product development. Authored method belongs in the reference
sheets; generated docs and counts follow their source.

Employer-specific prep, credentials, personal rep logs, and tailored notes
belong in private downstream material. See the
[source-of-truth contract](docs/guide/source-of-truth.md).

## Personal tooling

Keep provider settings, agent personas, skills, prompts, plugins, and agent
notes on your personal fork's orphan `agents-overlay` branch. Restore selected
files locally and exclude them with `.git/info/exclude`; do not merge that
branch into the product. The product retains ordinary behavioral contracts,
portable commands, source, and tests. `just lint` checks tracked contributions
without rejecting untracked local overlays.

## Check and contribute back

```bash
just check
just hooks-check
just hooks-test
git push -u origin HEAD
gh pr create --repo DSA-Woodshed/dsa-study-packet
```

The hook implementation is mirrored byte-for-byte from organization
`.github/githooks` into `.githooks`. `just hooks-check` compares the mirror;
`just hooks-test` runs isolated signed/unsigned and fork/org fixtures. Update
shared hooks in the governance repository before refreshing consumers.
`just check` also runs the locked lint and test gates. Include commands and
results in the pull request; rerun after changes that invalidate the evidence.

## Codespaces acceptance

Use a newly created workspace at the exact pushed commit, never a resumed one.
Run `just codespaces-acceptance-plan <disposable-branch>` and open its URL:
`https://codespaces.new/Jesssullivan/dsa-study-packet/tree/<disposable-branch>`.
Then run `just codespaces-acceptance-verify <EXPECTED_SHA>`. Optional agent
provider readiness and protected SSO admission are separate from basic
workspace readiness. Never copy credentials into acceptance evidence.

Maintainers publish CalVer release tags (`vYYYY.M.PATCH`) through the existing
release workflow. Assets remain inventoried on
[GitHub Releases](https://github.com/Jesssullivan/dsa-study-packet/releases).
