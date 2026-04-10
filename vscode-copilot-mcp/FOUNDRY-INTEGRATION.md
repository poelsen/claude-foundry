# Copilot MCP — claude-foundry Integration Guide

## What It Does

Routes Claude Code tasks to VS Code Copilot models (Claude Opus/Sonnet 4.6, GPT-5.4, Gemini 3.1, Grok, etc.) via an MCP bridge. Saves Claude tokens by offloading work to your existing Copilot subscription. Supports multiple VS Code windows with parallel Claude Code sessions.

**Two components:**
1. **VS Code extension** — HTTP server inside VS Code, proxies to `vscode.lm` API
2. **MCP bridge** — Node.js stdio MCP server that forwards Claude Code tool calls to the extension's HTTP endpoint

## Architecture

```
Claude Code CLI (in project dir)
  → MCP bridge (stdio, discovers .vscode/copilot-mcp.json)
    → HTTP (127.0.0.1:<auto-port>, Bearer auth)
      → VS Code extension (same project workspace)
        → vscode.lm API (copilot vendor)
          → Model (Opus 4.6, GPT-5.4, Gemini, etc.)
```

Each VS Code window writes its own `{port, token}` to the workspace's `.vscode/copilot-mcp.json`. The MCP bridge discovers this file by walking upward from the cwd. With the default `copilot-mcp.port: 0`, the OS assigns a free port to each window so multiple VS Code windows on different projects work in parallel without port collision.

## Prerequisites

- VS Code with GitHub Copilot Chat (paid subscription with model access)
- Node.js >= 20
- For `mcp/watch-job.sh` (used by background jobs): `bash`, `curl`, `python3`, `awk`, `mktemp` (all standard on Linux/macOS/WSL/Git Bash)
- **Windows note**: `watch-job.sh` only runs in a bash-compatible shell (WSL, Git Bash, Cygwin). Native PowerShell/cmd is not supported for the background-job watcher.

## Integration with claude-foundry

**Source layout in this repo:** the TypeScript lives under `src/`, the MCP bridge under `mcp/`. The `copilot-*` slash-command skills are NOT in this repo — they currently live in the development foundry at `~/.claude/skills/copilot-*`. They need to be copied/moved into this repo (under e.g. `skills/`) before the foundry can pick them up.

**Layout under claude-foundry:**
```
claude-foundry/
  vscode-copilot-mcp/            ← entire repo, git submodule or copy
    src/                         ← TypeScript sources
    out/                         ← compiled .js (built by foundry setup, or committed)
    mcp/
      server.js
      watch-job.sh
      node_modules/              ← installed by foundry setup
      package.json
    skills/                      ← MOVE copilot-* skill dirs here (currently under ~/.claude/skills/)
      copilot-list-models/
      copilot-ask/
      copilot-review/
      copilot-audit/
      copilot-agent/
      copilot-multi/
      copilot-job/
    package.json
    FOUNDRY-INTEGRATION.md
  scripts/
    install-copilot-mcp.sh       ← foundry install script (see below)
```

### What foundry's setup needs to do

1. **Build the .vsix** (if not pre-built):
   ```bash
   cd vscode-copilot-mcp
   npm install
   npm run compile
   npx @vscode/vsce package --allow-missing-repository
   ```
2. **Install extension in VS Code**:
   ```bash
   code --install-extension vscode-copilot-mcp-*.vsix --force
   ```
3. **Install MCP bridge deps**:
   ```bash
   cd vscode-copilot-mcp/mcp
   npm install
   ```
4. **Deploy skills**: copy (or symlink) the `copilot-*` skill dirs from `vscode-copilot-mcp/skills/` to `~/.claude/skills/` or the target project's `.claude/skills/`.
5. **Register MCP server**: **deep-merge** into user/project `.mcp.json` (do not replace — other MCP servers may be configured):
   ```json
   {
     "mcpServers": {
       "copilot-mcp": {
         "command": "node",
         "args": ["<foundry-root>/vscode-copilot-mcp/mcp/server.js"]
       }
     }
   }
   ```
