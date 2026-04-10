#!/usr/bin/env bash
# install-copilot-mcp.sh — Install the VS Code Copilot MCP extension.
#
# Prefers a pre-built .vsix from the foundry release tarball (fast path,
# ~2s install). Falls back to building from source when no .vsix exists
# (git clone without a prior build), using the full build chain:
#   npm install -> tsc -> vsce package -> code --install-extension
#
# Always installs MCP bridge dependencies in vscode-copilot-mcp/mcp/ — the
# bridge runs on the host, not inside VS Code, and depends on
# @modelcontextprotocol/sdk at runtime regardless of how the extension
# itself was built.
#
# Invoked by setup.py when the user selects the copilot-mcp MCP server,
# or run manually by a user after `setup.py init`.
#
# Idempotent — re-runs safely.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FOUNDRY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
EXT_DIR="$FOUNDRY_ROOT/vscode-copilot-mcp"

if [[ ! -d "$EXT_DIR" ]]; then
    echo "ERROR: $EXT_DIR not found — is this a claude-foundry checkout?" >&2
    exit 1
fi

# ── Detect pre-built .vsix ──────────────────────────────────────────
PREBUILT_VSIX=$(ls -1 "$EXT_DIR"/vscode-copilot-mcp-*.vsix 2>/dev/null | head -n1)

# ── Prerequisite checks ─────────────────────────────────────────────
# Always required (bridge runtime + final install step)
always_required=("code" "node" "npm" "bash" "curl" "python3" "awk" "mktemp")
missing=()
for cmd in "${always_required[@]}"; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        missing+=("$cmd")
    fi
done

if (( ${#missing[@]} > 0 )); then
    echo "ERROR: missing required commands: ${missing[*]}" >&2
    echo "" >&2
    echo "Install the missing tools and re-run:" >&2
    echo "  - node   — Node.js 20+ (https://nodejs.org)" >&2
    echo "  - others — standard on Linux/macOS/WSL/Git Bash" >&2
    if [[ " ${missing[*]} " == *" code "* ]]; then
        echo "" >&2
        echo "  Note: 'code' is the shell command on your PATH that controls VS Code" >&2
        echo "  (used here for 'code --install-extension <vsix>'), NOT the integrated" >&2
        echo "  terminal panel inside VS Code." >&2
        echo "" >&2
        echo "  On Linux / macOS / native Windows: install via VS Code's command palette" >&2
        echo "  ('Shell Command: Install code command in PATH'), then restart your shell." >&2
        echo "" >&2
        echo "  On WSL: 'code' is typically not available in a plain WSL shell. Open a" >&2
        echo "  terminal inside VS Code (with your WSL workspace attached) and re-run" >&2
        echo "  this script from there — 'code' will be on PATH inside that terminal." >&2
    fi
    exit 1
fi

node_major=$(node --version | sed 's/^v//' | cut -d. -f1)
if (( node_major < 20 )); then
    echo "ERROR: Node.js >= 20 required (found v$node_major)" >&2
    exit 1
fi

echo "==> Prerequisites OK (node v$(node --version | sed 's/^v//'), npm $(npm --version))"

# ── Path A: Pre-built .vsix available ──────────────────────────────
if [[ -n "$PREBUILT_VSIX" ]]; then
    echo "==> Using pre-built extension: $(basename "$PREBUILT_VSIX")"
    VSIX="$PREBUILT_VSIX"
else
    # ── Path B: Build from source ──────────────────────────────────
    echo "==> No pre-built .vsix found — building extension from source"
    cd "$EXT_DIR"

    echo "==> Installing extension devDependencies"
    npm install --no-audit --no-fund --silent

    echo "==> Compiling TypeScript"
    npm run compile --silent

    echo "==> Packaging .vsix"
    rm -f vscode-copilot-mcp-*.vsix
    npx --yes @vscode/vsce package --allow-missing-repository --out "$EXT_DIR" >/dev/null

    VSIX=$(ls -1 "$EXT_DIR"/vscode-copilot-mcp-*.vsix 2>/dev/null | head -n1)
    if [[ -z "$VSIX" ]]; then
        echo "ERROR: vsce package did not produce a .vsix" >&2
        exit 1
    fi
    echo "==> Built: $(basename "$VSIX")"
fi

# ── Install .vsix in VS Code ───────────────────────────────────────
echo "==> Installing extension in VS Code"
code --install-extension "$VSIX" --force >/dev/null

# ── Install MCP bridge runtime deps ─────────────────────────────────
# Required regardless of how the extension was built — server.js runs
# on the host and depends on @modelcontextprotocol/sdk.
echo "==> Installing MCP bridge dependencies"
cd "$EXT_DIR/mcp"
npm install --no-audit --no-fund --silent

# ── Post-install notice ────────────────────────────────────────────
cat <<EOF

══════════════════════════════════════════════════════════════════════
  Copilot MCP extension installed successfully.
══════════════════════════════════════════════════════════════════════

Next steps (REQUIRED — the extension is DISABLED by default):

  1. Enable the extension for your project workspace
     In your project root, add or edit .vscode/settings.json:

         {
           "copilot-mcp.autoStart": true
         }

     The extension is disabled in every VS Code window by default so
     it only runs in workspaces where you actually want the bridge.

  2. Make the setting take effect (extension reads autoStart at
     activation, so a runtime change isn't picked up by the running
     instance). Pick one:
       - Run "Developer: Reload Window" from the VS Code command palette, OR
       - Run "Copilot MCP: Start Server" from the command palette
     A full VS Code restart is NOT required.

  3. Restart Claude Code (one-time, only after the very first install).
     The MCP bridge process is spawned at startup and will not see the
     new .claude.json entry until you restart.

  4. Open your project workspace in VS Code (if not already open).
     The extension writes connection info to .vscode/copilot-mcp.json.

  5. Verify from Claude Code in that workspace:
        /copilot-list-models

RUNTIME REQUIREMENTS (every time you use /copilot-* commands):
  - VS Code is running
  - The project folder is open as a workspace in VS Code
  - Claude Code is launched from within that workspace tree
  - .vscode/settings.json has copilot-mcp.autoStart = true

Requires a GitHub Copilot subscription with model access.

══════════════════════════════════════════════════════════════════════
EOF
