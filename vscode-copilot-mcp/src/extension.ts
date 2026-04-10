import * as vscode from 'vscode';
import * as fsp from 'node:fs/promises';
import * as path from 'node:path';
import { Server } from './server';
import { initLogger, disposeLogger, log } from './logger';

let server: Server | undefined;
let connectionFile: string | undefined;

function getVscodeDir(): string | undefined {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders?.length) { return undefined; }
  return path.join(folders[0].uri.fsPath, '.vscode');
}

function getConnectionFile(): string | undefined {
  const dir = getVscodeDir();
  if (!dir) { return undefined; }
  return path.join(dir, 'copilot-mcp.json');
}

async function writeConnectionFile(port: number, token: string): Promise<void> {
  const filePath = getConnectionFile();
  if (!filePath) { return; }

  const dir = path.dirname(filePath);
  await fsp.mkdir(dir, { recursive: true });
  // `mode` in writeFile only applies on CREATE, not overwrite — an existing
  // file with permissive mode stays permissive. Delete first to force mode on
  // fresh creation. Best-effort; errors are ignored if the file doesn't exist.
  try { await fsp.unlink(filePath); } catch { /* didn't exist */ }
  await fsp.writeFile(filePath, JSON.stringify({ port, token }, null, 2), { mode: 0o600 });
  // Explicitly chmod to handle edge cases where the OS ignored the mode flag
  try { await fsp.chmod(filePath, 0o600); } catch { /* Windows/no-op */ }
  connectionFile = filePath;
}

async function removeConnectionFile(): Promise<void> {
  if (connectionFile) {
    try { await fsp.unlink(connectionFile); } catch { /* ignore */ }
    connectionFile = undefined;
  }
}

export async function activate(context: vscode.ExtensionContext) {
  const channel = initLogger();
  context.subscriptions.push(channel);
  log.info('Extension activating');

  const config = vscode.workspace.getConfiguration('copilot-mcp');

  context.subscriptions.push(
    vscode.commands.registerCommand('copilot-mcp.start', () => startServer(config)),
    vscode.commands.registerCommand('copilot-mcp.stop', () => stopServer()),
    vscode.commands.registerCommand('copilot-mcp.listModels', () => listModels()),
  );

  // Disabled by default. Users opt in per-workspace via .vscode/settings.json
  // ({ "copilot-mcp.autoStart": true }) so the server only runs in windows
  // where they actually want to use the bridge.
  if (config.get<boolean>('autoStart', false)) {
    await startServer(config);
  } else {
    log.info('autoStart=false — extension idle. Run "Copilot MCP: Start Server" or enable via .vscode/settings.json');
  }
}

async function startServer(config: vscode.WorkspaceConfiguration) {
  if (server) {
    vscode.window.showInformationMessage('Copilot MCP: Server already running');
    return;
  }

  // Use port 0 to auto-assign a free port, or configured port
  const configPort = config.get<number>('port', 0);
  const candidate = new Server(configPort);

  try {
    const actualPort = await candidate.start();
    // Only commit server to module state after successful start
    server = candidate;
    await writeConnectionFile(actualPort, candidate.getToken());
    log.info(`Server started on port ${actualPort}`);
    vscode.window.showInformationMessage(`Copilot MCP: Server running on port ${actualPort}`);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    log.error(`Server start failed: ${msg}`);
    vscode.window.showErrorMessage(`Copilot MCP: Failed to start server — ${msg}`);
    throw err;
  }
}

async function stopServer() {
  if (!server) {
    vscode.window.showInformationMessage('Copilot MCP: Server not running');
    return;
  }
  await server.stop();
  server = undefined;
  await removeConnectionFile();
  log.info('Server stopped');
  vscode.window.showInformationMessage('Copilot MCP: Server stopped');
}

async function listModels() {
  const models = await vscode.lm.selectChatModels();
  if (models.length === 0) {
    vscode.window.showWarningMessage('No language models available. Is Copilot active?');
    return;
  }
  const items = models.map(m => `${m.id} (${m.vendor}/${m.family}, max ${m.maxInputTokens} tokens)`);
  const picked = await vscode.window.showQuickPick(items, { title: 'Available Models' });
  if (picked) {
    await vscode.env.clipboard.writeText(models[items.indexOf(picked)].id);
    vscode.window.showInformationMessage('Model ID copied to clipboard');
  }
}

export async function deactivate(): Promise<void> {
  log.info('Extension deactivating');
  if (server) {
    await server.stop();
    server = undefined;
  }
  await removeConnectionFile();
  disposeLogger();
}
