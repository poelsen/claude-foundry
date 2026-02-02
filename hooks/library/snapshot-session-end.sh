#!/bin/bash
# SessionEnd hook: auto-snapshot on session termination
# No cooldown — always capture on exit

input=$(cat)
command -v jq >/dev/null 2>&1 || { echo "$input"; exit 0; }

SNAPSHOT_DIR=".claude/snapshots"

mkdir -p "$SNAPSHOT_DIR"

timestamp=$(date +%Y-%m-%d-%H%M%S)
filename="${SNAPSHOT_DIR}/${timestamp}-session-end.md"
transcript=$(echo "$input" | jq -r '.transcript_path // ""')

cat > "$filename" << SNAPSHOT
---
created: $(date -u +%Y-%m-%dT%H:%M:%SZ)
trigger: session-end
transcript: ${transcript}
goal: ""
status: in_progress
---

# Auto-snapshot (session end)

Run \`/snapshot --restore\` to extract session context from the transcript.
SNAPSHOT

date +%s > "${SNAPSHOT_DIR}/.last-snapshot"

# Prune: keep 10 most recent snapshots
ls -1t "$SNAPSHOT_DIR"/*.md 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null

echo "$input"
