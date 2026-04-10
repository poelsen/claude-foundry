---
name: copilot-job
description: Start, check, or list background Copilot agent jobs. Usage: /copilot-job [start|status|list] [args]
---

# /copilot-job — Background Agent Jobs

Manage long-running Copilot agent tasks that run in the background without timeout issues.

## Usage

```
/copilot-job start [model] [session:name] <task>   — start a background job
/copilot-job status <jobId>                         — check job status / get results
/copilot-job list                                   — list all jobs
/copilot-job delete <jobId>                         — delete a completed job
```

## Instructions

1. Parse the subcommand (start/status/list/delete). Default to "list" if no args.

2. For **start**:
   a. Parse model and session like `/copilot-agent`.
   b. Call `mcp__copilot-mcp__copilot_job_start` — the response includes a ready-to-run watcher command.
   c. Run the watcher command from the response with `Bash(run_in_background: true)`. The watcher script reads the token from `.vscode/copilot-mcp.json` itself, so no secrets are passed via CLI.
   d. Tell the user: "Job `<jobId>` started on `<model>`. You'll be notified when it completes."

3. For **status**: call `mcp__copilot-mcp__copilot_job_status` with the jobId. Display results if done, or elapsed time if still running.

4. For **list**: call `mcp__copilot-mcp__copilot_jobs` with action "list". Display as a table.

5. For **delete**: call `mcp__copilot-mcp__copilot_jobs` with action "delete" and the jobId.
