#!/usr/bin/env bash
# Self-test for the DSA Woodshed git hooks. Run by `just hooks-test`.
#
# Builds a throwaway repository under ${TMPDIR:-/tmp} with fixture commits
# (signed with a throwaway SSH key, unsigned, AI attribution, em dash, good and
# bad branch names), pushes to local bare repositories standing in for the
# organization remote and a fork, and asserts exit codes and warnings. The
# operator's global and system git configuration is never read: explicit git
# config overrides point into the temporary directory, which is removed on exit.
set -euo pipefail

hooks="$(cd "$(dirname "$0")" && pwd -P)"
work="$(mktemp -d "${TMPDIR:-/tmp}/woodshed-hooks-test.XXXXXX")"
cleanup() {
  rm -rf "$work"
}
trap cleanup EXIT

export GIT_CONFIG_GLOBAL="$work/gitconfig"
export GIT_CONFIG_NOSYSTEM=1
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE SSH_AUTH_SOCK WOODSHED_HOOKS_CHAINED || true
mkdir -p "$work/marks" "$work/global-hooks"

em="$(printf '\342\200\224')"
robot="$(printf '\360\237\244\226')"

# Vendor and GitHub addresses are assembled at run time so no source line
# carries a literal address outside the documentation domains; the public PII
# validators in every repository scan this file. The hooks still see the full
# address.
ai_vendor_domain=anthropic.com
ai_vendor_alt_domain=openai.com
github_domain=github.com
claude_addr="noreply@${ai_vendor_domain}"
codex_addr="codex@${ai_vendor_alt_domain}"
github_merge_addr="noreply@${github_domain}"

# A stand-in for a machine-wide hook layer; records that it was chained to.
for hook in pre-commit commit-msg; do
  printf '#!/usr/bin/env bash\n: > "%s/%s"\n' "$work/marks" "$hook" > "$work/global-hooks/$hook"
done
printf '#!/usr/bin/env bash\ncat > "%s/pre-push"\n' "$work/marks" > "$work/global-hooks/pre-push"
chmod +x "$work/global-hooks/"*

ssh-keygen -q -t ed25519 -N '' -C woodshed-hooks-test -f "$work/signing"
git config --global user.name "Hook Test"
git config --global user.email "hook-test@example.org"
git config --global init.defaultBranch main
git config --global gpg.format ssh
git config --global user.signingkey "$work/signing"
git config --global commit.gpgsign true
git config --global core.hooksPath "$work/global-hooks"

passed=0
failed=0
out="$work/out"

# check NAME WANT_STATUS [--warns|--quiet|--refused] -- COMMAND...
check() {
  local name="$1" want="$2" expect="$3" got
  shift 4
  set +e
  "$@" > "$out" 2>&1
  got=$?
  set -e
  local ok=1
  if [ "$want" = 0 ] && [ "$got" -ne 0 ]; then ok=0; fi
  if [ "$want" != 0 ] && [ "$got" -eq 0 ]; then ok=0; fi
  case "$expect" in
    --warns) grep -q '^woodshed-hooks: warning:' "$out" || ok=0 ;;
    --quiet) grep -q '^woodshed-hooks:' "$out" && ok=0 ;;
    --refused) grep -q '^woodshed-hooks: REFUSED:' "$out" && grep -q '^woodshed-hooks:   fix:' "$out" || ok=0 ;;
  esac
  if [ "$ok" -eq 1 ]; then
    passed=$((passed + 1))
    printf 'ok   %s\n' "$name"
  else
    failed=$((failed + 1))
    printf 'FAIL %s (exit %s, wanted %s, %s)\n' "$name" "$got" "$want" "$expect"
    sed 's/^/     | /' "$out"
  fi
}

mark_check() {
  local name="$1" file="$2"
  if [ -f "$work/marks/$file" ]; then
    passed=$((passed + 1))
    printf 'ok   %s\n' "$name"
  else
    failed=$((failed + 1))
    printf 'FAIL %s (global %s hook did not run)\n' "$name" "$file"
  fi
}

out_has() {
  if grep -qF -- "$2" "$out"; then
    passed=$((passed + 1))
    printf 'ok   %s\n' "$1"
  else
    failed=$((failed + 1))
    printf 'FAIL %s\n' "$1"
  fi
}

repo="$work/repo"
git init -q "$repo"
cd "$repo"
git config core.hooksPath "$hooks"

commit() { git commit -q --allow-empty "$@"; }

# commit-msg and pre-commit
printf 'plain text\n' > a.txt
git add a.txt
check "signed conventional commit passes quietly" 0 --quiet -- commit -m "feat: add a"
mark_check "commit-msg chains to the global hooks path" commit-msg
mark_check "pre-commit chains to the global hooks path" pre-commit
base="$(git rev-parse HEAD)"