6. **Tell the user to restart Claude Code** — the MCP server process is spawned at startup and won't see the new entry until restart.
7. **Verify installation**:
   - Open the target workspace in VS Code (extension auto-starts)
   - Check `.vscode/copilot-mcp.json` exists
   - From within that workspace, run `/copilot-list-models` in Claude Code

### Runtime requirements the foundry installer should check

- `code --version` — VS Code CLI available
- `node --version >= 20`
- `bash`, `curl`, `python3`, `awk`, `mktemp` on PATH (for `watch-job.sh`)
- Copilot subscription with model access — hard to check programmatically; fail gracefully if `copilot_models` returns empty

### Idempotency notes

- `code --install-extension --force` overwrites cleanly
- `npm install` in `mcp/` is idempotent
- Skill copies should be idempotent (overwrite or skip-if-exists)
- `.mcp.json` merging must be deep-merge to preserve other MCP servers

### Critical precondition

The MCP bridge discovers the extension's connection file by walking **upward from the Claude Code CLI's current working directory** looking for `.vscode/copilot-mcp.json`. This means:
- Claude Code **must be launched from within** the same workspace tree that VS Code has open
- If the user runs Claude Code from `~/unrelated-dir/` while VS Code is open in `~/my-project/`, the MCP bridge won't find the connection file

## Manual Installation (for testing without foundry)

### 1. Build the extension

```bash
cd vscode-copilot-mcp
npm install
npm run compile
```

### 2. Install in VS Code

**Option A — dev mode (for development):**
- Open `vscode-copilot-mcp/` in VS Code
- Press F5 to launch the Extension Development Host

**Option B — packaged .vsix (for end users):**
```bash
npx @vscode/vsce package --allow-missing-repository
code --install-extension vscode-copilot-mcp-0.1.0.vsix
```

The extension auto-starts the HTTP server on an auto-assigned port and writes connection info to `.vscode/copilot-mcp.json` in the workspace root.

### 3. Install MCP bridge dependencies

```bash
cd vscode-copilot-mcp/mcp
npm install
```

### 4. Register the MCP bridge in Claude Code

Add to your project's `.mcp.json` (or user-level `~/.claude.json`):

```json
{
  "mcpServers": {
    "copilot-mcp": {
      "command": "node",
      "args": ["/absolute/path/to/vscode-copilot-mcp/mcp/server.js"]
    }
  }
}
```

Restart Claude Code to pick up the new MCP server.

### 5. Deploy skills (optional but recommended)

Copy these directories to `~/.claude/skills/`:

| Skill | Command | Purpose |
|---|---|---|
| `copilot-list-models/` | `/copilot-list-models` | List available models |
| `copilot-ask/` | `/copilot-ask <model> <prompt>` | One-shot question |
| `copilot-review/` | `/copilot-review [model] [target]` | Code review |
| `copilot-audit/` | `/copilot-audit [skill] [model] [target]` | Adversarial audit |
| `copilot-agent/` | `/copilot-agent [model] [session:name] <task>` | Autonomous agent |
| `copilot-multi/` | `/copilot-multi [models:list] <task>` | Fan-out to multiple models |
| `copilot-job/` | `/copilot-job [start\|status\|list] <args>` | Background jobs |

### 6. Gitignore

Add to your project's `.gitignore`:
```
.vscode/copilot-mcp.json
.vscode/copilot-mcp-sessions/
```

These contain auth tokens and session history — never commit.

## MCP Tools Exposed

| Tool | Description |
|---|---|
| `copilot_models` | List all available Copilot models with capabilities |
| `copilot_chat` | Stateless prompt → response (any model) |
| `copilot_agent` | Autonomous agent loop with workspace tools |
| `copilot_job_start` | Start a long-running agent task in the background |
| `copilot_job_status` | Check job status / retrieve results |
| `copilot_jobs` | List, cancel, or delete background jobs |
| `copilot_sessions` | List, view, or delete persistent sessions |

## Agent Tools (what the Copilot model can do)

