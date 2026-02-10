#!/usr/bin/env bash
set -euo pipefail

# /private-remove <prefix> — Remove a private config source by prefix
# Deletes all {prefix}-* files and removes the source from manifest

PREFIX="${1:-}"

if [[ -z "$PREFIX" ]]; then
    echo "Usage: /private-remove <prefix>"
    echo ""
    echo "Run /private-list to see registered sources."
    exit 1
fi

MANIFEST=".claude/setup-manifest.json"

if [[ ! -f "$MANIFEST" ]]; then
    echo "No setup manifest found at $MANIFEST"
    exit 1
fi

# Verify prefix exists in manifest
FOUND=$(python3 -c "
import json, sys
m = json.load(open('$MANIFEST'))
sources = m.get('private_sources', [])
for s in sources:
    if s.get('prefix') == '$PREFIX':
        print('found')
        sys.exit(0)
print('not_found')
" 2>&1)

if [[ "$FOUND" != "found" ]]; then
    echo "No private source with prefix '$PREFIX' found."
    echo ""
    echo "Run /private-list to see registered sources."
    exit 1
fi

echo "Removing private source: $PREFIX"

# Remove prefixed files from all component dirs
REMOVED=0
for dir in .claude/rules .claude/agents .claude/commands; do
    if [[ -d "$dir" ]]; then
        for f in "$dir"/"${PREFIX}"-*; do
            if [[ -f "$f" ]]; then
                rm "$f"
                echo "  Removed: $f"
                REMOVED=$((REMOVED + 1))
            fi
        done
    fi
done

# Remove prefixed skill directories
if [[ -d ".claude/skills" ]]; then
    for d in .claude/skills/"${PREFIX}"-*/; do
        if [[ -d "$d" ]]; then
            rm -rf "$d"
            echo "  Removed: $d"
            REMOVED=$((REMOVED + 1))
        fi
    done
fi

# Remove prefixed hook scripts
if [[ -d ".claude/hooks/library" ]]; then
    for f in .claude/hooks/library/"${PREFIX}"-*; do
        if [[ -f "$f" ]]; then
            rm "$f"
            echo "  Removed: $f"
            REMOVED=$((REMOVED + 1))
        fi
    done
fi

# Update manifest — remove the source entry
python3 -c "
import json
m = json.load(open('$MANIFEST'))
sources = m.get('private_sources', [])
m['private_sources'] = [s for s in sources if s.get('prefix') != '$PREFIX']
if not m['private_sources']:
    del m['private_sources']
with open('$MANIFEST', 'w') as f:
    json.dump(m, f, indent=2)
    f.write('\n')
"

echo ""
echo "Removed $REMOVED files/directories with prefix '$PREFIX'"
echo "Manifest updated."
