#!/usr/bin/env bash
set -euo pipefail

# /private-list — List registered private config sources
# Reads private_sources from .claude/setup-manifest.json

MANIFEST=".claude/setup-manifest.json"

if [[ ! -f "$MANIFEST" ]]; then
    echo "No setup manifest found at $MANIFEST"
    exit 0
fi

# Extract private_sources array using python (available everywhere setup.py runs)
SOURCES=$(python3 -c "
import json, sys, os
try:
    m = json.load(open('$MANIFEST'))
except (json.JSONDecodeError, FileNotFoundError):
    sys.exit(0)
sources = m.get('private_sources', [])
if not sources:
    print('No private sources registered.')
    sys.exit(0)
print(f'{len(sources)} private source(s) registered:')
print()
for s in sources:
    path = s.get('path', '?')
    prefix = s.get('prefix', '?')
    exists = os.path.isdir(path)
    status = 'OK' if exists else 'MISSING'
    # Count deployed items
    counts = []
    for key in ['rules', 'commands', 'skills', 'agents', 'hooks']:
        items = s.get(key, [])
        if items:
            counts.append(f'{len(items)} {key}')
    count_str = ', '.join(counts) if counts else 'no items'
    print(f'  [{prefix}] {path}')
    print(f'    Status: {status}')
    print(f'    Deployed: {count_str}')
    # List individual items
    for key in ['rules', 'commands', 'skills', 'agents', 'hooks']:
        items = s.get(key, [])
        for item in items:
            print(f'      {key}: {prefix}-{item}')
    print()
" 2>&1)

echo "$SOURCES"
