#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const CONNECTION_FILE = ".vscode/copilot-mcp.json";

function getConnection() {
  // Walk up from cwd looking for .vscode/copilot-mcp.json. First match wins.
  // Note: we do NOT stop at .git because the VS Code workspace may be a
  // parent directory that itself is not a git repo but contains git
  // subdirectories. The token is per-workspace and the workspace is
  // identified by whichever directory contains .vscode/copilot-mcp.json.
  let dir = process.cwd();
  while (true) {
    const candidate = join(dir, CONNECTION_FILE);
    if (existsSync(candidate)) {
      try {
        const data = JSON.parse(readFileSync(candidate, "utf-8"));
        if (data.port && data.token) return data;
      } catch { /* fall through */ }
    }
    const parent = join(dir, "..");
    if (parent === dir) break;
    dir = parent;
  }
  throw new Error(
    `Cannot find ${CONNECTION_FILE} in current or parent directories. Is VS Code running with the Copilot MCP extension?`
  );
}

async function checkAlive(port) {
  // Quick health check — returns true if server responds, false otherwise
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 2000);
  try {
    const res = await fetch(`http://127.0.0.1:${port}/health`, { signal: controller.signal });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timeout);
  }
}

async function mcpRequest(path, options = {}) {
  const { port, token } = getConnection();
  const baseUrl = `http://127.0.0.1:${port}`;

  // Defensive health check — detects stale connection file from a crashed extension
  // Only ping /health for fast ops; skip for the model list and long-running endpoints
  // where the request itself will surface connection errors anyway.
  // We run the health check once per request; overhead is ~1ms on localhost.
  const alive = await checkAlive(port);
  if (!alive) {
    throw new Error(
      `Copilot MCP extension not reachable on port ${port}. The connection file may be stale from a crashed VS Code session. Restart VS Code with the Copilot MCP extension.`
    );
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 300000);
  try {
    const headers = {
      ...options.headers,
      Authorization: `Bearer ${token}`,
    };
    const res = await fetch(`${baseUrl}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
    });
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`Copilot MCP server error ${res.status}: ${body}`);
    }
    return res.json();
  } finally {
    clearTimeout(timeout);
  }
}

const server = new McpServer({
  name: "copilot-mcp",
  version: "0.1.0",
});

server.tool(
  "copilot_chat",
  "Send a prompt to VS Code Copilot and get a response. Use this to offload tasks to Copilot instead of using Claude tokens. Good for: code generation, summarization, translation, mechanical transforms, simple Q&A.",
  {
    prompt: z.string().describe("The prompt to send"),
    context: z.string().optional().describe("Optional context to prepend (e.g. file contents)"),
    model: z.string().optional().describe("Model family to use (e.g. claude-opus-4.6, claude-sonnet-4.6, gpt-5.4). Defaults to claude-sonnet-4.6"),
  },
  async ({ prompt, context, model }) => {
    const messages = [];
    if (context) {
      messages.push({ role: "user", content: context });
      messages.push({ role: "assistant", content: "I've read the context. What would you like me to do?" });
    }
    messages.push({ role: "user", content: prompt });

    const result = await mcpRequest("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages,
        family: model || "claude-sonnet-4.6",
        vendor: "copilot",
      }),
    });

    return {
      content: [{ type: "text", text: result.content }],
    };
  }
);

server.tool(
  "copilot_agent",
  "Run an autonomous agent task using VS Code Copilot models. The agent has full workspace access: read/write files, search code, run commands. Use for complex tasks that need multiple steps. The agent runs inside VS Code with access to the same workspace.",
  {
    task: z.string().describe("The task to accomplish (be specific and detailed)"),
    model: z.string().optional().describe("Model family (e.g. claude-opus-4.6, gpt-5.4). Defaults to claude-sonnet-4.6"),
    sessionId: z.string().optional().describe("Session ID for persistent conversations. Omit for one-shot tasks."),
    maxIterations: z.number().optional().describe("Max agent loop iterations (default 100, safety net only)"),
  },
  async ({ task, model, sessionId, maxIterations }) => {
    const result = await mcpRequest("/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task,
        family: model || "claude-sonnet-4.6",
        vendor: "copilot",
        sessionId,
        maxIterations,
      }),
    });

    const summary = [
      result.result,
      "",
      `---`,
      `Model: ${result.model} | Iterations: ${result.iterations} | Tool calls: ${result.toolCalls.length}`,
    ];

    if (result.toolCalls.length > 0) {
      summary.push("Tools used: " + [...new Set(result.toolCalls.map((c) => c.tool))].join(", "));
    }

    return {
      content: [{ type: "text", text: summary.join("\n") }],
    };
  }
);

server.tool(
  "copilot_job_start",
  "Start a long-running agent task in the background. Returns a job ID immediately. IMPORTANT: After calling this tool, you MUST immediately run the bash watcher command included in the response using Bash with run_in_background:true. This ensures automatic notification when the job completes.",
  {
    task: z.string().describe("The task to accomplish (be specific and detailed)"),
    model: z.string().optional().describe("Model family (e.g. claude-opus-4.6, gpt-5.4). Defaults to claude-sonnet-4.6"),
    sessionId: z.string().optional().describe("Session ID for persistent conversations. Omit for one-shot tasks."),
    maxIterations: z.number().optional().describe("Max agent loop iterations (default 100, safety net only)"),
  },
  async ({ task, model, sessionId, maxIterations }) => {
    const result = await mcpRequest("/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task,
        family: model || "claude-sonnet-4.6",
        vendor: "copilot",
        sessionId,
        maxIterations,
      }),
    });

    const scriptDir = new URL('.', import.meta.url).pathname;
    const watchScript = join(scriptDir, 'watch-job.sh');

    return {
      content: [{ type: "text", text: `Job started: ${result.jobId}\n\nNow run this with Bash(run_in_background: true):\nbash ${watchScript} ${result.jobId}` }],
    };
  }
);

server.tool(
  "copilot_job_status",
  "Check the status of a background agent job and retrieve results when done.",
  {
    jobId: z.string().describe("The job ID returned by copilot_job_start"),
  },
  async ({ jobId }) => {
    const job = await mcpRequest(`/jobs/${encodeURIComponent(jobId)}`);

    if (job.status === "running") {
      const elapsed = Math.round(job.elapsed / 1000);
      return {
        content: [{ type: "text", text: `Job ${jobId}: still running (${elapsed}s elapsed)` }],
      };
    }

    if (job.status === "failed") {
      return {
        content: [{ type: "text", text: `Job ${jobId}: FAILED — ${job.error}` }],
      };
    }

    if (job.status === "cancelled") {
      return {
        content: [{ type: "text", text: `Job ${jobId}: CANCELLED — ${job.error ?? 'cancelled by user'}` }],
      };
    }

    // Done
    const r = job.result;
    if (!r) {
      return {
        content: [{ type: "text", text: `Job ${jobId}: status=${job.status} but no result available` }],
      };
    }
    const summary = [
      r.result,
      "",
      "---",
      `Model: ${r.model} | Iterations: ${r.iterations} | Tool calls: ${r.toolCalls.length} | Elapsed: ${Math.round(job.elapsed / 1000)}s`,
    ];

    if (r.toolCalls.length > 0) {
      summary.push("Tools used: " + [...new Set(r.toolCalls.map((c) => c.tool))].join(", "));
    }

    return {
      content: [{ type: "text", text: summary.join("\n") }],
    };
  }
);

server.tool(
  "copilot_jobs",
  "List, cancel, or delete background jobs. Cancel stops a running job and prevents further LLM calls / tool execution. Delete removes the job record.",
  {
    action: z.enum(["list", "cancel", "delete"]).describe("Action to perform"),
    jobId: z.string().optional().describe("Job ID (required for cancel/delete)"),
  },
  async ({ action, jobId }) => {
    if (action === "list") {
      const result = await mcpRequest("/jobs");
      if (result.jobs.length === 0) {
        return { content: [{ type: "text", text: "No jobs." }] };
      }
      const lines = result.jobs.map((j) => {
        const elapsed = j.finishedAt ? `${Math.round((j.finishedAt - j.startedAt) / 1000)}s` : "running";
        return `${j.id} [${j.status}] ${elapsed} — ${j.task}`;
      });
      return { content: [{ type: "text", text: lines.join("\n") }] };
    }

    if (action === "cancel") {
      if (!jobId) {
        return { content: [{ type: "text", text: "jobId required for cancel" }] };
      }
      const result = await mcpRequest(`/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" });
      return { content: [{ type: "text", text: result.cancelled ? `Cancelled job: ${jobId}` : `Job not found or not running: ${jobId}` }] };
    }

    if (action === "delete") {
      if (!jobId) {
        return { content: [{ type: "text", text: "jobId required for delete" }] };
      }
      const result = await mcpRequest(`/jobs/${encodeURIComponent(jobId)}`, { method: "DELETE" });
      return { content: [{ type: "text", text: result.deleted ? `Deleted job: ${jobId}` : `Job not found: ${jobId}` }] };
    }

    return { content: [{ type: "text", text: "Unknown action" }] };
  }
);

