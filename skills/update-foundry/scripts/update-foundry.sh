#!/usr/bin/env bash
# update-foundry.sh — Deterministic update script for claude-foundry configuration.
# Usage: update-foundry.sh [--check] [--interactive] [project_dir]
set -euo pipefail

CHECK_ONLY=false
INTERACTIVE_FLAG="--non-interactive"

# Parse flags
ARGS=()
for arg in "$@"; do
    case "$arg" in
        --check) CHECK_ONLY=true ;;
        --interactive) INTERACTIVE_FLAG="" ;;
        *) ARGS+=("$arg") ;;
    esac
done

PROJECT_DIR="${ARGS[0]:-$PWD}"
MANIFEST="$PROJECT_DIR/.claude/setup-manifest.json"

# ── Read manifest ──────────────────────────────────────────────────────
if [[ ! -f "$MANIFEST" ]]; then
    echo "Error: No manifest found at $MANIFEST"
    echo "Run setup.py init first to configure the project."
    exit 1
fi

CURRENT_VERSION=$(python3 -c "import json; print(json.load(open('$MANIFEST'))['version'])")
REPO_URL=$(python3 -c "import json; print(json.load(open('$MANIFEST'))['repo_url'])")

echo "Current version: $CURRENT_VERSION"
echo "Repository: $REPO_URL"

# ── Check latest release ───────────────────────────────────────────────
API_URL="https://api.github.com/repos/$REPO_URL/releases/latest"
RELEASE_JSON=$(curl -sL "$API_URL")

LATEST_VERSION=$(echo "$RELEASE_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['tag_name'])")
RELEASE_URL=$(echo "$RELEASE_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['html_url'])")
ASSET_URL=$(echo "$RELEASE_JSON" | python3 -c "
import json,sys
d = json.load(sys.stdin)
assets = d.get('assets', [])
print(assets[0]['browser_download_url'] if assets else '')
")

echo "Latest version: $LATEST_VERSION"
echo "Release: $RELEASE_URL"

if [[ "$CURRENT_VERSION" == "$LATEST_VERSION" ]]; then
    echo ""
    echo "Already up to date."
    exit 0
fi

echo ""
echo "Update available: $CURRENT_VERSION → $LATEST_VERSION"

if [[ "$CHECK_ONLY" == true ]]; then
    exit 0
fi

# ── Download and extract ───────────────────────────────────────────────
if [[ -z "$ASSET_URL" ]]; then
    echo "Error: No download asset found in release."
    exit 1
fi

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

echo ""
echo "Downloading $ASSET_URL ..."
curl -sL "$ASSET_URL" -o "$TMPDIR/release.tar.gz"
tar -xzf "$TMPDIR/release.tar.gz" -C "$TMPDIR"

# Find extracted directory
EXTRACTED=$(find "$TMPDIR" -maxdepth 1 -type d -name "claude-foundry-*" | head -1)
if [[ -z "$EXTRACTED" ]]; then
    echo "Error: Could not find extracted release directory."
    exit 1
fi

# ── Find Python ────────────────────────────────────────────────────────
PYTHON=""
if command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    PY_VERSION=$(python --version 2>&1 | grep -oP '\d+' | head -1)
    if [[ "$PY_VERSION" == "3" ]]; then
        PYTHON="python"
    fi
fi
if [[ -z "$PYTHON" ]] && command -v uv &>/dev/null; then
    PYTHON="uv run python3"
fi
if [[ -z "$PYTHON" ]]; then
    echo "Error: No Python 3 interpreter found."
    exit 1
fi

# ── Snapshot old state ─────────────────────────────────────────────────
CLAUDE_DIR="$PROJECT_DIR/.claude"
OLD_COMMANDS=$(ls "$CLAUDE_DIR/commands/" 2>/dev/null | sort || true)
OLD_RULES=$(ls "$CLAUDE_DIR/rules/" 2>/dev/null | sort || true)
OLD_AGENTS=$(ls "$CLAUDE_DIR/agents/" 2>/dev/null | sort || true)
OLD_SKILLS=$(ls "$CLAUDE_DIR/skills/" 2>/dev/null | sort || true)

# ── Run setup ──────────────────────────────────────────────────────────
echo "Applying update..."
echo ""
$PYTHON "$EXTRACTED/tools/setup.py" init "$PROJECT_DIR" $INTERACTIVE_FLAG

# ── Report changes ─────────────────────────────────────────────────────
NEW_COMMANDS=$(ls "$CLAUDE_DIR/commands/" 2>/dev/null | sort || true)
NEW_RULES=$(ls "$CLAUDE_DIR/rules/" 2>/dev/null | sort || true)
NEW_AGENTS=$(ls "$CLAUDE_DIR/agents/" 2>/dev/null | sort || true)
NEW_SKILLS=$(ls "$CLAUDE_DIR/skills/" 2>/dev/null | sort || true)

echo ""
echo "═══════════════════════════════════════════"
echo "Update complete: $CURRENT_VERSION → $LATEST_VERSION"
echo "═══════════════════════════════════════════"

CHANGES=false
if [[ "$OLD_COMMANDS" != "$NEW_COMMANDS" ]]; then
    echo "  Commands changed — available immediately"
    CHANGES=true
fi
if [[ "$OLD_RULES" != "$NEW_RULES" ]]; then
    echo "  Rules changed — take effect next interaction"
    CHANGES=true
fi
if [[ "$OLD_AGENTS" != "$NEW_AGENTS" ]]; then
    echo "  Agents changed — load on demand"
    CHANGES=true
fi
if [[ "$OLD_SKILLS" != "$NEW_SKILLS" ]]; then
    echo "  Skills changed — available immediately"
    CHANGES=true
fi
if [[ "$CHANGES" == false ]]; then
    echo "  Version bumped, configuration unchanged"
fi
