#!/usr/bin/env bash
# update-foundry.sh — Deterministic update script for claude-foundry configuration.
# Usage: update-foundry.sh [--check] [--interactive] [project_dir]
#
# Per-project foundry cache model: the extracted release tree is persisted
# under <project>/.claude/foundry/ so manual re-runs of setup.py always
# match this project's version. No user-level cache, no symlinks — one
# self-contained copy per project.
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

# pwd -W returns Windows-style paths under MSYS/git-bash so Python (Windows
# native) can open them; plain pwd returns MSYS paths like /d/... which break.
# On Linux/macOS pwd -W fails, and we fall back to pwd.
PROJECT_DIR="$(cd "${ARGS[0]:-$PWD}" && { pwd -W 2>/dev/null || pwd; })"
MANIFEST="$PROJECT_DIR/.claude/setup-manifest.json"

# ── Find Python (before any use) ──────────────────────────────────────
# Probe candidates by actually executing them — not just checking PATH — because
# the Windows Microsoft Store stub for python/python3 is on PATH but errors out.
# Also validates user-supplied PYTHON env override (so PYTHON=bogus fails fast).
PROBE='import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)'
if [[ -n "${PYTHON:-}" ]]; then
    if ! $PYTHON -c "$PROBE" >/dev/null 2>&1; then
        echo "Error: PYTHON=$PYTHON is not a working Python 3.11+ interpreter." >&2
        exit 1
    fi
else
    for candidate in python3 python "py -3"; do
        if $candidate -c "$PROBE" >/dev/null 2>&1; then
            PYTHON="$candidate"
            break
        fi
    done
    if [[ -z "${PYTHON:-}" ]] && command -v uv &>/dev/null; then
        # `uv run python` not `python3` — on Windows, uv's managed Python
        # only provides python.exe, and `python3` falls through to PATH (MS
        # Store stub). `python` works on all platforms.
        PYTHON="uv run python"
    fi
fi
if [[ -z "${PYTHON:-}" ]]; then
    echo "Error: No working Python 3.11+ interpreter found." >&2
    echo "Install Python 3.11+, or set PYTHON=<path> before running." >&2
    exit 1
fi

# ── Read manifest ──────────────────────────────────────────────────────
if [[ ! -f "$MANIFEST" ]]; then
    echo "Error: No manifest found at $MANIFEST"
    echo "Run setup.py init first to configure the project."
    exit 1
fi

CURRENT_VERSION=$(MANIFEST_PATH="$MANIFEST" $PYTHON -c "import json, os; print(json.load(open(os.environ['MANIFEST_PATH']))['version'])")
REPO_URL=$(MANIFEST_PATH="$MANIFEST" $PYTHON -c "import json, os; print(json.load(open(os.environ['MANIFEST_PATH']))['repo_url'])")

echo "Current version: $CURRENT_VERSION"
echo "Repository: $REPO_URL"

# ── Check latest release ───────────────────────────────────────────────
API_URL="https://api.github.com/repos/$REPO_URL/releases/latest"
RELEASE_JSON=$(curl -sL "$API_URL")