check "human Co-Authored-By trailer passes" 0 --quiet -- \
  commit -m "docs: pair work" -m "Co-Authored-By: Ada Lovelace <ada@example.org>"
check "human named Aiden passes" 0 --quiet -- \
  commit -m "docs: pair work" -m "Co-Authored-By: Aiden Smith <aiden@example.org>"
check "Claude trailer refused" 1 --refused -- \
  commit -m "feat: x" -m "Co-Authored-By: Claude <${claude_addr}>"
check "Codex trailer refused" 1 --refused -- \
  commit -m "feat: x" -m "Co-authored-by: Codex <${codex_addr}>"
check "Copilot trailer refused" 1 --refused -- \
  commit -m "feat: x" -m "Co-Authored-By: Copilot <copilot@example.org>"
check "an AI trailer refused" 1 --refused -- \
  commit -m "feat: x" -m "Co-Authored-By: Some AI <bot@example.org>"
check "Gemini trailer refused" 1 --refused -- \
  commit -m "feat: x" -m "Co-Authored-By: Gemini <bot@example.org>"
check "GPT trailer refused" 1 --refused -- \
  commit -m "feat: x" -m "Co-Authored-By: ChatGPT <bot@example.org>"
check "Generated with line refused" 1 --refused -- \
  commit -m "feat: x" -m "Generated with some tool"
check "robot face refused" 1 --refused -- \
  commit -m "feat: x" -m "$robot made this"
check "[codex] subject prefix refused" 1 --refused -- \
  commit -m "[codex] feat: x"
check "non-conventional subject warns" 0 --warns -- commit -m "update stuff"
check "em dash in message warns" 0 --warns -- commit -m "fix: one ${em} two"

printf 'new %s dash\n' "$em" > dash.txt
git add dash.txt
check "em dash added to a new file warns" 0 --warns -- commit -m "docs: add dash file"
printf 'more %s dash\n' "$em" >> dash.txt
git add dash.txt
check "em dash added to a file that had one is quiet" 0 --quiet -- commit -m "docs: extend dash file"

# Loop guard: a global hooks path equal to this directory is never chained to.
git config --global core.hooksPath "$hooks"
check "global hooks path equal to the repo hooks does not loop" 0 --quiet -- commit -m "chore: loop guard"
git config --global core.hooksPath "$work/global-hooks"

# pre-push
mkdir -p "$work/github.com/DSA-Woodshed" "$work/github.com/someone"
git init -q --bare "$work/github.com/DSA-Woodshed/repo.git"
git init -q --bare "$work/github.com/someone/repo.git"
git remote add upstream "file://$work/github.com/DSA-Woodshed/repo.git"
git remote add origin "file://$work/github.com/someone/repo.git"

git switch -q -c feat/ok "$base"
commit -m "feat: signed work"
check "push of signed work to the organization remote refused" 1 --refused -- git push -q upstream feat/ok
out_has "refusal names the Fork first section" 'Fork first'
check "push of signed work to the fork passes quietly" 0 --quiet -- git push -q origin feat/ok
if [ -s "$work/marks/pre-push" ] && grep -q 'refs/heads/feat/ok' "$work/marks/pre-push"; then
  passed=$((passed + 1)); echo "ok   pre-push chains to the global hooks path with stdin"
else
  failed=$((failed + 1)); echo "FAIL pre-push chain did not receive stdin"
fi

