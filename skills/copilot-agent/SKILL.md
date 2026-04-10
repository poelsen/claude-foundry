---
name: copilot-agent
description: Run an autonomous agent task on Copilot tokens with full workspace access. Usage: /copilot-agent [model] [session] <task>
---

# /copilot-agent — Autonomous Copilot Agent

Launch an autonomous agent that runs on Copilot tokens with full VS Code workspace access. The agent can read/write files, search code, and run shell commands.

## Usage

```
/copilot-agent [model] [session:<name>] <task>
```

- **model**: Model family (default: `claude-sonnet-4.6`)
- **session:<name>**: Named session for persistent context (optional). Use to continue multi-turn work.
- **task**: What the agent should do. Be specific.

## Examples

```
/copilot-agent Summarize the authentication module
/copilot-agent gpt-5.4 session:refactor Refactor the data pipeline for better error handling
/copilot-agent claude-opus-4.6 session:refactor Now add tests for the changes you made
```

## Instructions

1. Parse arguments:
   - If first word matches a known model family pattern (contains `claude`, `gpt`, `gemini`, `grok`), use it as model.
   - If any word matches `session:<name>`, extract as sessionId.
   - If any word matches `bg` or `background`, use job mode (background execution).
   - Everything else is the task.

2. **For quick tasks (default):** Call `mcp__copilot-mcp__copilot_agent` synchronously. Display result with metadata.

3. **For background mode** (user says `bg`, or model is opus, or task looks heavy): Use the job system:
   a. Call `mcp__copilot-mcp__copilot_job_start` with task, model, and optional sessionId. The response includes a ready-to-run watcher command.
   b. Run the watcher command with `Bash(run_in_background: true)`. The watcher reads the token from `.vscode/copilot-mcp.json` itself — no secrets in CLI args.
   c. Tell the user: "Agent started on `<model>`. You'll be notified when it completes."