LATEST_VERSION=$(echo "$RELEASE_JSON" | $PYTHON -c "import json,sys; print(json.load(sys.stdin)['tag_name'])")
RELEASE_URL=$(echo "$RELEASE_JSON" | $PYTHON -c "import json,sys; print(json.load(sys.stdin)['html_url'])")
# Find the tarball asset specifically (not the .vsix or other attachments)
ASSET_URL=$(echo "$RELEASE_JSON" | $PYTHON -c "
import json,sys
d = json.load(sys.stdin)
for a in d.get('assets', []):
    if a['name'].endswith('.tar.gz') and 'latest' not in a['name']:
        print(a['browser_download_url'])
        break
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

# ── Download and extract to per-project cache ─────────────────────────
if [[ -z "$ASSET_URL" ]]; then
    echo "Error: No download asset found in release."
    exit 1
fi

CLAUDE_DIR="$PROJECT_DIR/.claude"
FOUNDRY_DIR="$CLAUDE_DIR/foundry"
FOUNDRY_NEW="$CLAUDE_DIR/.foundry.new"
FOUNDRY_OLD="$CLAUDE_DIR/.foundry.old"

mkdir -p "$CLAUDE_DIR"

# Clean up any leftover staging/backup from a previous failed run
rm -rf "$FOUNDRY_NEW" "$FOUNDRY_OLD"

# Download tarball to a temp location inside .claude/ so it shares the
# same filesystem as the final destination (rename is atomic on the same FS).
TMP_TARBALL="$CLAUDE_DIR/.foundry-release.tar.gz"
trap 'rm -f "$TMP_TARBALL"; rm -rf "$FOUNDRY_NEW"' EXIT

echo ""
echo "Downloading $ASSET_URL ..."
curl -sL "$ASSET_URL" -o "$TMP_TARBALL"

echo "Extracting to $FOUNDRY_NEW ..."
mkdir -p "$FOUNDRY_NEW"
tar -xzf "$TMP_TARBALL" -C "$FOUNDRY_NEW" --strip-components=1

# Sanity check: setup.py must exist in the extracted tree
if [[ ! -f "$FOUNDRY_NEW/tools/setup.py" ]]; then
    echo "Error: extracted tarball missing tools/setup.py"
    exit 1
fi

# ── Atomic swap: promote .foundry.new → foundry ───────────────────────
if [[ -d "$FOUNDRY_DIR" ]]; then
    mv "$FOUNDRY_DIR" "$FOUNDRY_OLD"
fi
mv "$FOUNDRY_NEW" "$FOUNDRY_DIR"

# ── Snapshot old state ─────────────────────────────────────────────────
OLD_COMMANDS=$(ls "$CLAUDE_DIR/commands/" 2>/dev/null | sort || true)
OLD_RULES=$(ls "$CLAUDE_DIR/rules/" 2>/dev/null | sort || true)
OLD_AGENTS=$(ls "$CLAUDE_DIR/agents/" 2>/dev/null | sort || true)
OLD_SKILLS=$(ls "$CLAUDE_DIR/skills/" 2>/dev/null | sort || true)

# ── Run setup from the per-project foundry cache ───────────────────────
echo "Applying update..."
echo ""
if ! $PYTHON "$FOUNDRY_DIR/tools/setup.py" init "$PROJECT_DIR" $INTERACTIVE_FLAG; then
    echo ""
    echo "ERROR: setup.py init failed — rolling back to previous version"
    rm -rf "$FOUNDRY_DIR"
    if [[ -d "$FOUNDRY_OLD" ]]; then
        mv "$FOUNDRY_OLD" "$FOUNDRY_DIR"
    fi
    exit 1
fi

# Success — wipe backup
rm -rf "$FOUNDRY_OLD"

# ── Report changes ─────────────────────────────────────────────────────
NEW_COMMANDS=$(ls "$CLAUDE_DIR/commands/" 2>/dev/null | sort || true)
NEW_RULES=$(ls "$CLAUDE_DIR/rules/" 2>/dev/null | sort || true)
NEW_AGENTS=$(ls "$CLAUDE_DIR/agents/" 2>/dev/null | sort || true)
NEW_SKILLS=$(ls "$CLAUDE_DIR/skills/" 2>/dev/null | sort || true)

echo ""
echo "═══════════════════════════════════════════"
echo "Update complete: $CURRENT_VERSION → $LATEST_VERSION"
echo "═══════════════════════════════════════════"
echo "  Foundry source pinned at: $FOUNDRY_DIR"
echo "  Manual re-init:           $PYTHON $FOUNDRY_DIR/tools/setup.py init $PROJECT_DIR"
echo ""

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