sha="$(git rev-parse HEAD)"
null="$(printf '%0*d' "${#sha}" 0)"
for url in git@github.com:DSA-Woodshed/meta.git https://github.com/DSA-Woodshed/meta.git \
  ssh://git@github.com/dsa-woodshed/meta.git ssh://git@github.com:443/DSA-Woodshed/meta.git; do
  check "synthetic push to $url refused" 1 --refused -- \
    bash -c "printf 'refs/heads/feat/ok %s refs/heads/feat/ok %s\n' '$sha' '$null' | '$hooks/pre-push' upstream '$url'"
done
check "synthetic push to a fork URL passes" 0 --quiet -- \
  bash -c "printf 'refs/heads/feat/ok %s refs/heads/feat/ok %s\n' '$sha' '$null' | '$hooks/pre-push' origin git@github.com:someone/meta.git"

# Real pushes exercise transferred personal locations and the genuine forks.
# Local bare repositories model the URL paths without contacting GitHub.
mkdir -p "$work/github.com/Jesssullivan"
for product in dsa-study-packet dsa-woodshed.space; do
  transferred="$work/github.com/Jesssullivan/$product.git"
  contribution="$work/github.com/Jesssullivan/$product-contrib.git"
  git init -q --bare "$transferred"
  git init -q --bare "$contribution"
  git remote add "transferred-$product" "file://$transferred"
  git remote add "contribution-$product" "file://$contribution"
  check "real push to transferred $product alias refused" 1 --refused -- \
    git push -q "transferred-$product" feat/ok
  check "refused transferred $product remains untouched" 0 --quiet -- \
    test -z "$(git --git-dir="$transferred" for-each-ref --format='%(refname)')"
  check "real push to personal $product-contrib fork passes" 0 --quiet -- \
    git push -q "contribution-$product" feat/ok

  for url in "git@github.com:Jesssullivan/$product.git" \
    "https://github.com/Jesssullivan/$product" \
    "https://github.com/jesssullivan/$product.git/" \
    "ssh://git@github.com/Jesssullivan/$product.git" \
    "ssh://git@github.com:443/Jesssullivan/$product.git"; do
    check "synthetic push to transferred $url refused" 1 --refused -- \
      bash -c "printf 'refs/heads/feat/ok %s refs/heads/feat/ok %s\n' '$sha' '$null' | '$hooks/pre-push' origin '$url'"
  done
  for url in "git@github.com:Jesssullivan/$product-contrib.git" \
    "https://github.com/Jesssullivan/$product-contrib" \
    "ssh://git@github.com:443/Jesssullivan/$product-contrib.git"; do
    check "synthetic push to real $url fork passes" 0 --quiet -- \
      bash -c "printf 'refs/heads/feat/ok %s refs/heads/feat/ok %s\n' '$sha' '$null' | '$hooks/pre-push' origin '$url'"
  done
done

check "similarly named personal repo is not a transferred alias" 0 --quiet -- \
  bash -c "printf 'refs/heads/feat/ok %s refs/heads/feat/ok %s\n' '$sha' '$null' | '$hooks/pre-push' origin https://github.com/Jesssullivan/dsa-study-packet-notes.git"

git switch -q -c wip/x "$base"
commit -m "feat: signed work on a loose branch"
check "branch wip/x warns but pushes" 0 --warns -- git push -q origin wip/x

git switch -q -c feat/unsigned "$base"
commit --no-verify --no-gpg-sign -m "feat: unsigned work"
check "unsigned commit refused" 1 --refused -- git push -q origin feat/unsigned
out_has "unsigned refusal gives the rebase command" 'rebase --force-rebase --gpg-sign'

git switch -q -c feat/trailer "$base"
commit --no-verify -m "feat: trailer" -m "Co-Authored-By: Claude <${claude_addr}>"
check "AI trailer committed with --no-verify refused at push" 1 --refused -- git push -q origin feat/trailer

git switch -q -c feat/generated "$base"
commit --no-verify -m "feat: generated" -m "Generated with a tool"
check "generated-by line refused at push" 1 --refused -- git push -q origin feat/generated

# Commits already on a remote-tracking ref are not walked again.
git switch -q -c feat/legacy "$base"
commit --no-verify --no-gpg-sign -m "chore: legacy unsigned"
git push -q --no-verify origin feat/legacy
git switch -q -c feat/stacked
commit -m "feat: signed on top of legacy"
check "only commits not on a remote-tracking ref are walked" 0 --quiet -- git push -q origin feat/stacked

# Merge commits made by GitHub are exempt from the signature rule.
git switch -q -c feat/merged "$base"
commit -m "feat: left"
GIT_COMMITTER_NAME=GitHub GIT_COMMITTER_EMAIL="$github_merge_addr" \
  git merge -q --no-verify --no-ff --no-gpg-sign -m "Merge pull request #1 from someone/feat/ok" feat/ok
check "unsigned GitHub merge commit is exempt" 0 --quiet -- git push -q origin feat/merged

git switch -q -c feat/local-merge "$base"
commit -m "feat: right"
git merge -q --no-verify --no-ff --no-gpg-sign -m "Merge branch 'feat/ok'" feat/ok
check "unsigned local merge commit refused" 1 --refused -- git push -q origin feat/local-merge

check "branch deletion passes" 0 --quiet -- git push -q origin :wip/x

# Installer ownership fixtures use a stand-in API, never a real login or network.
# They assert configuration effects rather than diagnostic wording.
mkdir -p "$work/bin"
cat > "$work/bin/gh" <<'EOF'
#!/usr/bin/env bash
set -eu
[ "${WOODSHED_FIXTURE_API:-ok}" != unavailable ] || exit 1
case "$4" in
  user) printf '%s\n' "${WOODSHED_FIXTURE_LOGIN:-contributor}" ;;
  repos/DSA-Woodshed/.github) printf '101\tDSA-Woodshed/.github\n' ;;
  repos/contributor/woodshed-contrib)
    if [ "${WOODSHED_FIXTURE_API:-ok}" = changed ]; then
      git config --local core.hooksPath changed-during-readback
    elif [ "${WOODSHED_FIXTURE_API:-ok}" = changed-default ]; then
      printf '#!/usr/bin/env bash\nexit 0\n' > .git/hooks/pre-commit
      chmod +x .git/hooks/pre-commit
    fi
    printf 'contributor/woodshed-contrib\tcontributor\t%s\t%s\t%s\n' \
      "${WOODSHED_FIXTURE_FORK:-true}" "${WOODSHED_FIXTURE_PARENT:-101}" "${WOODSHED_FIXTURE_SOURCE:-101}"
    ;;
  *) exit 1 ;;
