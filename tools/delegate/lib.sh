#!/usr/bin/env bash
# tools/delegate/lib.sh
#
# Shared helpers for the foundry-delegate scripts. Source from entry
# scripts (run.sh, launch.sh, activate.sh, proxy.sh, worktree.sh).
# Do not run this file directly.

# Don't `set -e` here — callers decide. Do enable nounset + pipefail
# for the functions so shadowed vars and broken pipelines fail loudly.
set -uo pipefail

# Define error helpers first so REPO_ROOT check below can use die().
die()  { printf '[delegate] ERROR: %s\n' "$*" >&2; exit 1; }
info() { printf '[delegate] %s\n'        "$*" >&2; }

DELEGATE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# REPO_ROOT is the git repo of the INVOKING cwd (target project), not of
# the script's location. This lets one deployed copy of these scripts —
# e.g. $TARGET/.claude/foundry/tools/delegate/ — operate on any project
# the user cd-s into before invocation. Using the script's parent would
# incorrectly resolve to the foundry cache root.
REPO_ROOT="$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null)" \
    || die "not inside a git repository (cwd=$PWD) — cd into the target project first"
REPO_NAME="$(basename "$REPO_ROOT")"
FOUNDRY_STATE_DIR="$REPO_ROOT/.foundry"
DELEGATE_LOG="$FOUNDRY_STATE_DIR/delegate-log.jsonl"

# Proxy: claude-code-router (ccr). Translates Anthropic /v1/messages →
# OpenAI /v1/chat/completions and forwards to the configured backend
# (MiniMax, etc.). ccr owns its own daemon + PID file at
# ~/.claude-code-router/.claude-code-router.pid and listens on :3456 by
# default — we just check health + start/stop it via the `ccr` CLI.
PROXY_HOST="127.0.0.1"
PROXY_PORT="${FOUNDRY_DELEGATE_PROXY_PORT:-3456}"
PROXY_URL="http://${PROXY_HOST}:${PROXY_PORT}"
CCR_CONFIG_DIR="${CCR_CONFIG_DIR:-$HOME/.claude-code-router}"
CCR_CONFIG_FILE="$CCR_CONFIG_DIR/config.json"

DEFAULT_MODEL="${FOUNDRY_DELEGATE_DEFAULT_MODEL:-MiniMax-M2}"

# Load repo-root .env (and tools/delegate/.env if present) into the environment.
# Safe to call multiple times — `set -a` exports everything sourced.
load_env() {
    local f
    set -a
    for f in "$REPO_ROOT/.env" "$DELEGATE_DIR/.env"; do
        # shellcheck disable=SC1090
        [[ -f "$f" ]] && source "$f"
    done
    set +a
}

require_env() {
    local var="$1"
    [[ -n "${!var:-}" ]] || die "missing env var: $var (check $REPO_ROOT/.env or $DELEGATE_DIR/.env)"
}

# ── Worktree ──────────────────────────────────────────────────────────

worktree_path()   { local job="${1:?job required}"; printf '%s/%s-delegate-%s' "$(dirname "$REPO_ROOT")" "$REPO_NAME" "$job"; }
worktree_branch() { local job="${1:?job required}"; printf 'delegate/%s' "$job"; }

ensure_worktree() {
    local job="${1:?job required}"
    local wt_path branch
    wt_path="$(worktree_path "$job")"
    branch="$(worktree_branch "$job")"

    if [[ -d "$wt_path/.git" || -f "$wt_path/.git" ]]; then
        info "worktree exists: $wt_path"
        return 0
    fi

    info "creating worktree: $wt_path (branch $branch)"
    ( cd "$REPO_ROOT"
      if git show-ref --verify --quiet "refs/heads/$branch"; then
          git worktree add "$wt_path" "$branch" >&2
      else
          git worktree add -b "$branch" "$wt_path" >&2
      fi
    )
}

# ── Proxy ─────────────────────────────────────────────────────────────

