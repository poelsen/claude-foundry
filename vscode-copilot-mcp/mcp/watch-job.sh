#!/usr/bin/env bash
# Usage: watch-job.sh <jobId>
# Polls a copilot-mcp job every 15s, prints result when done.
# Reads port+token from .vscode/copilot-mcp.json (searching upward from cwd)
# so the token is never exposed via ps/cmdline.

JOBID=$1

if [ -z "$JOBID" ]; then
  echo "Usage: watch-job.sh <jobId>" >&2
  exit 1
fi

find_connection_file() {
  # Walk up looking for .vscode/copilot-mcp.json. First match wins.
  # Note: we do NOT stop at .git because the VS Code workspace may be a
  # parent directory that itself is not a git repo but contains git
  # subdirectories.
  local dir="$PWD"
  while [ "$dir" != "/" ]; do
    if [ -f "$dir/.vscode/copilot-mcp.json" ]; then
      echo "$dir/.vscode/copilot-mcp.json"
      return 0
    fi
    dir=$(dirname "$dir")
  done
  return 1
}

read_connection() {
  local file
  file=$(find_connection_file) || return 1
  # Pass file path via env var to avoid shell-to-Python string injection
  # (paths with apostrophes would break the inline code).
  COPILOT_MCP_CONN_FILE="$file" python3 -c "
import json, os, sys
try:
  with open(os.environ['COPILOT_MCP_CONN_FILE']) as f:
    d = json.load(f)
  print(d['port'], d['token'])
except Exception:
  print('error', file=sys.stderr)
  sys.exit(1)
"
}

FAILED_CHECKS=0
while true; do
  CONN=$(read_connection) || {
    echo "Error: cannot find or parse .vscode/copilot-mcp.json" >&2
    exit 1
  }
  PORT=$(echo "$CONN" | awk '{print $1}')
  TOKEN=$(echo "$CONN" | awk '{print $2}')

  # Write HTTP status code to one file, body to another, so we can distinguish
  # network failures (curl non-zero exit) from HTTP errors (4xx/5xx body).
  BODY_FILE=$(mktemp)
  HTTP_CODE=$(curl -s --max-time 10 -o "$BODY_FILE" -w '%{http_code}' \
    -H "Authorization: Bearer $TOKEN" \
    "http://127.0.0.1:$PORT/jobs/$JOBID")
  CURL_EXIT=$?

  if [ $CURL_EXIT -ne 0 ]; then
    rm -f "$BODY_FILE"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    if [ $FAILED_CHECKS -ge 3 ]; then
      echo "Error: server unreachable (curl exit $CURL_EXIT) after 3 attempts." >&2
      exit 1
    fi
    sleep 15
    continue
  fi

  # 401 = stale token, 404 = job not found (likely deleted) — fatal either way
  if [ "$HTTP_CODE" = "401" ]; then
    rm -f "$BODY_FILE"
    echo "Error: unauthorized (401). Token may be stale from extension restart." >&2
    exit 1
  fi
  if [ "$HTTP_CODE" = "404" ]; then
    rm -f "$BODY_FILE"
    echo "Error: job $JOBID not found (404). It may have been deleted." >&2
    exit 1
  fi
  if [ "$HTTP_CODE" != "200" ]; then
    rm -f "$BODY_FILE"
    echo "Error: unexpected HTTP status $HTTP_CODE from server." >&2
    exit 1
  fi
  FAILED_CHECKS=0

  RESP=$(cat "$BODY_FILE")
  rm -f "$BODY_FILE"

  STATUS=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['status'])" 2>/dev/null)

  if [ "$STATUS" = "done" ] || [ "$STATUS" = "failed" ] || [ "$STATUS" = "cancelled" ]; then
    echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
status = d['status']
if status=='done':
  r=d['result']
  print(f'COPILOT JOB DONE: {d[\"id\"]}')
  print(f'Model: {r[\"model\"]} | Iterations: {r[\"iterations\"]} | Tool calls: {len(r[\"toolCalls\"])} | Elapsed: {d[\"elapsed\"]//1000}s')
  print()
  print(r['result'])
else:
  print(f'COPILOT JOB {status.upper()}: {d[\"id\"]} — {d.get(\"error\",\"unknown\")}')
"
    break
  fi
  sleep 15
done
