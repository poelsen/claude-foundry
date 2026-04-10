import * as vscode from 'vscode';

type Level = 'debug' | 'info' | 'warn' | 'error';

let channel: vscode.OutputChannel | undefined;

export function initLogger(): vscode.OutputChannel {
  if (!channel) {
    channel = vscode.window.createOutputChannel('Copilot MCP');
  }
  return channel;
}

export function disposeLogger(): void {
  channel?.dispose();
  channel = undefined;
}

function emit(level: Level, message: string): void {
  const ts = new Date().toISOString();
  const line = `[${ts}] [${level.toUpperCase()}] ${message}`;
  // Always write to VS Code output channel if initialized
  if (channel) {
    channel.appendLine(line);
  }
  // Also write to console so it still shows up in the Extension Host log
  // (useful when running in dev mode)
  if (level === 'error') {
    console.error(line);
  } else if (level === 'warn') {
    console.warn(line);
  } else {
    console.log(line);
  }
}

export const log = {
  debug: (msg: string) => emit('debug', msg),
  info: (msg: string) => emit('info', msg),
  warn: (msg: string) => emit('warn', msg),
  error: (msg: string) => emit('error', msg),
};
