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
        echo "  About 'code': it's a SHELL command on your PATH that controls VS Code" >&2
        echo "  from outside (used here for 'code --install-extension <vsix>'). It is" >&2
        echo "  NOT the integrated terminal panel inside VS Code." >&2
        echo "" >&2
        echo "  Install on Linux/macOS/native Windows:" >&2
        echo "    VS Code → Ctrl+Shift+P → 'Shell Command: Install code command in PATH'" >&2
        echo "    Then restart your shell." >&2
        echo "" >&2
        echo "  WSL note: 'code' is typically NOT available in a plain WSL shell." >&2
        echo "  The VS Code Server CLI only works from inside an integrated VS Code" >&2
        echo "  terminal. Open VS Code with your WSL workspace attached, then open" >&2
        echo "  a terminal panel via the menu: View → Terminal (the Ctrl+\` shortcut" >&2
        echo "  works on US/UK layouts but not on Nordic/dead-key layouts; use the" >&2
        echo "  menu or rebind 'Toggle Integrated Terminal' in Keyboard Shortcuts)." >&2
        echo "  Re-run this script from that terminal — 'code' will be on PATH there." >&2
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
     This per-workspace opt-in prevents it from running in unrelated
     VS Code windows.

  2. Restart Claude Code
     The MCP server process is spawned at startup and will not see
     the new entry until you restart.

  3. Open your project workspace in VS Code
     The extension auto-starts (because you enabled it in step 1) and
     writes connection info to .vscode/copilot-mcp.json.

  4. Verify from Claude Code in that workspace:
        /copilot-list-models

  5. Add to your project's .gitignore:
        .vscode/copilot-mcp.json
        .vscode/copilot-mcp-sessions/

RUNTIME REQUIREMENTS (every time you use /copilot-* commands):
  - VS Code is running
  - The project folder is open as a workspace in VS Code
  - Claude Code is launched from within that workspace tree
  - .vscode/settings.json has copilot-mcp.autoStart = true

Requires a GitHub Copilot subscription with model access.
See vscode-copilot-mcp/FOUNDRY-INTEGRATION.md for tribal knowledge
and troubleshooting.

══════════════════════════════════════════════════════════════════════
EOF
