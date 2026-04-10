---
name: copilot-audit
description: Adversarial red-team audit via Copilot agent. Usage: /copilot-audit [skill] [model] [target]
model: opus
---

# /copilot-audit — Adversarial Copilot Audit

Run a deep adversarial audit using a Copilot agent. Combines a megamind skill's analytical framework with full workspace access.

## Usage

```
/copilot-audit [skill] [model] [target]
```

- **skill**: Analysis framework to apply (default: `megamind-adversarial`). Can be any megamind skill: `megamind-deep`, `megamind-creative`, `megamind-adversarial`.
- **model**: Model family (default: `claude-opus-4.6`). For cross-model validation use `gpt-5.4`.
- **target**: What to audit — module, file, feature, architecture, or a description. Default: entire codebase.

## Instructions

1. Parse arguments. Defaults: skill=`megamind-adversarial`, model=`claude-opus-4.6`, target=entire codebase.
2. Read the chosen skill file from `.claude/skills/{skill}/SKILL.md` to get the analytical framework.
3. Build the audit task by combining the skill's framework with workspace-specific instructions:

```
{skill framework content}

Apply this analytical framework to audit the following target: {target}

You have full workspace access. Use readFile, listFiles, searchText, and runCommand to investigate thoroughly. Don't guess — read the actual code. Be specific with file paths and line references.

Focus on:
- Silent failures and error swallowing
- Data validation gaps
- Hardcoded assumptions that could break
- Security vulnerabilities
- Dead code and stub functions
- Architecture weaknesses

Rate each finding: CRITICAL / HIGH / MEDIUM / LOW with real-world impact.
Report the top 15 most dangerous findings.
```

4. Use the job system for reliability (no timeouts):
   a. Call `mcp__copilot-mcp__copilot_job_start` with the task, chosen model, and sessionId based on target (e.g. `"audit-{target-slug}"`). The response includes a ready-to-run watcher command.
   b. Run the watcher command with `Bash(run_in_background: true)`. The watcher reads the token from `.vscode/copilot-mcp.json` itself — no secrets in CLI args.
   c. Tell the user: "Audit started on `<model>`. You'll be notified when it completes."
