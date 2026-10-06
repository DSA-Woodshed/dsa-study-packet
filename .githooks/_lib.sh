# shellcheck shell=bash
# shellcheck disable=SC2034 # variables are used by the hooks that source this file
# Shared helpers for the DSA Woodshed git hooks.
#
# Canonical copy: DSA-Woodshed/.github, githooks/. Product repositories carry
# byte-identical .githooks/ copies; `just hooks-check` checks the pinned mirror.
#
# Plain bash and git, compatible with bash 3.2; setup optionally reads identity
# with an existing GitHub CLI. Every refusal or warning
# prints three lines: what happened, the CONTRIBUTING.md section that explains
# the rule, and the exact command that fixes it. The text is written for a
# person or an agent reading stderr.

WOODSHED_CONTRIBUTING="https://github.com/DSA-Woodshed/.github/blob/main/CONTRIBUTING.md"

# Characters built from bytes so these sources contain none of them.
WOODSHED_EM_DASH="$(printf '\342\200\224')"
WOODSHED_ROBOT="$(printf '\360\237\244\226')"

WOODSHED_REFUSED=0

woodshed_refuse() {
  # $1 what was refused, $2 CONTRIBUTING.md section, $3 fix command
  printf 'woodshed-hooks: REFUSED: %s\n' "$1" >&2
  printf 'woodshed-hooks:   rule: CONTRIBUTING.md, section "%s" (%s)\n' "$2" "$WOODSHED_CONTRIBUTING" >&2
  printf 'woodshed-hooks:   fix:  %s\n' "$3" >&2
  WOODSHED_REFUSED=1
}

woodshed_warn() {
  # $1 what looks wrong, $2 CONTRIBUTING.md section, $3 fix command
  printf 'woodshed-hooks: warning: %s\n' "$1" >&2
  printf 'woodshed-hooks:   rule: CONTRIBUTING.md, section "%s" (%s)\n' "$2" "$WOODSHED_CONTRIBUTING" >&2
  printf 'woodshed-hooks:   fix:  %s\n' "$3" >&2
}

# Accept ordinary GitHub clone URLs only. Never echo a remote URL: an unusual
# URL can contain credentials. API readback below resolves repository identity.
woodshed_github_repo() {
  local repo
  case "$1" in
    https://github.com/*) repo="${1#https://github.com/}" ;;
    git@github.com:*) repo="${1#git@github.com:}" ;;
    ssh://git@github.com/*) repo="${1#ssh://git@github.com/}" ;;
    ssh://git@github.com:443/*) repo="${1#ssh://git@github.com:443/}" ;;
    *) return 1 ;;
  esac
  repo="${repo%/}"
  repo="${repo%.git}"
  case "$repo" in *[!A-Za-z0-9_./-]*|/*|*/|*/*/*) return 1 ;; esac
  case "$repo" in */*) ;; *) return 1 ;; esac
  case "${repo%%/*}" in ''|.|..) return 1 ;; esac
  case "${repo#*/}" in ''|.|..) return 1 ;; esac
  printf '%s\n' "$repo"
}

woodshed_same_repo() {
  [ "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" = \
    "$(printf '%s' "$2" | tr '[:upper:]' '[:lower:]')" ]
}

woodshed_setup_notice() {
  printf 'woodshed-setup: %s; contributor configuration preserved. See CONTRIBUTING.md.\n' "$1" >&2
}

woodshed_has_default_hooks() {
  local hook
  for hook in "$1/hooks/"*; do
    case "$hook" in *.sample) continue ;; esac
    [ -f "$hook" ] && [ -x "$hook" ] && return 0
  done
  return 1
}

