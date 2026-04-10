---
name: copilot-ask
description: Send a one-shot question to a Copilot model. Usage: /copilot-ask <model> <prompt>
---

# /copilot-ask — Direct Copilot Query

Send a one-shot prompt to any Copilot model. Zero Claude tokens spent on the actual work.

## Usage

```
/copilot-ask <model> <prompt>
```

**Models:** `claude-opus-4.6`, `claude-sonnet-4.6`, `gpt-5.4`, `gpt-5.4-mini`, `gemini-2.5-pro`, `grok-code-fast-1`, or any family from `/copilot-list-models`

If model is omitted, default to `claude-sonnet-4.6`.

## Instructions

1. Parse the arguments: first word is the model family, rest is the prompt. If the first word doesn't look like a model name, treat the entire input as the prompt and use default model.
2. Call `mcp__copilot-mcp__copilot_chat` with the parsed model and prompt.
3. Display the response to the user. Prefix with which model was used.