| Tool | Purpose |
|---|---|
| `readFile(path, root?)` | Read file (5MB limit, multi-root aware) |
| `listFiles(pattern, root?)` | Glob-based file discovery |
| `searchText(query, glob?, root?)` | Ripgrep across workspace |
| `editFile(path, old_text, new_text, replace_all?, root?)` | Edit or create files (per-file lock, ambiguity detection) |
| `runCommand(command, timeout?, root?)` | Execute shell (destructive command blocklist) |
| `getDiagnostics(path?, severity?, root?)` | LSP errors/warnings without running build |
| `getSymbols(path, root?)` | File symbol outline from language server |
| `getDefinition(path, line, character, root?)` | Go-to-definition |
| `getHover(path, line, character, root?)` | Type info and docs |
| `webFetch(url, timeout?)` | Fetch URL (SSRF-protected, 5MB response cap) |
| `listWorkspaceRoots()` | List workspace folders (for multi-root) |

Tool results are truncated at 15K chars to prevent context overflow.

## VS Code Extension Settings

| Setting | Default | Description |
|---|---|---|
| `copilot-mcp.port` | 0 (auto) | HTTP server port. 0 = OS picks free port. |
| `copilot-mcp.autoStart` | true | Start server on VS Code launch |
| `copilot-mcp.allowUnsafeCommands` | false | Bypass the destructive command blocklist |

## Security Posture

### Hard security controls

- HTTP server binds to `127.0.0.1` only
- Random 256-bit token per session, timing-safe comparison
- Token file at `.vscode/copilot-mcp.json` with mode 0600 (POSIX only)
- All endpoints except `/health` require `Authorization: Bearer <token>`
- **SSRF protection** in `webFetch`: blocks loopback, private networks (RFC1918), link-local (169.254/16 including cloud metadata), multicast, IPv6 loopback/ULA/link-local, IPv4-mapped IPv6 in both dotted and hex form, DNS rebinding (resolves hostnames and verifies IPs), redirect chains (validates every hop)
- **Path traversal** protection on all file tools (validates resolved path stays under workspace root)
- **Session ID** validated against `/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,199}$/`
- **Atomic session writes** (tmp + rename prevents partial/corrupt files)
- **Per-file / per-session locks** prevent concurrent write races
- **Runtime validation** on all LLM-supplied tool arguments (strict type checks)
- **Client disconnect cancellation** — LM requests and agent loops abort when HTTP client closes
- **Request body cap** 1MB (byte-counted, not char-counted)
- **readFile size cap** 5MB (stat check before read prevents OOM)
- **webFetch response cap** 5MB (streamed with byte limit)
- **Structured logging** to dedicated VS Code OutputChannel with ISO timestamps

### Deliberate trade-offs (accepted, not fixed)

- **Command blocklist, not allowlist.** Destructive patterns (rm -rf, mkfs, dd, curl|sh, chown, etc.) are denied, bypassable via `allowUnsafeCommands` config. A determined LLM could bypass via `python3 -c`, `node -e`, base64 decoding, etc. Accepted because allowlists are impractical for developer workflows.
- **Sessions and jobs auto-persist with no TTL.** Session files in `.vscode/copilot-mcp-sessions/` grow without bound. Match industry behavior (ChatGPT, Copilot Chat, Cursor all do this). User manages retention manually via `copilot_sessions delete` / `copilot_jobs delete`.
- **No concurrency cap on /agent or /jobs.** An authenticated caller with the bearer token can flood the extension host. Accepted because anyone with the token already has full RCE via `runCommand`.
- **Task and tool-call argument previews are logged.** If user prompts or file contents contain secrets, they land in the VS Code output channel and may end up in bug reports. Documented as user responsibility.
- **No hard wall-clock timeout on agent loops.** Long tasks can run for hours. User cancels via `copilot_jobs cancel` when stuck.
- **`.gitignore` not auto-managed.** Users are documented to add `.vscode/copilot-mcp.json` and `.vscode/copilot-mcp-sessions/` themselves.
- **Native Windows 0o600 not enforced.** NTFS ignores POSIX mode. Documented; user hardens via `icacls` on shared Windows systems.

