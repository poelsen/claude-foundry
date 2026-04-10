import * as vscode from 'vscode';
import { toolDefinitions, executeTool } from './tools';
import { truncate } from './pure';
import { log } from './logger';
import {
  generateSessionId,
  loadSession,
  saveSession,
  messagesToStored,
  storedToMessages,
  type SessionData,
} from './sessions';

export interface AgentRequest {
  task: string;
  family?: string;
  vendor?: string;
  maxIterations?: number;
  sessionId?: string;
}

export interface AgentResponse {
  result: string;
  model: string;
  iterations: number;
  toolCalls: Array<{ tool: string; args: Record<string, unknown>; result: string }>;
  sessionId: string;
}

const SYSTEM_PROMPT = `You are an autonomous coding agent working inside VS Code with full workspace access. Use the provided tools to accomplish the task. Read files, search, edit, run commands, and use language server features as needed. When done, provide your final answer.

If the workspace has multiple root folders, call listWorkspaceRoots first to discover available roots, then pass the root name to file tools via the root parameter.`;

function toLmTools(): vscode.LanguageModelChatTool[] {
  return toolDefinitions.map(def => ({
    name: def.name,
    description: def.description,
    inputSchema: def.inputSchema,
  }));
}

class CancellationError extends Error {
  constructor() { super('Cancelled'); this.name = 'CancellationError'; }
}

function checkCancelled(token?: vscode.CancellationToken): void {
  if (token?.isCancellationRequested) { throw new CancellationError(); }
}

// Per-session lock to serialize concurrent runAgent calls against the same
// sessionId. Without this, two parallel jobs both load → append → save,
// and the last save wins — silently dropping the other run's transcript.
const sessionLocks = new Map<string, Promise<unknown>>();

async function withSessionLock<T>(sessionId: string, fn: () => Promise<T>): Promise<T> {
  const prev = sessionLocks.get(sessionId) ?? Promise.resolve();
  const next = prev.then(fn, fn);
  sessionLocks.set(sessionId, next);
  try {
    return await next;
  } finally {
    if (sessionLocks.get(sessionId) === next) {
      sessionLocks.delete(sessionId);
    }
  }
}

export async function runAgent(req: AgentRequest, externalToken?: vscode.CancellationToken): Promise<AgentResponse> {
  // Resolve session ID first (same logic as runAgentInner) so we can lock on it.
  // Auto-generated IDs include seconds + slug so concurrent identical tasks
  // would collide on the same second; we want them to serialize.
  const sessionId = req.sessionId ?? generateSessionId(req.task);
  const lockedReq = { ...req, sessionId };
  return withSessionLock(sessionId, () => runAgentInner(lockedReq, externalToken));
}