proxy_alive() {
    # Use bash's /dev/tcp to test whether anything is listening on the
    # port. Reliable and doesn't depend on ccr's HTTP behavior. Redirects
    # are because /dev/tcp writes "cannot connect" to stderr on failure.
    (exec 3<>"/dev/tcp/$PROXY_HOST/$PROXY_PORT") 2>/dev/null || return 1
    exec 3<&- 2>/dev/null || true
    return 0
}

# Locate the ccr binary. Prefer user-level npm install
# (~/.npm-global/bin/ccr) or whatever is on PATH.
_ccr_bin() {
    if   [[ -x "$HOME/.npm-global/bin/ccr" ]]; then echo "$HOME/.npm-global/bin/ccr"
    elif command -v ccr >/dev/null 2>&1;         then echo "ccr"
    else return 1
    fi
}

ensure_proxy() {
    if proxy_alive; then
        info "proxy up at $PROXY_URL"
        return 0
    fi

    local ccr_bin; ccr_bin="$(_ccr_bin)" \
        || die "ccr not found — run: npm install -g @musistudio/claude-code-router (with npm prefix set to ~/.npm-global)"
    [[ -f "$CCR_CONFIG_FILE" ]] \
        || die "ccr config missing: $CCR_CONFIG_FILE (see tools/delegate/README.md)"

    # Load .env so env-var interpolation in ccr's config (e.g.
    # $MINIMAX_API_KEY) resolves to actual credentials.
    load_env

    info "starting ccr (config: $CCR_CONFIG_FILE)"
    # ccr's `start` command runs its HTTP server in the foreground. Background
    # it and detach so this script can return once the port is reachable.
    nohup "$ccr_bin" start </dev/null >/dev/null 2>&1 &
    disown 2>/dev/null || true

    local i
    for i in $(seq 1 30); do
        sleep 0.5
        if proxy_alive; then
            info "proxy ready at $PROXY_URL"
            return 0
        fi
    done
    die "ccr failed to become reachable at $PROXY_URL within 15s — see $CCR_CONFIG_DIR/logs/"
}

stop_proxy() {
    local ccr_bin; ccr_bin="$(_ccr_bin)" || { info "ccr not on PATH; nothing to stop"; return 0; }
    "$ccr_bin" stop >/dev/null 2>&1 || true
    info "ccr stopped"
}

# ── Env export ────────────────────────────────────────────────────────

# Print shell-exportable env for a delegate session. Exports BOTH the
# Anthropic family (for Claude Code) and the OpenAI family (for
# opencode/aider/etc.), pointing both at the same ccr proxy.
export_env_for_shell() {
    local job="${1:?job required}"
    local model="${2:-$DEFAULT_MODEL}"
    cat <<EOF
export ANTHROPIC_BASE_URL="$PROXY_URL"
export ANTHROPIC_AUTH_TOKEN="delegate-proxy-no-auth"
export ANTHROPIC_MODEL="$model"
export OPENAI_BASE_URL="$PROXY_URL/v1"
export OPENAI_API_KEY="delegate-proxy-no-auth"
export FOUNDRY_DELEGATE_JOB="$job"
export FOUNDRY_DELEGATE_MODEL="$model"
EOF
}

# ── Logging ───────────────────────────────────────────────────────────

# Append a JSON row to the delegate log. Caller passes a JSON object body
# (no braces, no leading/trailing comma) — ts is added automatically.
# Example:  log_event '"event":"start","job":"scrape","model":"MiniMax-M2"'
log_event() {
    local body="${1:-}"
    local ts; ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    mkdir -p "$FOUNDRY_STATE_DIR"
    if [[ -n "$body" ]]; then
        printf '{"ts":"%s",%s}\n' "$ts" "$body" >>"$DELEGATE_LOG"
    else
        printf '{"ts":"%s"}\n' "$ts" >>"$DELEGATE_LOG"
    fi
}

# JSON-encode a string (for embedding in log rows / output). Uses python3
# to avoid reimplementing escape rules in shell.
json_str() {
    python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()), end="")'
}