### Platform notes

- **Linux/macOS/WSL**: `0o600` enforced; fully supported
- **Native Windows / NTFS**: Node's `mode` option to `fsp.writeFile` is silently ignored on Windows. Token file inherits parent directory ACLs. Safe on single-user machines; harden manually via `icacls` on shared systems. (We mitigate by deleting then recreating plus explicit `fsp.chmod`, but NTFS doesn't honor POSIX mode.)

## Available Models

The available model list is discovered dynamically from `vscode.lm.selectChatModels()` at runtime — the exact count depends on your Copilot subscription tier and which models are currently enabled. Typical install shows ~20+ models across Claude (Opus/Sonnet/Haiku 4.5-4.6), GPT (4.1-5.4), Gemini (2.5-3.1), and Grok families. Run `/copilot-list-models` to see your actual list.

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `Cannot find .vscode/copilot-mcp.json` | Extension not running or Claude Code running outside the workspace | Start VS Code with the workspace; run Claude Code from the same directory tree |
| `Unauthorized` (401) | Stale token from extension restart | Restart Claude Code so MCP bridge re-reads token |
| `Copilot MCP extension not reachable` | Extension crashed, connection file stale | Restart VS Code / the extension dev host |
| `EADDRINUSE` / server failed to bind | User explicitly set `copilot-mcp.port` to a fixed value that's already taken | Set `copilot-mcp.port` back to `0` in VS Code settings (auto-assign) |
| "Allow" popup on first request | VS Code permission for `vscode.lm` API | Click Allow — persists for the session |
| Empty response from model | Wrong vendor routing | Should not happen; extension forces `vendor: copilot` on all request paths |
| `Message exceeds token limit` | Session history grew too large | Start a fresh session or delete the existing one via `copilot_sessions delete` |
| Job stuck / hanging | LM backend slow, extension host blocked | Cancel via `copilot_jobs cancel <id>`, then restart extension if needed |
| Watch-job.sh exits "server unreachable" | Extension stopped mid-job | Restart extension, job is lost |
| "Too many redirects" from webFetch | Legitimate redirect chain >5 hops | Rare; not a real use case |
| "URL blocked" from webFetch | SSRF protection triggered | Intentional; use a non-private URL |
| `readFile` returns "exceeds limit" | File is larger than 5MB | Use `searchText` or `listFiles` instead |

## Testing

```bash
cd vscode-copilot-mcp
npm test              # 58 unit tests, ~60ms
npm run test:coverage # 100% line coverage on pure.ts
```

## Repository

Private: `github.com/poelsen/vscode-copilot-mcp`

## Known Limitations

- VS Code must be running with the extension loaded and a workspace folder open
- `vscode.lm` is stateless — sessions persist to disk but active agent state is process-local
- First LM request after extension load triggers a "Allow" popup once per VS Code session
- Token limit varies by model (~168K for Claude, ~272K for GPT-5.x)
- Large files (>5MB) rejected by `readFile` — use `searchText` instead
- `runCommand` destructive patterns blocked by default (opt out via config)

---

## Tribal Knowledge

Things we learned building this that aren't obvious from the code. Read these before making changes.

### VS Code LM API gotchas