# Apply defaults only in an independently owned, verified personal fork.
# Unknown identity and existing custom/shared configuration are advisory skips:
# ordinary practice setup does not require GitHub authentication or new tools.
# $1 vendored hook directory, $2 authoritative organization repository.
woodshed_install_hooks() {
  local hooks="$1" canonical="$2" root common config hooks_path old_hooks
  local origin upstream push_origin login canonical_data canonical_id canonical_name
  local fork_data fork_name fork_owner is_fork parent_id source_id
  case "$hooks" in githooks|.githooks) ;; *) woodshed_setup_notice 'Unknown hook directory'; return 0 ;; esac
  root="$(git rev-parse --show-toplevel 2>/dev/null)" || { woodshed_setup_notice 'Not a checkout'; return 0; }
  common="$(git rev-parse --git-common-dir 2>/dev/null)" || return 0
  common="$(cd "$common" 2>/dev/null && pwd -P)" || return 0
  config="$common/config"
  if [ ! -O "$root" ] || [ ! -O "$config" ]; then
    woodshed_setup_notice 'Checkout ownership differs from the current user'; return 0
  fi
  if [ "$(git worktree list --porcelain | grep -c '^worktree ')" != 1 ]; then
    woodshed_setup_notice 'Linked worktrees share this configuration'; return 0
  fi
  if [ ! -x "$root/$hooks/pre-commit" ] || [ ! -x "$root/$hooks/commit-msg" ] || [ ! -x "$root/$hooks/pre-push" ]; then
    woodshed_setup_notice 'Vendored hooks are unavailable'; return 0
  fi
  old_hooks="$(git config --local --includes --get-all core.hooksPath 2>/dev/null || true)"
  hooks_path="$(git config --worktree --includes --get-all core.hooksPath 2>/dev/null || true)"
  if { [ -n "$old_hooks" ] && [ "$old_hooks" != "$hooks" ]; } || \
    { [ -n "$hooks_path" ] && [ "$hooks_path" != "$hooks" ]; }; then
    woodshed_setup_notice 'A custom checkout hook path is configured'; return 0
  fi
  if woodshed_has_default_hooks "$common"; then
    woodshed_setup_notice 'Custom hooks exist in the default hooks directory'; return 0
  fi
  origin="$(woodshed_github_repo "$(git remote get-url --all origin 2>/dev/null)")" || { woodshed_setup_notice 'Origin identity is unavailable'; return 0; }
  push_origin="$(woodshed_github_repo "$(git remote get-url --push --all origin 2>/dev/null)")" || { woodshed_setup_notice 'Origin push identity is unavailable'; return 0; }
  upstream="$(woodshed_github_repo "$(git remote get-url --all upstream 2>/dev/null)")" || { woodshed_setup_notice 'Upstream identity is unavailable'; return 0; }
  if ! woodshed_same_repo "$upstream" "$canonical" || ! woodshed_same_repo "$origin" "$push_origin"; then
    woodshed_setup_notice 'Remote identities differ from the contribution topology'; return 0
  fi
  if ! command -v gh >/dev/null 2>&1; then
    woodshed_setup_notice 'Optional GitHub identity readback is unavailable'; return 0
  fi
  login="$(GH_DEBUG= gh api --hostname github.com user --jq .login 2>/dev/null)" || { woodshed_setup_notice 'Optional GitHub identity readback is unavailable'; return 0; }
  canonical_data="$(GH_DEBUG= gh api --hostname github.com "repos/$canonical" --jq '[.id, .full_name] | @tsv' 2>/dev/null)" || { woodshed_setup_notice 'Canonical repository readback is unavailable'; return 0; }
  fork_data="$(GH_DEBUG= gh api --hostname github.com "repos/$origin" --jq '[.full_name, .owner.login, .fork, .parent.id, .source.id] | @tsv' 2>/dev/null)" || { woodshed_setup_notice 'Fork repository readback is unavailable'; return 0; }
  IFS=$'\t' read -r canonical_id canonical_name <<< "$canonical_data"
  IFS=$'\t' read -r fork_name fork_owner is_fork parent_id source_id <<< "$fork_data"
  if [ -z "$login" ] || [ -z "$canonical_id" ] || [ "$is_fork" != true ] || \
    [ "$parent_id" != "$canonical_id" ] || [ "$source_id" != "$canonical_id" ] || \
    ! woodshed_same_repo "$canonical_name" "$canonical" || \
    ! woodshed_same_repo "$fork_name" "$origin" || ! woodshed_same_repo "$fork_owner" "$login"; then
    woodshed_setup_notice 'Origin is not a personal fork owned by the current GitHub user'; return 0
  fi
  # Recheck shared configuration immediately before writing. Do not rewrite any
  # remote URL, signing setting, or an existing push default (including global).
  if [ "$(git worktree list --porcelain | grep -c '^worktree ')" != 1 ]; then
    woodshed_setup_notice 'Linked worktrees now share this configuration'; return 0
  fi
  if [ ! -O "$root" ] || [ ! -O "$config" ] || woodshed_has_default_hooks "$common" || \
    [ "$(git config --local --includes --get-all core.hooksPath 2>/dev/null || true)" != "$old_hooks" ] || \
    [ "$(git config --worktree --includes --get-all core.hooksPath 2>/dev/null || true)" != "$hooks_path" ] || \
    ! woodshed_same_repo "$(woodshed_github_repo "$(git remote get-url --all origin 2>/dev/null)")" "$origin" || \
    ! woodshed_same_repo "$(woodshed_github_repo "$(git remote get-url --push --all origin 2>/dev/null)")" "$push_origin" || \
    ! woodshed_same_repo "$(woodshed_github_repo "$(git remote get-url --all upstream 2>/dev/null)")" "$upstream"; then
    woodshed_setup_notice 'Checkout configuration changed during identity readback'; return 0
  fi
  if [ -z "$old_hooks" ] && [ -z "$hooks_path" ]; then
    git config --local core.hooksPath "$hooks" || return
  fi
  if ! git config --get-all remote.pushDefault >/dev/null 2>&1; then
    git config --local remote.pushDefault origin || return
  fi
  printf 'woodshed-setup: Verified personal fork; shared hooks ready. Remote URLs and signing configuration preserved.\n'
}

