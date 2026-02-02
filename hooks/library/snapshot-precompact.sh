#!/bin/bash
# PreCompact hook: auto-snapshot before context compaction
# Captures transcript path so /snapshot --restore can summarize later
# Cooldown: 5 minutes between auto-snapshots

input=$(cat)
command -v jq >/dev/null 2>&1 || { echo "$input"; exit 0; }

SNAPSHOT_DIR=".claude/snapshots"
STATE_FILE="${SNAPSHOT_DIR}/.last-snapshot"

# Anti-spam: skip if snapshot taken in last 5 minutes
if [ -f "$STATE_FILE" ]; then
    last=$(cat "$STATE_FILE")
    now=$(date +%s)
    elapsed=$(( now - last ))
    if [ "$elapsed" -lt 300 ]; then
        echo "$input"
        exit 0
    fi
fi

mkdir -p "$SNAPSHOT_DIR"

timestamp=$(date +%Y-%m-%d-%H%M%S)
filename="${SNAPSHOT_DIR}/${timestamp}-precompact.md"
transcript=$(echo "$input" | jq -r '.transcript_path // ""')

cat > "$filename" << SNAPSHOT
---
created: $(date -u +%Y-%m-%dT%H:%M:%SZ)
trigger: precompact
transcript: ${transcript}
goal: ""
status: in_progress
---

# Auto-snapshot (pre-compaction)

Run \`/snapshot --restore\` to extract session context from the transcript.
SNAPSHOT

date +%s > "$STATE_FILE"

# Prune: keep 10 most recent snapshots
ls -1t "$SNAPSHOT_DIR"/*.md 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null

echo "$input"
