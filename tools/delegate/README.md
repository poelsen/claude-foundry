# foundry-delegate

Tooling for running a secondary Claude Code CLI (or any Anthropic/OpenAI-compatible agent) in an isolated git worktree, pointed at a cheap model (MiniMax, Kimi, DeepSeek, …) via a **claude-code-router (ccr)** proxy. Used by the primary Claude Code session to offload bulk work (scraping, analysis, refactors) without burning Max / Copilot quota.

## Two modes

- **Orchestrated** — primary Claude invokes `run.sh` via Bash; gets back a JSON summary. Used for fire-and-forget tasks.
- **Interactive** — operator sources `activate.sh` (or runs `launch.sh`) to enter a delegate shell and drive it by hand.

Both modes share the same worktree + proxy + env setup in `lib.sh`.

## One-time setup

```bash
# 1. Install ccr globally (user-level prefix to avoid sudo)
mkdir -p ~/.npm-global
npm config set prefix ~/.npm-global
npm install -g @musistudio/claude-code-router
# Add ~/.npm-global/bin to PATH (or the scripts will find it automatically).

# 2. Put ccr's config at ~/.claude-code-router/config.json
cp tools/delegate/ccr-config.example.json ~/.claude-code-router/config.json
# Edit if you want to change models / add providers. The default routes
# everything to MiniMax M2 via api.minimax.io (the Coding Plan endpoint).

# 3. Provide the MiniMax Coding Plan key (sk-cp-…)
cp tools/delegate/.env.example .env
# edit .env — fill in MINIMAX_API_KEY (matches $MINIMAX_API_KEY refs in
# the ccr config above; lib.sh's load_env exports it before starting ccr).
```

`.env` is gitignored. Never commit it.

## Orchestrated mode (primary → secondary)

From the primary Claude Code session (or any shell, inside the target project's git repo):

```bash
tools/delegate/run.sh \
  --job scrape \
  --model MiniMax-M2 \
  --timeout 600 \
  --task "Scrape product data from urls.txt, extract name/price/sku as JSON, save to data/products.json"
```

Output is a JSON object on stdout:

```json
{
  "job": "scrape",
  "model": "MiniMax-M2",
  "exit_reason": "complete",
  "exit_code": 0,
  "duration_s": 143,
  "files_changed": 2,
  "worktree": "/home/you/git/claude-foundry-delegate-scrape",
  "summary": "..."
}
```

Secondary's file changes are auto-committed to the `delegate/<job>` branch in the sibling worktree. Primary can then:

```bash
tools/delegate/worktree.sh show    scrape    # inspect commits + diffstat
tools/delegate/worktree.sh merge   scrape    # merge into current branch
tools/delegate/worktree.sh discard scrape    # wipe worktree + branch
```

## Interactive mode (operator in a terminal)

### Option A — takeover launch

```bash
tools/delegate/launch.sh --job scrape --model MiniMax-M2
```

Preps everything and execs `claude` in the worktree. Your terminal *is* the secondary session. `/quit` or Ctrl+D returns to your primary shell.

### Option B — activate pattern (venv-style)

Open a fresh terminal, then:

```bash
source tools/delegate/activate.sh scrape MiniMax-M2
# now cwd is the worktree, env points at the ccr proxy
claude                    # drives MiniMax through Claude Code CLI
opencode run "task"       # or opencode, using OPENAI_BASE_URL — goes through ccr
aider ...                 # or aider
bash                      # or plain curl/python scripts against the proxy
```

When done, close the terminal — or unset the env vars and `cd` back.

## Proxy lifecycle

ccr starts automatically when needed. For manual control:

```bash
tools/delegate/proxy.sh status     # up/down
tools/delegate/proxy.sh start
tools/delegate/proxy.sh stop
tools/delegate/proxy.sh restart
tools/delegate/proxy.sh logs       # tail ccr log files
```

Listens on `127.0.0.1:3456` by default. Override with `FOUNDRY_DELEGATE_PROXY_PORT` (and update ccr's config to match) if 3456 is taken.

## Layout & state

- Worktrees: `../<repo>-delegate-<job>/` (sibling to this repo — automatically isolated; never touches primary)
- Branches: `delegate/<job>` in this repo
- ccr config + logs: `~/.claude-code-router/`
- Event log: `.foundry/delegate-log.jsonl` (gitignored)

## Safety notes

- `.env` must never be committed.
- ccr binds the proxy to `127.0.0.1` by default. If you're on a shared host, set `APIKEY` in ccr's config to require a bearer token.
- Secondary agents operate only within their worktree — primary repo is untouched until `worktree.sh merge`.

## Known gaps (explicit non-goals for v1)

- No async / job-id polling — `run.sh` is sync. Use Bash `run_in_background` if you need async.
- No cost metering at all — fine for flat-rate providers (MiniMax Coding Plan), not safe for metered ones. Add a `--max-usd` cap if/when needed.
- MiniMax tool-use quality ≠ Claude. Expect occasional misfires. Scope tasks clearly.
