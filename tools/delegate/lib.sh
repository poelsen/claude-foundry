#!/usr/bin/env bash
# tools/delegate/lib.sh
#
# Shared helpers for the foundry-delegate scripts. Source from entry
# scripts (run.sh, launch.sh, activate.sh, proxy.sh, worktree.sh).
# Do not run this file directly.

# Don't `set -e` here — callers decide. Do enable nounset + pipefail
# for the functions so shadowed vars and broken pipelines fail loudly.
set -uo pipefail

DELEGATE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$DELEGATE_DIR/../.." && pwd)"
REPO_NAME="$(basename "$REPO_ROOT")"
FOUNDRY_STATE_DIR="$REPO_ROOT/.foundry"
DELEGATE_LOG="$FOUNDRY_STATE_DIR/delegate-log.jsonl"

PROXY_HOST="127.0.0.1"
PROXY_PORT="${FOUNDRY_DELEGATE_PROXY_PORT:-4000}"
PROXY_URL="http://${PROXY_HOST}:${PROXY_PORT}"
PROXY_BASE_PATH="${XDG_RUNTIME_DIR:-/tmp}"
PROXY_PID_FILE="${PROXY_BASE_PATH}/foundry-delegate-litellm.pid"
PROXY_LOG_FILE="${PROXY_BASE_PATH}/foundry-delegate-litellm.log"

DEFAULT_MODEL="${FOUNDRY_DELEGATE_DEFAULT_MODEL:-MiniMax-M2}"

die()  { printf '[delegate] ERROR: %s\n' "$*" >&2; exit 1; }
info() { printf '[delegate] %s\n'        "$*" >&2; }

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

worktree_path()   { local slot="${1:?slot required}"; printf '%s/%s-delegate-%s' "$(dirname "$REPO_ROOT")" "$REPO_NAME" "$slot"; }
worktree_branch() { local slot="${1:?slot required}"; printf 'delegate/%s' "$slot"; }

ensure_worktree() {
    local slot="${1:?slot required}"
    local wt_path branch
    wt_path="$(worktree_path "$slot")"
    branch="$(worktree_branch "$slot")"

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
    # LiteLLM exposes /health/liveliness; fall back to the root for older builds.
    curl -fsS -o /dev/null --max-time 2 "$PROXY_URL/health/liveliness" 2>/dev/null && return 0
    curl -fsS -o /dev/null --max-time 2 "$PROXY_URL/"                  2>/dev/null && return 0
    return 1
}

ensure_proxy() {
    if proxy_alive; then
        info "proxy up at $PROXY_URL"
        return 0
    fi

    # Kill stale PID if present
    if [[ -f "$PROXY_PID_FILE" ]]; then
        local old_pid; old_pid="$(cat "$PROXY_PID_FILE" 2>/dev/null || true)"
        if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
            info "stale proxy PID $old_pid — killing"
            kill "$old_pid" 2>/dev/null || true
            sleep 1
        fi
        rm -f "$PROXY_PID_FILE"
    fi

    command -v litellm >/dev/null 2>&1 || die "litellm not on PATH — run: pip install 'litellm[proxy]'"
    local config="$DELEGATE_DIR/litellm.yaml"
    [[ -f "$config" ]] || die "missing config: $config"

    info "starting litellm proxy on :$PROXY_PORT (log: $PROXY_LOG_FILE)"
    nohup litellm --config "$config" --port "$PROXY_PORT" >"$PROXY_LOG_FILE" 2>&1 &
    echo "$!" >"$PROXY_PID_FILE"

    local i
    for i in $(seq 1 30); do
        sleep 0.5
        if proxy_alive; then
            info "proxy ready (pid $(cat "$PROXY_PID_FILE"))"
            return 0
        fi
    done
    die "proxy failed to start within 15s — see $PROXY_LOG_FILE"
}

stop_proxy() {
    if [[ ! -f "$PROXY_PID_FILE" ]]; then
        info "no PID file; proxy not managed by us"
        return 0
    fi
    local pid; pid="$(cat "$PROXY_PID_FILE" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        info "stopping proxy (pid $pid)"
        kill "$pid" 2>/dev/null || true
    fi
    rm -f "$PROXY_PID_FILE"
}

# ── Env export ────────────────────────────────────────────────────────

# Print shell-exportable env for a delegate session. Exports BOTH the
# Anthropic family (for Claude Code) and the OpenAI family (for
# opencode/aider/etc.), pointing both at the same LiteLLM proxy.
export_env_for_shell() {
    local slot="${1:?slot required}"
    local model="${2:-$DEFAULT_MODEL}"
    cat <<EOF
export ANTHROPIC_BASE_URL="$PROXY_URL"
export ANTHROPIC_AUTH_TOKEN="delegate-proxy-no-auth"
export ANTHROPIC_MODEL="$model"
export OPENAI_BASE_URL="$PROXY_URL/v1"
export OPENAI_API_KEY="delegate-proxy-no-auth"
export FOUNDRY_DELEGATE_SLOT="$slot"
export FOUNDRY_DELEGATE_MODEL="$model"
EOF
}

# ── Logging ───────────────────────────────────────────────────────────

# Append a JSON row to the delegate log. Caller passes a JSON object body
# (no braces, no leading/trailing comma) — ts is added automatically.
# Example:  log_event '"event":"start","slot":"scrape","model":"MiniMax-M2"'
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
