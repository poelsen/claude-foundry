---
name: copilot-multi
description: Fan-out a task to multiple Copilot models and compare results. Usage: /copilot-multi [models] <task>
model: opus
---

# /copilot-multi — Multi-Model Comparison

Send the same task to multiple Copilot models in parallel and compare their responses. Great for cross-validation, getting diverse perspectives, or finding the best model for a task type.

## Usage

```
/copilot-multi [models:<comma-separated>] <task>
```

- **models**: Comma-separated list (default: `claude-opus-4.6,gpt-5.4,claude-sonnet-4.6`)
- **task**: The prompt/task to send to all models

## Examples

```
/copilot-multi Review this error handling approach
/copilot-multi models:gpt-5.4,gemini-2.5-pro,claude-opus-4.6 What are the security risks in src/auth.py?
```

## Instructions

1. Parse arguments:
   - If first word matches `models:<list>`, extract the model list.
   - Everything else is the task.
   - Default models: `claude-opus-4.6`, `gpt-5.4`, `claude-sonnet-4.6`

2. For simple tasks (no workspace access needed): call `mcp__copilot-mcp__copilot_chat` for each model in parallel (use multiple tool calls in one message).

3. For tasks that need workspace access (file reading, code search, etc.): call `mcp__copilot-mcp__copilot_agent` for each model in parallel, each with a unique sessionId like `"multi-{model}"`.

4. Present results side-by-side:
   - Show each model's response under a clear header
   - Add a **Synthesis** section at the end highlighting:
     - Where models agree (high confidence findings)
     - Where models disagree (needs investigation)
     - Unique insights from each model