- **Vendor matters.** `vscode.lm.selectChatModels()` returns models from multiple vendors: `claude-code` (from Anthropic's own extension), `copilotcli`, and `copilot`. **Only `copilot` works for programmatic use.** If you let the selector auto-pick, you may get a `claude-code` model whose `sendRequest` returns empty responses. The extension explicitly forces `vendor: 'copilot'` — don't remove this.
- **Grok model family vs ID.** The family is `grok-code`, but the ID is `grok-code-fast-1`. Same model, two strings. Use `family`, not `id`, when selecting.
- **Native tool calling is the right path.** We initially used regex parsing of fenced ` ```tool_call ``` ` blocks. This was fragile across models. The native `vscode.lm.LanguageModelChatTool` + streaming response parts API (`LanguageModelTextPart`, `LanguageModelToolCallPart`, `LanguageModelToolResultPart`) is available in VS Code 1.93+ and widely used since. Our extension manifest declares `^1.90.0` engine — this is loose but works because the LM API was added in 1.90 and tool calling stabilized by 1.93. Consider bumping engine to `^1.93.0` if you find issues. Don't go back to prompt-based parsing.
- **System prompts aren't real.** `vscode.lm` has no true system role. We inject the "system" prompt as a User message. Prompt injection via file contents can override it — mitigated only by `runCommand` blocklist and input validation.
- **First request triggers an "Allow" popup.** The first `sendRequest` after extension activation asks the user to permit LM API access. The request blocks until the user clicks allow. We can't work around this.
- **`toolInvocationToken` is not fabricate-able.** We can enumerate VS Code's built-in chat participant tools via `vscode.lm.tools` in proposed API, but invoking them requires a `toolInvocationToken` that's only valid inside a chat participant handler. We can't call built-in Copilot tools from outside.

### Model behavior & performance

- **Opus 4.6 is slow with tools.** Can take 2–5 minutes per iteration even for simple tasks when tool schemas are present. GPT-5.4 is usually faster but less thorough. Use job-mode with background watchers for Opus; sync mode is fine for Sonnet/GPT.
- **Models will re-flag accepted issues.** Every audit round, models complain about unbounded jobs, unbounded sessions, no concurrency caps, command denylist being a denylist, etc. These are in the "consciously accepted" list because they match industry practice (ChatGPT/Copilot all do the same). Always pass a "previously fixed / accepted" list to audit prompts or you'll get repeat findings.
- **Models do different things well.** Opus finds architectural/subtle bugs (the IPv6 hex SSRF bypass was Opus-only). GPT-5.4 finds operational issues (disconnect handling, race conditions). Codex finds code-level bugs and TypeScript issues. Run all three for full coverage.
- **Opus literally tested `rm -rf .` during an audit.** Not a hallucination — the agent tried it as a security test. This proved the destructive command blocklist was needed.

### MCP / Claude Code integration

- **MCP server process is long-lived per Claude Code session.** Changes to `mcp/server.js` require a full Claude Code restart. Not just reloading the MCP config.
- **MCP tool call timeout < long agent tasks.** That's why we built the job system. Sync `copilot_agent` works for tasks under ~5 minutes. For anything longer, use `copilot_job_start` + `watch-job.sh` with `run_in_background: true`. The watcher script exits on completion and Claude Code gets a notification.
- **Polling via MCP costs tokens.** Don't have the model call `copilot_job_status` in a loop. Use the bash watcher instead — background shell loops are free.
- **Background tasks survive but state doesn't.** If Claude Code's MCP server is still running, a job started in one session can be checked from another (if you remember the jobId). If Claude Code restarts, the MCP server restarts fresh but the extension's in-memory job state persists until the extension host restarts.

### Node / fetch / HTTP gotchas

- **`fsp.writeFile({mode: 0o600})` only applies on CREATE.** Overwriting an existing file with permissive perms leaves those perms alone. Solution: delete-then-create, or explicit `fsp.chmod` after write. (Same applies to the sync `fs.writeFileSync` variant.)
- **`fetch()` follows redirects by default.** This bypasses SSRF checks on the initial URL. Always use `redirect: 'manual'` and validate every hop.
- **`URL.hostname` normalizes IPv6.** `http://[::ffff:127.0.0.1]/` → hostname is `[::ffff:7f00:1]` (hex). Your dotted-form regex won't match. Must handle both.
- **`crypto.timingSafeEqual` throws on mismatched lengths.** Always check `a.length === b.length` first, or an attacker can DoS the auth check with malformed headers.
- **`decodeURIComponent` throws on malformed `%FF`.** Unhandled rejection risk. Wrap in try/catch and return 400 on failure.
- **`http.createServer` callback doesn't await the handler.** Async throws in your handler become unhandled promise rejections. Wrap with `.catch()` at the call site.
- **`Server.closeAllConnections()` is Node 18.2+.** Without it, `server.close()` waits for in-flight connections to drain — which can be forever if there's a long streaming request.
- **`req.url` includes query strings.** Match on `new URL(req.url, 'http://localhost').pathname`, not `req.url === '/path'`.
- **Bash string interpolation into `python3 -c` is dangerous.** Paths with apostrophes break out of the string literal. Pass via env var instead.
- **`curl -s` returns exit 0 for HTTP 4xx/5xx.** Must inspect the status code with `-w '%{http_code}'` to distinguish network errors from HTTP errors.
- **`body.length` on a concatenated Buffer-to-string is char count, not bytes.** Multi-byte UTF-8 (emoji) can bypass a char-based size limit by ~4x. Sum `buf.byteLength` from raw Buffers.

### File system & workspace

- **`claude_general_stuff` is not a git repo, but contains git repos.** Git-root-based discovery (stopping the upward walk at `.git`) breaks when the workspace root is NOT a git repo but a subdirectory is. We tried this for L5 and had to revert. The upward walk looking for `.vscode/copilot-mcp.json` with NO stop condition is actually correct for VS Code workspace semantics.
- **VS Code bundles ripgrep.** At `vscode.env.appRoot/node_modules/@vscode/ripgrep/bin/rg` (and `rg.exe` on Windows). Faster than shell `grep` and works on all platforms. VS Code's own search uses it.
- **VS Code's `workspace.findTextInFiles` is proposed API.** Can't use it without enabling proposed APIs in the extension manifest. Use bundled ripgrep instead.
- **Multi-root workspaces are real.** `workspace.workspaceFolders[0]` is not always the "right" root. Tools that accept a `root` parameter (name of a WorkspaceFolder) handle this. The connection file still goes in the first root because HTTP servers are per-window, not per-root.

### Development process

- **Progress files are better than polling for long agent runs.** Tell the agent to write progress markdown every N steps. Observers read the file directly, no API calls, no tokens wasted.
- **Adversarial reviews surface real bugs even after you think you're done.** Three independent audits across multiple rounds kept finding new things. The IPv6 hex SSRF bypass was found in round 3 after we'd already "fixed" SSRF twice.
- **Meta-audits help deduplicate.** After running 3 parallel audits, feed all three reports to a single Opus instance and ask it to verify each finding against actual source. ~50% of findings were false positives, rehashes of accepted trade-offs, or already-fixed items.
- **Always pass a "consciously accepted" list.** Models will keep flagging accepted design decisions as bugs. Tell them explicitly what's off-limits.

### Dependency hygiene

- **`mcp/server.js` imports `zod` via the MCP SDK transitively.** `mcp/package.json` declares only `@modelcontextprotocol/sdk`; `zod` happens to work because the SDK pulls it in. If the SDK ever drops zod as a dep, our `server.js` breaks. **Fix if it becomes a problem**: add `zod` to `mcp/package.json` dependencies explicitly.
- **No lockfile strategy documented.** `mcp/package-lock.json` exists but wasn't analyzed for vuln scanning. Foundry should decide whether to run `npm audit` during install.

### What we deliberately didn't fix

These were raised by audits but accepted as intentional:

| Issue | Why we kept it |
|---|---|
| Unbounded job memory | Runtime state, cleared on VS Code restart; sessions persist the valuable data |
| No concurrency cap | Same as Claude Code; attacker with token already has RCE |
| No hard agent timeout | Legitimate tasks can run for hours; user cancels via `copilot_jobs cancel` |
| Command blocklist is bypassable | Denylists are fundamentally bypassable; `allowUnsafeCommands` is the opt-in escape hatch |
| Sessions auto-persist | Industry standard (ChatGPT, Copilot Chat, Cursor all do this) |
| Session ID collision theoretical | Auto-gen timestamp+slug; duplicates mean user re-ran the same task in the same second, intended behavior |
| `.gitignore` not auto-managed | Documented, not enforced |
| Native Windows 0o600 not enforced | NTFS ignores POSIX mode; documented, requires manual `icacls` on shared machines |
| No structured audit trail | Logging covers it; full tracing is overkill |
| Logging task previews | Task text may contain secrets but is useful for debugging; user responsibility |