server.tool(
  "copilot_sessions",
  "List, view, or delete Copilot agent sessions. Sessions are auto-saved to .vscode/copilot-mcp-sessions/ and persist across VS Code restarts.",
  {
    action: z.enum(["list", "view", "delete"]).describe("Action to perform"),
    sessionId: z.string().optional().describe("Session ID (required for view/delete)"),
  },
  async ({ action, sessionId }) => {
    if (action === "list") {
      const result = await mcpRequest("/sessions");
      const sessions = result.sessions;
      if (sessions.length === 0) {
        return { content: [{ type: "text", text: "No sessions." }] };
      }
      const lines = sessions.map((s) => {
        const age = Math.round((Date.now() - s.updatedAt) / 1000 / 60);
        const ageStr = age < 60 ? `${age}m` : age < 1440 ? `${Math.round(age / 60)}h` : `${Math.round(age / 1440)}d`;
        const preview = s.task.slice(0, 80);
        return `${s.id}\n  ${ageStr} ago | ${s.turns} turns | ${preview}`;
      });
      return { content: [{ type: "text", text: lines.join("\n\n") }] };
    }

    if (action === "view") {
      if (!sessionId) {
        return { content: [{ type: "text", text: "sessionId required for view" }] };
      }
      const session = await mcpRequest(`/sessions/${encodeURIComponent(sessionId)}`);
      const summary = [
        `Session: ${session.id}`,
        `Task: ${session.task}`,
        `Created: ${new Date(session.createdAt).toISOString()}`,
        `Updated: ${new Date(session.updatedAt).toISOString()}`,
        `Turns: ${session.turns}`,
        `Messages: ${session.messages.length}`,
      ];
      return { content: [{ type: "text", text: summary.join("\n") }] };
    }

    if (action === "delete") {
      if (!sessionId) {
        return { content: [{ type: "text", text: "sessionId required for delete" }] };
      }
      const result = await mcpRequest(`/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
      return { content: [{ type: "text", text: result.deleted ? `Deleted session: ${sessionId}` : `Session not found: ${sessionId}` }] };
    }

    return { content: [{ type: "text", text: "Unknown action" }] };
  }
);

server.tool(
  "copilot_models",
  "List available models from VS Code Copilot with capabilities",
  {},
  async () => {
    const models = await mcpRequest("/models");
    const copilotModels = models
      .filter((m) => m.vendor === "copilot")
      .map((m) => {
        const caps = [];
        if (m.supportsTools) caps.push("tools");
        if (m.supportsImages) caps.push("images");
        const capStr = caps.length ? ` [${caps.join(",")}]` : "";
        return `${m.family} (max ${m.maxInputTokens} tokens)${capStr}`;
      })
      .join("\n");

    return {
      content: [{ type: "text", text: copilotModels }],
    };
  }
);

const transport = new StdioServerTransport();
await server.connect(transport);
