#!/usr/bin/env bash
# tools/delegate/activate.sh
#
# Source this file from an interactive shell to enter a delegate
# environment. It sets the Anthropic *and* OpenAI env families (pointing
# both at the local LiteLLM proxy), cds into the worktree, and leaves
# you in your shell. Run `claude`, `opencode`, `aider`, or anything
# else that reads those env vars — all go to the delegate model.
#
# Usage:
#   source tools/delegate/activate.sh SLOT [MODEL]
#
# Example:
#   source tools/delegate/activate.sh scrape MiniMax-M2
#   claude
#
# NOTE: must be sourced, not executed. Running directly will exit
# without effect (the env exports wouldn't survive the subshell).

# Guard: detect if executed rather than sourced.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "activate.sh: must be sourced, not executed" >&2
    echo "usage: source tools/delegate/activate.sh SLOT [MODEL]" >&2
    exit 1
fi

_delegate_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_delegate_dir/lib.sh"

_slot="${1:-}"
_model="${2:-$DEFAULT_MODEL}"

if [[ -z "$_slot" ]]; then
    echo "usage: source tools/delegate/activate.sh SLOT [MODEL]" >&2
    return 1 2>/dev/null || true
fi

load_env || return 1
ensure_proxy    || return 1
ensure_worktree "$_slot" || return 1

_wt_path="$(worktree_path "$_slot")"
# shellcheck disable=SC2046
eval $(export_env_for_shell "$_slot" "$_model")

cd "$_wt_path" || return 1

log_event "\"event\":\"activate\",\"slot\":\"$_slot\",\"model\":\"$_model\""

cat <<BANNER >&2

  ┌─ foundry-delegate activated ─────────────────────────────
  │ slot:     $_slot
  │ model:    $_model
  │ proxy:    $PROXY_URL
  │ cwd:      $_wt_path
  │ env set:  ANTHROPIC_* + OPENAI_* → proxy
  │
  │ Run: claude    opencode    aider    (anything)
  │ When done: cd back to primary and unset env vars
  │ (or just close this shell).
  └──────────────────────────────────────────────────────────

BANNER

unset _delegate_dir _slot _model _wt_path