esac
EOF
chmod +x "$work/bin/gh"

installer_repo() {
  git init -q "$work/installer-$1"
  cd "$work/installer-$1"
  cp -R "$hooks" githooks
  git remote add origin https://github.com/contributor/woodshed-contrib.git
  git remote add upstream git@github.com:DSA-Woodshed/.github.git
}

install_hooks() {
  PATH="$work/bin:$PATH" bash -c 'source githooks/_lib.sh; woodshed_install_hooks githooks DSA-Woodshed/.github'
}

installer_defaults() (
  installer_repo defaults
  local upstream_before config_before
  upstream_before="$(git remote get-url --push upstream)"
  git config --local commit.gpgsign false
  install_hooks || return 1
  [ "$(git config --local --get core.hooksPath)" = githooks ] || return 1
  [ "$(git config --local --get remote.pushDefault)" = origin ] || return 1
  [ "$(git remote get-url --push upstream)" = "$upstream_before" ] || return 1
  [ "$(git config --local --get commit.gpgsign)" = false ] || return 1
  config_before="$(cat .git/config)"
  install_hooks || return 1
  [ "$(cat .git/config)" = "$config_before" ]
)

installer_preserves() (
  local mode="$1" config_before
  installer_repo "$mode"
  case "$mode" in
    custom) git config --local core.hooksPath maintainer-hooks ;;
    push-default) git config --local remote.pushDefault another-owned-remote ;;
    global-push-default)
      cp "$GIT_CONFIG_GLOBAL" "$work/installer-global-config"
      export GIT_CONFIG_GLOBAL="$work/installer-global-config"
      git config --global remote.pushDefault another-owned-remote
      ;;
    built-in) printf '#!/usr/bin/env bash\nexit 0\n' > .git/hooks/pre-commit; chmod +x .git/hooks/pre-commit ;;
    shared)
      git -c core.hooksPath=/dev/null commit -q --allow-empty -m 'chore: worktree fixture'
      git worktree add -q -b feat/other-owner "$work/installer-linked"
      cd "$work/installer-linked"
      cp -R "$hooks" githooks
      ;;
    worktree-custom)
      git config --local extensions.worktreeConfig true
      git config --worktree core.hooksPath another-owner-hooks
      ;;
    different-login) export WOODSHED_FIXTURE_LOGIN=another-person ;;
    wrong-parent) export WOODSHED_FIXTURE_PARENT=102 ;;
    wrong-source) export WOODSHED_FIXTURE_SOURCE=102 ;;
    non-fork) export WOODSHED_FIXTURE_FORK=false ;;
    unavailable) export WOODSHED_FIXTURE_API=unavailable ;;
    canonical-origin) git remote set-url origin https://github.com/DSA-Woodshed/.github.git ;;
    push-elsewhere) git remote set-url --push origin https://github.com/contributor/another-repo.git ;;
    wrong-upstream) git remote set-url upstream https://github.com/DSA-Woodshed/another-repo.git ;;
    credential-url) git remote set-url origin https://hidden@example.org/contributor/woodshed-contrib.git ;;
    changed) export WOODSHED_FIXTURE_API=changed ;;
    changed-default) export WOODSHED_FIXTURE_API=changed-default ;;
  esac
  local common
  common="$(git rev-parse --git-common-dir)"
  config_before="$(cat "$common/config")"
  install_hooks || return 1
  if [ "$mode" = push-default ] || [ "$mode" = global-push-default ]; then
    [ "$(git config --get remote.pushDefault)" = another-owned-remote ] || return 1
    [ "$(git config --local --get core.hooksPath)" = githooks ]
  elif [ "$mode" = changed ]; then
    [ "$(git config --local --get core.hooksPath)" = changed-during-readback ] || return 1
    ! git config --local --get remote.pushDefault >/dev/null
  else
    [ "$(cat "$common/config")" = "$config_before" ]
  fi
)

check "verified personal fork installs only missing defaults and is idempotent" 0 --quiet -- installer_defaults
for mode in custom built-in shared worktree-custom different-login wrong-parent wrong-source non-fork \
  unavailable canonical-origin push-elsewhere wrong-upstream credential-url changed changed-default push-default global-push-default; do
  check "installer preserves configuration: $mode" 0 --quiet -- installer_preserves "$mode"
done

printf '\nhooks-test: %s passed, %s failed\n' "$passed" "$failed"
[ "$failed" -eq 0 ]