# Print the message body without comment lines and without anything below a
# `git commit --verbose` scissors line.
woodshed_message_text() {
  sed -e '/^# -\{1,\} >8 -\{1,\}$/,$d' -e '/^#/d' "$1"
}

# Exit 0 when the message text on stdin carries AI attribution, printing the
# offending line. Human Co-Authored-By trailers pass.
woodshed_ai_attribution_line() {
  local text first
  text="$(cat)"
  first="$(printf '%s\n' "$text" | sed -n '/[^[:space:]]/{p;q;}')"
  if printf '%s\n' "$first" | grep -iqE '^[[:space:]]*\[codex\]'; then
    printf '%s\n' "$first"
    return 0
  fi
  printf '%s\n' "$text" | grep -m1 -iE '^[[:space:]]*co-authored-by:.*(claude|codex|copilot|gpt|gemini|anthropic\.com|openai\.com)' && return 0
  printf '%s\n' "$text" | grep -m1 -E '^[[:space:]]*[Cc][Oo]-[Aa][Uu][Tt][Hh][Oo][Rr][Ee][Dd]-[Bb][Yy]:(.*[^[:alnum:]])?AI([^[:alnum:]]|$)' && return 0
  printf '%s\n' "$text" | grep -m1 -iE 'generated with' && return 0
  printf '%s\n' "$text" | grep -m1 -F "$WOODSHED_ROBOT" && return 0
  return 1
}

# Run the hook of the same name from the global core.hooksPath, when one is
# set, executable, and a different directory, so a machine-wide hook layer
# keeps running. Never chains twice and never chains to itself.
# $1 hook name, $2 file holding the stdin to replay (or empty), rest: args.
woodshed_chain() {
  local hook="$1" input="$2" global here there
  shift 2
  [ -z "${WOODSHED_HOOKS_CHAINED:-}" ] || return 0
  global="$(git config --global --type=path --get core.hooksPath 2>/dev/null || true)"
  [ -n "$global" ] || return 0
  here="$(cd "$(dirname "$0")" && pwd -P)" || return 0
  there="$(cd "$global" 2>/dev/null && pwd -P)" || return 0
  [ "$here" != "$there" ] || return 0
  [ -f "$there/$hook" ] && [ -x "$there/$hook" ] || return 0
  export WOODSHED_HOOKS_CHAINED=1
  if [ -n "$input" ]; then
    "$there/$hook" "$@" < "$input"
  else
    "$there/$hook" "$@"
  fi
}
