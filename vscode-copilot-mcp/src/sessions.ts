import * as vscode from 'vscode';
import * as fsp from 'node:fs/promises';
import * as path from 'node:path';
import { generateSessionId, isValidSessionId } from './pure';

export { generateSessionId };

export type StoredPart =
  | { type: 'text'; value: string }
  | { type: 'tool_call'; callId: string; name: string; input: Record<string, unknown> }
  | { type: 'tool_result'; callId: string; content: string };

export interface StoredMessage {
  role: 'user' | 'assistant';
  parts: StoredPart[];
}

export interface SessionData {
  id: string;
  task: string;
  createdAt: number;
  updatedAt: number;
  turns: number;
  messages: StoredMessage[];
}

function getSessionsDir(): string | undefined {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders?.length) { return undefined; }
  return path.join(folders[0].uri.fsPath, '.vscode', 'copilot-mcp-sessions');
}

async function ensureSessionsDir(): Promise<string> {
  const dir = getSessionsDir();
  if (!dir) { throw new Error('No workspace folder open'); }
  await fsp.mkdir(dir, { recursive: true, mode: 0o700 });
  return dir;
}

async function sessionPath(id: string): Promise<string> {
  const dir = await ensureSessionsDir();
  if (!isValidSessionId(id)) {
    throw new Error(`Invalid session ID: ${id}`);
  }
  return path.join(dir, `${id}.json`);
}

function isValidStoredPart(p: unknown): p is StoredPart {
  if (typeof p !== 'object' || p === null) { return false; }
  const obj = p as Record<string, unknown>;
  if (obj.type === 'text') { return typeof obj.value === 'string'; }
  if (obj.type === 'tool_call') {
    return typeof obj.callId === 'string' && typeof obj.name === 'string' && typeof obj.input === 'object' && obj.input !== null;
  }
  if (obj.type === 'tool_result') {
    return typeof obj.callId === 'string' && typeof obj.content === 'string';
  }
  return false;
}

function isValidSessionData(data: unknown): data is SessionData {
  if (typeof data !== 'object' || data === null) { return false; }
  const s = data as Record<string, unknown>;
  if (typeof s.id !== 'string') { return false; }
  if (typeof s.task !== 'string') { return false; }
  if (typeof s.createdAt !== 'number' || !Number.isFinite(s.createdAt)) { return false; }
  if (typeof s.updatedAt !== 'number' || !Number.isFinite(s.updatedAt)) { return false; }
  if (typeof s.turns !== 'number' || !Number.isInteger(s.turns) || s.turns < 0) { return false; }
  if (!Array.isArray(s.messages)) { return false; }
  for (const msg of s.messages) {
    if (typeof msg !== 'object' || msg === null) { return false; }
    const m = msg as Record<string, unknown>;
    if (m.role !== 'user' && m.role !== 'assistant') { return false; }
    if (!Array.isArray(m.parts)) { return false; }
    if (!m.parts.every(isValidStoredPart)) { return false; }
  }
  return true;
}

export async function loadSession(id: string): Promise<SessionData | undefined> {
  try {
    const data = await fsp.readFile(await sessionPath(id), 'utf-8');
    const parsed: unknown = JSON.parse(data);
    if (!isValidSessionData(parsed)) {
      return undefined;
    }
    return parsed;
  } catch {
    return undefined;
  }
}

export async function saveSession(session: SessionData): Promise<void> {
  const filePath = await sessionPath(session.id);
  // Atomic write: write to tmp in the same dir, then rename. Prevents
  // partial/corrupt files on crash and concurrent reads seeing half-written
  // JSON. Also re-asserts mode 0o600 since fsp.writeFile's mode only
  // applies on CREATE.
  const tmpPath = `${filePath}.${process.pid}.tmp`;
  await fsp.writeFile(tmpPath, JSON.stringify(session, null, 2), { mode: 0o600 });
  try { await fsp.chmod(tmpPath, 0o600); } catch { /* Windows no-op */ }
  await fsp.rename(tmpPath, filePath);
}

export async function deleteSession(id: string): Promise<boolean> {
  try {
    await fsp.unlink(await sessionPath(id));
    return true;
  } catch {
    return false;
  }
}

export async function listSessions(): Promise<Array<{ id: string; task: string; createdAt: number; updatedAt: number; turns: number }>> {
  const dir = getSessionsDir();
  if (!dir) { return []; }

  let files: string[];
  try {
    files = (await fsp.readdir(dir)).filter(f => f.endsWith('.json'));
  } catch {
    return []; // dir doesn't exist yet
  }

  const sessions = await Promise.all(files.map(async (f) => {
    try {
      const raw = await fsp.readFile(path.join(dir, f), 'utf-8');
      const parsed: unknown = JSON.parse(raw);
      if (!isValidSessionData(parsed)) { return null; }
      return {
        id: parsed.id,
        task: parsed.task,
        createdAt: parsed.createdAt,
        updatedAt: parsed.updatedAt,
        turns: parsed.turns,
      };
    } catch {
      return null;
    }
  }));

  // Sort by updatedAt descending (most recent first)
  return sessions
    .filter((s): s is NonNullable<typeof s> => s !== null)
    .sort((a, b) => b.updatedAt - a.updatedAt);
}

function contentToStoredParts(content: unknown): StoredPart[] {
  if (typeof content === 'string') {
    return [{ type: 'text', value: content }];
  }
  if (!Array.isArray(content)) { return []; }

  return content.map((p): StoredPart | null => {
    if (p instanceof vscode.LanguageModelTextPart) {
      return { type: 'text', value: p.value };
    }
    if (p instanceof vscode.LanguageModelToolCallPart) {
      return { type: 'tool_call', callId: p.callId, name: p.name, input: p.input as Record<string, unknown> };
    }
    if (p instanceof vscode.LanguageModelToolResultPart) {
      const text = p.content.map(c => c instanceof vscode.LanguageModelTextPart ? c.value : '').join('');
      return { type: 'tool_result', callId: p.callId, content: text };
    }
    return null;
  }).filter((p): p is StoredPart => p !== null);
}

export function messagesToStored(messages: vscode.LanguageModelChatMessage[]): StoredMessage[] {
  return messages.map(m => ({
    role: m.role === vscode.LanguageModelChatMessageRole.User ? 'user' : 'assistant',
    parts: contentToStoredParts((m as any).content),
  }));
}

function storedPartsToContent(
  parts: StoredPart[],
): string | (vscode.LanguageModelTextPart | vscode.LanguageModelToolCallPart | vscode.LanguageModelToolResultPart)[] {
  if (parts.length === 1 && parts[0].type === 'text') {
    return parts[0].value;
  }
  return parts.map(p => {
    if (p.type === 'text') {
      return new vscode.LanguageModelTextPart(p.value);
    }
    if (p.type === 'tool_call') {
      return new vscode.LanguageModelToolCallPart(p.callId, p.name, p.input);
    }
    return new vscode.LanguageModelToolResultPart(p.callId, [new vscode.LanguageModelTextPart(p.content)]);
  });
}

export function storedToMessages(stored: StoredMessage[]): vscode.LanguageModelChatMessage[] {
  return stored.map(m => {
    const content = storedPartsToContent(m.parts);
    return m.role === 'user'
      ? vscode.LanguageModelChatMessage.User(content as any)
      : vscode.LanguageModelChatMessage.Assistant(content as any);
  });
}
