#!/usr/bin/env bash
# tools/delegate/run.sh
#
# Orchestrated (non-interactive) delegate run. Primary Claude invokes this
# via Bash; the script sets up the worktree + proxy, executes `claude
# --print "$task"` in the secondary environment, auto-commits resulting
# changes on the delegate branch, and emits a JSON summary to stdout.
#
# Usage:
#   run.sh --job NAME --task "DESC" [--model M] [--timeout S]
#
# Required:
#   --job NAME           worktree job (persisted; reuse across calls)
#   --task "DESC"        self-contained task description
#
# Optional:
#   --model M            ccr model name (default: MiniMax-M2)
#   --timeout S          wall-clock timeout in seconds (default: 600)

set -euo pipefail
DELEGATE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$DELEGATE_DIR/lib.sh"

job=""
task=""
model=""
timeout_s="600"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --job)      job="${2:?}";       shift 2 ;;
        --task)     task="${2:?}";      shift 2 ;;
        --model)    model="${2:?}";     shift 2 ;;
        --timeout)  timeout_s="${2:?}"; shift 2 ;;
        -h|--help)  sed -n '1,18p' "$0"; exit 0 ;;
        *)          die "unknown arg: $1" ;;
    esac
done

[[ -n "$job"  ]] || die "--job is required"
[[ -n "$task" ]] || die "--task is required"
model="${model:-$DEFAULT_MODEL}"

load_env
ensure_proxy
ensure_worktree "$job"

wt_path="$(worktree_path "$job")"
eval "$(export_env_for_shell "$job" "$model")"

info "delegating to $model in $wt_path (timeout ${timeout_s}s)"
log_event "\"event\":\"start\",\"job\":\"$job\",\"model\":\"$model\",\"timeout_s\":$timeout_s"

start_ts="$(date -u +%s)"
stdout_file="$(mktemp)"
cleanup() { rm -f "$stdout_file"; }
trap cleanup EXIT

set +e
( cd "$wt_path" && timeout "${timeout_s}s" claude --print "$task" ) >"$stdout_file" 2>&1
exit_code=$?
set -e

end_ts="$(date -u +%s)"
duration=$(( end_ts - start_ts ))

case "$exit_code" in
    0)   exit_reason="complete" ;;
    124) exit_reason="timeout"  ;;
    *)   exit_reason="error"    ;;
esac

# Auto-commit any uncommitted secondary changes onto the delegate branch.
# Count from the porcelain BEFORE commit (not git diff HEAD~1 — that
# would leak prior commits from the branch point).
changed_count=0
( cd "$wt_path"
  status="$(git status --porcelain 2>/dev/null)"
  if [[ -n "$status" ]]; then
      changed_count="$(printf '%s\n' "$status" | wc -l | tr -d ' ')"
      git add -A
      git -c user.name="delegate[$job]" -c user.email="delegate@foundry.local" \
          commit -q -m "delegate[$job]: ${task:0:60}" \
          -m "Model: $model" -m "Exit: $exit_reason (${duration}s)" || true
  fi
  echo "$changed_count"
) >"${stdout_file}.changed"
changed_count="$(cat "${stdout_file}.changed" | tail -1)"
rm -f "${stdout_file}.changed"

log_event "\"event\":\"end\",\"job\":\"$job\",\"model\":\"$model\",\"exit_reason\":\"$exit_reason\",\"duration_s\":$duration,\"files_changed\":${changed_count:-0}"

# Emit structured summary JSON to stdout (for primary to parse).
python3 - "$job" "$model" "$exit_reason" "$exit_code" "$duration" "${changed_count:-0}" "$wt_path" "$stdout_file" <<'PY'
import json, sys, pathlib
job, model, exit_reason, exit_code, duration, changed, wt_path, out_path = sys.argv[1:]
summary = pathlib.Path(out_path).read_text(errors="replace")
print(json.dumps({
    "job":          job,
    "model":         model,
    "exit_reason":   exit_reason,
    "exit_code":     int(exit_code),
    "duration_s":    int(duration),
    "files_changed": int(changed),
    "worktree":      wt_path,
    "summary":       summary,
}, indent=2))
PY
