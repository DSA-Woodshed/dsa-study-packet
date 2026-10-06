#!/usr/bin/env bash
# Devcontainer toolchain bootstrap for the practice loop.
#
# Deliberately independent of flake.nix: the Nix devshell stays the
# maintainer's local flow; containers get only the three command-line tools the
# editor practice loop needs (Python via uv, just, and optional watchexec).
# No account, agent, host identity or protected service is bootstrapped here.
#
# Modes:
#   --tools  pinned tool installs only (onCreateCommand)
#   --sync   dependency sync only (updateContentCommand)
#   --seed   seed per-user practice state (postCreateCommand)
#   --ready  inspect public runtime readiness (postStartCommand)
#   (none)   run all three phases, for an explicit manual bootstrap
set -euo pipefail

UV_VERSION="0.11.27"
JUST_VERSION="1.40.0"
WATCHEXEC_VERSION="2.3.2"
PYTHON_VERSION="3.14.6"

# Release digests are copied from each upstream project's signed/tagged GitHub
# release assets. The container supports the two architectures offered by
# Codespaces; unknown architectures fail before any downloaded bytes execute.
UV_SHA256_X86_64="5d5594af1530c7c31e46a8cc0a35ceb4d28f3890049efe2149ac53c9ad121493"
UV_SHA256_AARCH64="b0b1909a7e5caf2ec0cbe2649f5171050c26d85efb65d9d4de2cfe754dc14ea3"
JUST_SHA256_X86_64="181b91d0ceebe8a57723fb648ed2ce1a44d849438ce2e658339df4f8db5f1263"
JUST_SHA256_AARCH64="d065d0df1a1f99529869fba8a5b3e0a25c1795b9007099b00dfabe29c7c1f7b6"
WATCHEXEC_SHA256_X86_64="2e72e56f722212558ce53d71c13d069f469c8113396da09d8ebf122ce6a655a5"
WATCHEXEC_SHA256_AARCH64="4e39391a2b75048cccfb7ab85e53241a8a8c9f88259dac0ee612b13d04e0e7e2"

BIN_DIR="$HOME/.local/bin"
export PATH="$BIN_DIR:$PATH"
# The base image ships python3.11-minimal (no `json` module); uv must never
# probe it. Always use uv-managed CPython. Mirrored in containerEnv.
export UV_PYTHON_PREFERENCE=only-managed
export UV_PYTHON="$PYTHON_VERSION"
mkdir -p "$BIN_DIR"

log()  { echo "[setup] $*"; }
warn() { echo "[setup] WARN: $*" >&2; }

curl_https() {
	curl --proto '=https' --proto-redir '=https' --tlsv1.2 \
		--connect-timeout 10 --max-time 180 --retry 2 -LsSf "$@"
}

select_release_arch() {
	if [ "$(uname -s)" != "Linux" ]; then
		warn "the devcontainer tool installer supports Linux only"
		return 1
	fi
	case "$(uname -m)" in
		x86_64 | amd64)
			RELEASE_ARCH="x86_64"
			UV_SHA256="$UV_SHA256_X86_64"
			JUST_SHA256="$JUST_SHA256_X86_64"
			WATCHEXEC_SHA256="$WATCHEXEC_SHA256_X86_64"
			;;
		aarch64 | arm64)
			RELEASE_ARCH="aarch64"
			UV_SHA256="$UV_SHA256_AARCH64"
			JUST_SHA256="$JUST_SHA256_AARCH64"
			WATCHEXEC_SHA256="$WATCHEXEC_SHA256_AARCH64"
			;;
		*)
			warn "unsupported Codespaces architecture: $(uname -m)"
			return 1
			;;
	esac
}

download_verified() {
	local url="$1"
	local expected="$2"
	local destination="$3"
	curl_https "$url" -o "$destination" \
		&& printf '%s  %s\n' "$expected" "$destination" \
		| sha256sum --check --status -
}

install_uv() {
	local target="${RELEASE_ARCH}-unknown-linux-musl"
	local archive="uv-$target.tar.gz"
	local tmp_dir status
	tmp_dir="$(mktemp -d)"
	status=0
	if ! download_verified \
		"https://github.com/astral-sh/uv/releases/download/$UV_VERSION/$archive" \
		"$UV_SHA256" "$tmp_dir/$archive" \
		|| ! tar -xzf "$tmp_dir/$archive" -C "$tmp_dir" \
		|| ! install -m 0755 "$tmp_dir/uv-$target/uv" "$BIN_DIR/uv"; then
		status=1
	fi
	rm -rf "$tmp_dir"
	return "$status"
}

