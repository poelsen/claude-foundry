#!/usr/bin/env bash
# install-copilot-mcp.sh — Build and install the VS Code Copilot MCP extension.
#
# Invoked by setup.py when the user selects the copilot-mcp MCP server,
# or run manually by a user after `setup.py init`.
#
# Requirements (checked up front, fail gracefully if missing):
#   - VS Code CLI (`code`)
#   - Node.js >= 20
#   - npm
#   - bash, curl, python3, awk, mktemp (for watch-job.sh)
#
# Idempotent: can be re-run safely to pick up source changes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FOUNDRY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
EXT_DIR="$FOUNDRY_ROOT/vscode-copilot-mcp"

if [[ ! -d "$EXT_DIR" ]]; then
    echo "ERROR: $EXT_DIR not found — is this a claude-foundry checkout?" >&2
    exit 1
fi

# ── Prerequisite checks ─────────────────────────────────────────────
missing=()
for cmd in code node npm bash curl python3 awk mktemp; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        missing+=("$cmd")
    fi
done

if (( ${#missing[@]} > 0 )); then
    echo "ERROR: missing required commands: ${missing[*]}" >&2
    echo "" >&2
    echo "Install the missing tools and re-run:" >&2
    echo "  - code   — VS Code CLI (install 'code' command from VS Code: Shell Command: Install 'code' command in PATH)" >&2
    echo "  - node   — Node.js 20+ (https://nodejs.org)" >&2
    echo "  - others — standard on Linux/macOS/WSL/Git Bash" >&2
    exit 1
fi

node_major=$(node --version | sed 's/^v//' | cut -d. -f1)
if (( node_major < 20 )); then
    echo "ERROR: Node.js >= 20 required (found v$node_major)" >&2
    exit 1
fi

echo "==> Prerequisites OK (node v$(node --version | sed 's/^v//'), npm $(npm --version))"

# ── Build the extension ─────────────────────────────────────────────
echo "==> Installing extension devDependencies"
cd "$EXT_DIR"
npm install --no-audit --no-fund --silent

echo "==> Compiling TypeScript"
npm run compile --silent

# ── Package the .vsix ──────────────────────────────────────────────
echo "==> Packaging .vsix"
rm -f vscode-copilot-mcp-*.vsix
npx --yes @vscode/vsce package --allow-missing-repository --out "$EXT_DIR" >/dev/null

VSIX=$(ls -1 "$EXT_DIR"/vscode-copilot-mcp-*.vsix 2>/dev/null | head -n1)
if [[ -z "$VSIX" ]]; then
    echo "ERROR: vsce package did not produce a .vsix" >&2
    exit 1
fi

echo "==> Built: $(basename "$VSIX")"

# ── Install in VS Code ─────────────────────────────────────────────
echo "==> Installing extension in VS Code"
code --install-extension "$VSIX" --force >/dev/null

# ── Install MCP bridge deps ────────────────────────────────────────
echo "==> Installing MCP bridge dependencies"
cd "$EXT_DIR/mcp"
npm install --no-audit --no-fund --silent

# ── Post-install notice ────────────────────────────────────────────
cat <<EOF

══════════════════════════════════════════════════════════════════════
  Copilot MCP extension installed successfully.
══════════════════════════════════════════════════════════════════════

Next steps:

  1. Restart Claude Code
     The MCP server process is spawned at startup and will not see
     the new entry until you restart.

  2. Open your project workspace in VS Code
     The extension auto-starts and writes connection info to
     .vscode/copilot-mcp.json in the workspace root.

  3. Verify from Claude Code in that workspace:
        /copilot-list-models

  4. Add to your project's .gitignore:
        .vscode/copilot-mcp.json
        .vscode/copilot-mcp-sessions/

Requires a GitHub Copilot subscription with model access.
See vscode-copilot-mcp/FOUNDRY-INTEGRATION.md for tribal knowledge
and troubleshooting.

══════════════════════════════════════════════════════════════════════
EOF