async function runAgentInner(req: AgentRequest, externalToken?: vscode.CancellationToken): Promise<AgentResponse> {
  const selector: vscode.LanguageModelChatSelector = {};
  if (req.family) { selector.family = req.family; }
  (selector as any).vendor = req.vendor ?? 'copilot';

  const models = await vscode.lm.selectChatModels(selector);
  if (models.length === 0) {
    throw new Error('No matching model found');
  }
  const model = models[0];

  // Validate and clamp maxIterations. Accept finite positive integers only.
  // Upper bound of 1000 is a hard safety cap — long jobs should still run for
  // hours, but 1000 iterations with our tool loop is deeply unusual.
  const rawMaxIter = req.maxIterations;
  let maxIter = 100;
  if (rawMaxIter !== undefined) {
    if (typeof rawMaxIter !== 'number' || !Number.isFinite(rawMaxIter) || !Number.isInteger(rawMaxIter) || rawMaxIter < 1) {
      throw new Error(`maxIterations must be a positive integer (got ${rawMaxIter})`);
    }
    maxIter = Math.min(rawMaxIter, 1000);
  }

  const tools = toLmTools();

  // sessionId is guaranteed set by runAgent (outer wrapper)
  const sessionId = req.sessionId!;
  const existing = await loadSession(sessionId);

  let messages: vscode.LanguageModelChatMessage[];
  let sessionData: SessionData;
  const now = Date.now();

  if (existing) {
    messages = storedToMessages(existing.messages);
    messages.push(vscode.LanguageModelChatMessage.User(req.task));
    sessionData = { ...existing, updatedAt: now, turns: existing.turns + 1 };
  } else {
    messages = [
      vscode.LanguageModelChatMessage.User(SYSTEM_PROMPT),
      vscode.LanguageModelChatMessage.User(req.task),
    ];
    sessionData = {
      id: sessionId,
      task: req.task,
      createdAt: now,
      updatedAt: now,
      turns: 1,
      messages: [],
    };
  }

  const allToolCalls: AgentResponse['toolCalls'] = [];
  let iterations = 0;
  let finalText = '';
  let cancelled = false;

  // Fallback cancellation source for the sync path — created once, disposed
  // in finally. Avoids leaking one CancellationTokenSource per iteration.
  const fallbackSource = externalToken ? undefined : new vscode.CancellationTokenSource();
  const requestToken = externalToken ?? fallbackSource!.token;

  try {
  for (let i = 0; i < maxIter; i++) {
    iterations++;
    checkCancelled(externalToken);
    await new Promise(resolve => setImmediate(resolve));
    log.info(`Agent iteration ${iterations}, ${messages.length} messages`);

    const response = await model.sendRequest(
      messages,
      {
        tools,
        toolMode: vscode.LanguageModelChatToolMode.Auto,
      },
      requestToken,
    );

    // Collect text and tool calls from the stream
    const textParts: string[] = [];
    const toolCallParts: vscode.LanguageModelToolCallPart[] = [];

    for await (const part of response.stream) {
      checkCancelled(externalToken);
      if (part instanceof vscode.LanguageModelTextPart) {
        textParts.push(part.value);
      } else if (part instanceof vscode.LanguageModelToolCallPart) {
        toolCallParts.push(part);
      }
      // Yield periodically
      if ((textParts.length + toolCallParts.length) % 10 === 0) {
        await new Promise(resolve => setImmediate(resolve));
      }
    }

    const text = textParts.join('');

    if (toolCallParts.length === 0) {
      // No tool calls — agent is done
      finalText = text;
      messages.push(vscode.LanguageModelChatMessage.Assistant(text));
      break;
    }

    // Record the assistant turn (text + tool call parts)
    const assistantParts: (vscode.LanguageModelTextPart | vscode.LanguageModelToolCallPart)[] = [];
    if (text) { assistantParts.push(new vscode.LanguageModelTextPart(text)); }
    assistantParts.push(...toolCallParts);
    messages.push(vscode.LanguageModelChatMessage.Assistant(assistantParts));

    // Execute each tool call
    const resultParts: vscode.LanguageModelToolResultPart[] = [];
    for (const call of toolCallParts) {
      checkCancelled(externalToken);
      await new Promise(resolve => setImmediate(resolve));
      const argsPreview = JSON.stringify(call.input).slice(0, 100);
      log.info(`Tool call: ${call.name}(${argsPreview})`);

      let result;
      try {
        result = await executeTool(call.name, call.input as Record<string, unknown>);
      } catch (err) {
        result = { content: `Error: ${err instanceof Error ? err.message : String(err)}`, isError: true };
      }

      // Strip absolute workspace paths from tool results before feeding back
      // to the LLM — reduces leakage of local filesystem structure.
      const roots = vscode.workspace.workspaceFolders ?? [];
      let sanitized = result.content;
      for (const folder of roots) {
        const abs = folder.uri.fsPath;
        // Escape regex metachars in path
        const escaped = abs.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        sanitized = sanitized.replace(new RegExp(escaped, 'g'), '<workspace>');
      }
      const truncated = truncate(sanitized, 15000);

      allToolCalls.push({
        tool: call.name,
        args: call.input as Record<string, unknown>,
        result: truncated,
      });

      resultParts.push(new vscode.LanguageModelToolResultPart(
        call.callId,
        [new vscode.LanguageModelTextPart(truncated)],
      ));
    }

    // All tool results go in one User message
    messages.push(vscode.LanguageModelChatMessage.User(resultParts));
  }
  } catch (err) {
    if (err instanceof CancellationError) {
      cancelled = true;
      finalText = '[Agent cancelled]';
    } else {
      // Save partial session before re-throwing
      sessionData.messages = messagesToStored(messages);
      sessionData.updatedAt = Date.now();
      try { await saveSession(sessionData); } catch { /* best effort */ }
      fallbackSource?.dispose();
      throw err;
    }
  } finally {
    fallbackSource?.dispose();
  }

  // Save session (normal completion OR cancellation)
  sessionData.messages = messagesToStored(messages);
  sessionData.updatedAt = Date.now();
  await saveSession(sessionData);

  if (cancelled) {
    throw new CancellationError();
  }

  return {
    result: finalText || '[Agent reached max iterations without completing]',
    model: model.id,
    iterations,
    toolCalls: allToolCalls,
    sessionId,
  };
}