install_just() {
	local archive="just-$JUST_VERSION-$RELEASE_ARCH-unknown-linux-musl.tar.gz"
	local tmp_dir status
	tmp_dir="$(mktemp -d)"
	status=0
	if ! download_verified \
		"https://github.com/casey/just/releases/download/$JUST_VERSION/$archive" \
		"$JUST_SHA256" "$tmp_dir/$archive" \
		|| ! tar -xzf "$tmp_dir/$archive" -C "$tmp_dir" \
		|| ! install -m 0755 "$tmp_dir/just" "$BIN_DIR/just"; then
		status=1
	fi
	rm -rf "$tmp_dir"
	return "$status"
}

install_watchexec() {
	local directory="watchexec-$WATCHEXEC_VERSION-$RELEASE_ARCH-unknown-linux-musl"
	local archive="$directory.tar.xz"
	local tmp_dir status
	tmp_dir="$(mktemp -d)"
	status=0
	if ! download_verified \
		"https://github.com/watchexec/watchexec/releases/download/v$WATCHEXEC_VERSION/$archive" \
		"$WATCHEXEC_SHA256" "$tmp_dir/$archive" \
		|| ! tar -xJf "$tmp_dir/$archive" -C "$tmp_dir" \
		|| ! install -m 0755 "$tmp_dir/$directory/watchexec" "$BIN_DIR/watchexec"; then
		status=1
	fi
	rm -rf "$tmp_dir"
	return "$status"
}

tool_version() {
	"$1" --version 2>/dev/null | awk 'NR == 1 { version = $2; sub(/^v/, "", version); print version }'
}

has_version() {
	local tool="$1"
	local expected="$2"
	command -v "$tool" >/dev/null 2>&1 \
		&& [ "$(tool_version "$tool")" = "$expected" ]
}

require_version() {
	local tool="$1"
	local expected="$2"
	if ! has_version "$tool" "$expected"; then
		warn "$tool install did not provide declared version $expected"
		return 1
	fi
}

sync_deps() {
	log "syncing locked public Python dependencies with CPython $PYTHON_VERSION"
	uv sync --locked --python "$PYTHON_VERSION" --extra dev
}

seed_state() {
	# /workspaces and its checkout survive Codespaces rebuilds. Keep the state
	# directory regular: the practice engine deliberately rejects symlinks.
	.venv/bin/python scripts/environment.py setup
}

install_tools() {
	# Generate this Codespace's machine keys at runtime, never in a cached image.
	# The public base provides sudo; these are unrelated to any host identity.
	if [ "${CODESPACES:-false}" = "true" ] && command -v sshd >/dev/null 2>&1; then
		if [ "$(id -u)" = "0" ]; then
			ssh-keygen -A
		else
			sudo -n ssh-keygen -A
		fi
	fi

	if ! has_version uv "$UV_VERSION" \
		|| ! has_version just "$JUST_VERSION" \
		|| ! has_version watchexec "$WATCHEXEC_VERSION"; then
		select_release_arch
	fi

	if ! has_version uv "$UV_VERSION"; then
		log "installing uv $UV_VERSION"
		if ! install_uv; then
			warn "uv download, verification, or extraction failed"
		fi
		hash -r
	fi
	require_version uv "$UV_VERSION"

	if ! has_version just "$JUST_VERSION"; then
		log "installing just $JUST_VERSION"
		if ! install_just; then
			warn "just download, verification, or extraction failed"
		fi
		hash -r
	fi
	require_version just "$JUST_VERSION"

	if ! has_version watchexec "$WATCHEXEC_VERSION"; then
		# Watch mode is optional. Never fail container creation on this helper.
		log "installing watchexec $WATCHEXEC_VERSION"
		if ! install_watchexec; then
			warn "watchexec install failed; watch mode unavailable; the loop still works"
		fi
		hash -r
	fi
	if ! has_version watchexec "$WATCHEXEC_VERSION"; then
		warn "watchexec $WATCHEXEC_VERSION unavailable; use just practice-test"
	fi

}

case "${1:-}" in
	--tools) install_tools ;;
	--sync) sync_deps ;;
	--seed) seed_state ;;
	--ready) .venv/bin/python scripts/environment.py check ;;
	"")
		install_tools
		sync_deps
		seed_state
		;;
	*)
		echo "usage: $0 [--tools|--sync|--seed|--ready]" >&2
		exit 2
		;;
esac

log "${1:---all} complete"
