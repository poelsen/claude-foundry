# foundry-delegate

Tooling for running a secondary Claude Code CLI (or any OpenAI/Anthropic-compatible agent) in an isolated git worktree, pointed at a cheap model (MiniMax, Kimi, DeepSeek, …) via a local LiteLLM proxy. Used by the primary Claude Code session to offload bulk work (scraping, analysis, refactors) without burning Max / Copilot quota.

## Two modes

- **Orchestrated** — primary Claude invokes `run.sh` via Bash; gets back a JSON summary. Used for fire-and-forget tasks.
- **Interactive** — operator sources `activate.sh` (or runs `launch.sh`) to enter a delegate shell and drive it by hand.

Both modes share the same worktree + proxy + env setup in `lib.sh`.

## One-time setup

```bash
# 1. Install LiteLLM
pip install 'litellm[proxy]'

# 2. Provide at least one provider key
cp tools/delegate/.env.example .env       # or tools/delegate/.env
# edit .env — fill in MINIMAX_API_KEY (or MOONSHOT_/DEEPSEEK_/OPENROUTER_)

# 3. (Optional) customize model routing
# Edit tools/delegate/litellm.yaml — add/remove model_list entries.
```

`.env` is gitignored. Never commit it.

## Orchestrated mode (primary → secondary)

From the primary Claude Code session (or any shell):

```bash
tools/delegate/run.sh \
  --slot scrape \
  --model MiniMax-M2 \
  --max-usd 1.00 \
  --timeout 600 \
  --task "Scrape product data from urls.txt, extract name/price/sku as JSON, save to data/products.json"
```

Output is a JSON object on stdout:

```json
{
  "slot": "scrape",
  "model": "MiniMax-M2",
  "exit_reason": "complete",
  "exit_code": 0,
  "duration_s": 143,
  "files_changed": 2,
  "worktree": "/home/you/git/claude-foundry-delegate-scrape",
  "summary": "..."
}
```

Secondary's file changes are auto-committed to the `delegate/<slot>` branch in the sibling worktree. Primary can then:

```bash
tools/delegate/worktree.sh show    scrape    # inspect commits + diffstat
tools/delegate/worktree.sh merge   scrape    # merge into current branch
tools/delegate/worktree.sh discard scrape    # wipe worktree + branch
```

**`--max-usd` is mandatory** — the proxy has no cost ceiling and MiniMax is metered. Pick a number you'd be comfortable losing.

## Interactive mode (operator in a terminal)

### Option A — takeover launch

```bash
tools/delegate/launch.sh --slot scrape --model MiniMax-M2
```

Preps everything and execs `claude` in the worktree. Your terminal *is* the secondary session. `/quit` or Ctrl+D returns to your primary shell.

### Option B — activate pattern (venv-style)

Open a fresh terminal, then:

```bash
source tools/delegate/activate.sh scrape MiniMax-M2
# now cwd is the worktree, env points at the proxy
claude                    # drives MiniMax through Claude Code CLI
opencode run "task"       # or opencode, using OPENAI_BASE_URL
aider ...                 # or aider
bash                      # or just run curl/python scripts against the proxy
```

When done, close the terminal — or unset the env vars and `cd` back.

## Proxy lifecycle

The LiteLLM proxy starts automatically when needed. For manual control:

```bash
tools/delegate/proxy.sh status     # up/down
tools/delegate/proxy.sh start
tools/delegate/proxy.sh stop
tools/delegate/proxy.sh restart
tools/delegate/proxy.sh logs       # tail -f
```

Runs on `127.0.0.1:4000` by default. Override with `FOUNDRY_DELEGATE_PROXY_PORT` if 4000 is taken.

## Layout & state

- Worktrees: `../<repo>-delegate-<slot>/` (sibling to this repo, gitignored by default since they're outside the repo)
- Branches: `delegate/<slot>` in this repo
- Proxy PID/log: `$XDG_RUNTIME_DIR` or `/tmp` (`foundry-delegate-litellm.{pid,log}`)
- Event log: `.foundry/delegate-log.jsonl` (gitignored)

## Safety notes

- `.env` must never be committed.
- `run.sh` enforces `--max-usd` as a hard required arg. Interactive modes have no auto-cap — the operator is trusted. Watch cost via `tools/delegate/proxy.sh logs` or `tail -f .foundry/delegate-log.jsonl`.
- LiteLLM binds the proxy to localhost only. If you're on a shared host, also set `LITELLM_MASTER_KEY` and pass it via `ANTHROPIC_AUTH_TOKEN`.
- Secondary agents operate only within their worktree — primary repo is untouched until `worktree.sh merge`.

## Known gaps (explicit non-goals for v1)

- No async / job-id polling — `run.sh` is sync. Use Bash `run_in_background` if you need async.
- No daily cumulative budget cap — only per-task `--max-usd`. Add in a later pass if needed.
- No automatic summarization of long tool outputs before feeding back to the model — rely on the adapter + model for now.
- MiniMax tool-use quality ≠ Claude. Expect occasional misfires. Scope tasks clearly.
