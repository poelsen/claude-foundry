import * as vscode from 'vscode';
import * as cp from 'node:child_process';
import * as nodePath from 'node:path';
import * as dns from 'node:dns/promises';
import {
  matchDestructivePattern,
  isPathSafe,
  truncate,
  isBlockedHost,
  ValidationError,
  reqString,
  optString,
  reqInt,
  optInt,
  optBool,
  optEnum,
} from './pure';

export interface ToolDefinition {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

export interface ToolResult {
  content: string;
  isError?: boolean;
}

const ROOT_PARAM = { type: 'string', description: 'Workspace root name (only needed in multi-root workspaces). Call listWorkspaceRoots to see available roots. Defaults to the first root.' };

export const toolDefinitions: ToolDefinition[] = [
  {
    name: 'listWorkspaceRoots',
    description: 'List all workspace root folders. Use this first in multi-root workspaces to discover available roots before calling file tools.',
    inputSchema: { type: 'object', properties: {} },
  },
  {
    name: 'readFile',
    description: 'Read the contents of a file in the workspace. Returns the full text content.',
    inputSchema: {
      type: 'object',
      properties: {
        path: { type: 'string', description: 'Relative path from workspace root' },
        root: ROOT_PARAM,
      },
      required: ['path'],
    },
  },
  {
    name: 'listFiles',
    description: 'Find files matching a glob pattern in the workspace. Returns matching file paths.',
    inputSchema: {
      type: 'object',
      properties: {
        pattern: { type: 'string', description: 'Glob pattern (e.g. "**/*.ts", "src/**/*.py")' },
        maxResults: { type: 'number', description: 'Max results to return (default 50)' },
        root: ROOT_PARAM,
      },
      required: ['pattern'],
    },
  },
  {
    name: 'searchText',
    description: 'Search for text/regex across workspace files. Returns matching lines with file paths and line numbers.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Search string or regex pattern' },
        glob: { type: 'string', description: 'Optional glob to filter files (e.g. "*.ts")' },
        maxResults: { type: 'number', description: 'Max results (default 50)' },
        root: ROOT_PARAM,
      },
      required: ['query'],
    },
  },
  {
    name: 'editFile',
    description: 'Replace exact text in a file. The old_text must match exactly and be unique unless replace_all is true. For new files, use old_text="" and new_text with the full content.',
    inputSchema: {
      type: 'object',
      properties: {
        path: { type: 'string', description: 'Relative path from workspace root' },
        old_text: { type: 'string', description: 'Exact text to find and replace (empty string for new files)' },
        new_text: { type: 'string', description: 'Replacement text' },
        replace_all: { type: 'boolean', description: 'Replace all occurrences (default: false, fails if old_text is not unique)' },
        root: ROOT_PARAM,
      },
      required: ['path', 'old_text', 'new_text'],
    },
  },
  {
    name: 'runCommand',
    description: 'Execute a shell command in the workspace root. Returns stdout and stderr. Use for build, test, git, etc.',
    inputSchema: {
      type: 'object',
      properties: {
        command: { type: 'string', description: 'Shell command to execute' },
        timeout: { type: 'number', description: 'Timeout in ms (default 30000)' },
        root: ROOT_PARAM,
      },
      required: ['command'],
    },
  },
  {
    name: 'getDiagnostics',
    description: 'Get language server diagnostics (errors, warnings) for a file or the entire workspace. Shows TypeScript/Python/etc compiler and linter errors without running a build.',
    inputSchema: {
      type: 'object',
      properties: {
        path: { type: 'string', description: 'Optional file path. If omitted, returns diagnostics for all open/indexed files.' },
        severity: { type: 'string', enum: ['error', 'warning', 'info', 'hint'], description: 'Minimum severity (default: error)' },
        root: ROOT_PARAM,
      },
    },
  },
  {
    name: 'getSymbols',
    description: 'Get the symbol outline (classes, functions, methods) of a file from the language server.',
    inputSchema: {
      type: 'object',
      properties: {
        path: { type: 'string', description: 'Relative path to the file' },
        root: ROOT_PARAM,
      },
      required: ['path'],
    },
  },
  {
    name: 'getDefinition',
    description: 'Jump to the definition of a symbol at a given position in a file.',
    inputSchema: {
      type: 'object',
      properties: {
        path: { type: 'string', description: 'Relative path to the file' },
        line: { type: 'number', description: '1-based line number' },
        character: { type: 'number', description: '0-based character position in the line' },
        root: ROOT_PARAM,
      },
      required: ['path', 'line', 'character'],
    },
  },
  {
    name: 'getHover',
    description: 'Get hover info (type, docs) for a symbol at a position in a file.',
    inputSchema: {
      type: 'object',
      properties: {
        path: { type: 'string', description: 'Relative path to the file' },
        line: { type: 'number', description: '1-based line number' },
        character: { type: 'number', description: '0-based character position in the line' },
        root: ROOT_PARAM,
      },
      required: ['path', 'line', 'character'],
    },
  },
  {
    name: 'webFetch',
    description: 'Fetch content from a URL. Returns the response body (HTML, JSON, text). Use to look up documentation, API specs, or external references.',
    inputSchema: {
      type: 'object',
      properties: {
        url: { type: 'string', description: 'URL to fetch (http or https)' },
        timeout: { type: 'number', description: 'Timeout in ms (default 15000)' },
      },
      required: ['url'],
    },
  },
];

function getWorkspaceFolder(rootName?: string): vscode.WorkspaceFolder {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders?.length) { throw new Error('No workspace folder open'); }

  if (!rootName) { return folders[0]; }

  const match = folders.find(f => f.name === rootName);
  if (!match) {
    const available = folders.map(f => f.name).join(', ');
    throw new Error(`Workspace root "${rootName}" not found. Available: ${available}`);
  }
  return match;
}

function getWorkspaceRoot(rootName?: string): string {
  return getWorkspaceFolder(rootName).uri.fsPath;
}

function resolveUri(relativePath: string, rootName?: string): vscode.Uri {
  const root = nodePath.resolve(getWorkspaceRoot(rootName));
  const resolved = nodePath.resolve(root, relativePath);
  if (!isPathSafe(resolved, root, nodePath.sep)) {
    throw new Error(`Path traversal denied: ${relativePath}`);
  }
  return vscode.Uri.file(resolved);
}

async function listWorkspaceRoots(): Promise<ToolResult> {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders?.length) { return { content: 'No workspace folder open.' }; }
  const lines = folders.map((f, i) => `${i === 0 ? '* ' : '  '}${f.name} (${f.uri.fsPath})`);
  return { content: `${folders.length} root(s):\n${lines.join('\n')}\n\n* = default when root parameter is omitted.` };
}

const MAX_READ_BYTES = 5 * 1024 * 1024; // 5MB

async function readFile(args: { path: string; root?: string }): Promise<ToolResult> {
  const uri = resolveUri(args.path, args.root);

  // Check file size first to avoid OOM on huge files (e.g., binaries, logs).
  try {
    const stat = await vscode.workspace.fs.stat(uri);
    if (stat.size > MAX_READ_BYTES) {
      return {
        content: `Error: ${args.path} is ${Math.round(stat.size / 1024)}KB, exceeds readFile limit of ${MAX_READ_BYTES / 1024 / 1024}MB. Use listFiles + searchText for large files.`,
        isError: true,
      };
    }
  } catch {
    // If stat fails, fall through — readFile will produce a better error
  }

  const bytes = await vscode.workspace.fs.readFile(uri);
  return { content: Buffer.from(bytes).toString('utf-8') };
}

async function listFiles(args: { pattern: string; maxResults?: number; root?: string }): Promise<ToolResult> {
  const folder = getWorkspaceFolder(args.root);
  const relativePattern = new vscode.RelativePattern(folder, args.pattern);
  const uris = await vscode.workspace.findFiles(relativePattern, undefined, args.maxResults ?? 50);
  const rootPath = folder.uri.fsPath;
  const paths = uris.map(u => u.fsPath.replace(rootPath + nodePath.sep, ''));
  return { content: paths.join('\n') || 'No files found.' };
}

function getRipgrepPath(): string {
  // VS Code bundles ripgrep at a known path relative to appRoot
  const appRoot = vscode.env.appRoot;
  const rgName = process.platform === 'win32' ? 'rg.exe' : 'rg';
  return nodePath.join(appRoot, 'node_modules', '@vscode', 'ripgrep', 'bin', rgName);
}

async function searchText(args: { query: string; glob?: string; maxResults?: number; root?: string }): Promise<ToolResult> {
  const root = getWorkspaceRoot(args.root);
  const max = args.maxResults ?? 50;
  const rgArgs = ['--line-number', '--max-count', String(max), '--no-heading', '--color=never'];
  if (args.glob) { rgArgs.push('--glob', args.glob); }
  // `--` separator so a query starting with `-` isn't parsed as a flag
  rgArgs.push('--', args.query, '.');

  return new Promise((resolve) => {
    cp.execFile(getRipgrepPath(), rgArgs, { cwd: root, maxBuffer: 4 * 1024 * 1024 }, (err, stdout) => {
      // ripgrep exits with code 1 when no matches found — that's not an error
      if (err && (err as any).code !== 1 && (err as any).code !== 0) {
        resolve({ content: `Error: ${err.message}`, isError: true });
        return;
      }
      resolve({ content: stdout.trim() || 'No matches found.' });
    });
  });
}

// Per-file lock to serialize concurrent editFile calls against the same path.
// Without this, two parallel agent jobs both reading → editing → writing the
// same file would race and one edit would be lost.
const editLocks = new Map<string, Promise<unknown>>();

async function withFileLock<T>(key: string, fn: () => Promise<T>): Promise<T> {
  const prev = editLocks.get(key) ?? Promise.resolve();
  const next = prev.then(fn, fn); // run fn regardless of prior outcome
  editLocks.set(key, next);
  try {
    return await next;
  } finally {
    // Only clear if this is still the tail of the chain
    if (editLocks.get(key) === next) {
      editLocks.delete(key);
    }
  }
}

async function editFile(args: { path: string; old_text: string; new_text: string; replace_all?: boolean; root?: string }): Promise<ToolResult> {
  const uri = resolveUri(args.path, args.root);
  return withFileLock(uri.fsPath, () => editFileInner(uri, args));
}

async function editFileInner(uri: vscode.Uri, args: { path: string; old_text: string; new_text: string; replace_all?: boolean }): Promise<ToolResult> {
  if (args.old_text === '') {
    // Empty old_text = create new file. Refuse to silently overwrite an
    // existing file — the agent must pass actual old_text to modify.
    try {
      await vscode.workspace.fs.stat(uri);
      return {
        content: `Error: ${args.path} already exists. Use non-empty old_text to modify it, or delete it first.`,
        isError: true,
      };
    } catch {
      // stat failed = file doesn't exist, proceed with creation
    }
    await vscode.workspace.fs.writeFile(uri, Buffer.from(args.new_text, 'utf-8'));
    return { content: `Created ${args.path}` };
  }

  const bytes = await vscode.workspace.fs.readFile(uri);
  const content = Buffer.from(bytes).toString('utf-8');

  if (!content.includes(args.old_text)) {
    return { content: `Error: old_text not found in ${args.path}`, isError: true };
  }

  if (args.replace_all) {
    const newContent = content.split(args.old_text).join(args.new_text);
    const count = content.split(args.old_text).length - 1;
    await vscode.workspace.fs.writeFile(uri, Buffer.from(newContent, 'utf-8'));
    return { content: `Updated ${args.path} (${count} replacements)` };
  }

  // Single replacement — fail if ambiguous
  const firstIdx = content.indexOf(args.old_text);
  const secondIdx = content.indexOf(args.old_text, firstIdx + 1);
  if (secondIdx !== -1) {
    const count = content.split(args.old_text).length - 1;
    return { content: `Error: old_text found ${count} times in ${args.path}. Provide more context to make it unique, or use replace_all: true.`, isError: true };
  }

  const newContent = content.replace(args.old_text, args.new_text);
  await vscode.workspace.fs.writeFile(uri, Buffer.from(newContent, 'utf-8'));
  return { content: `Updated ${args.path}` };
}

function isCommandBlocked(command: string): string | undefined {
  const config = vscode.workspace.getConfiguration('copilot-mcp');
  if (config.get<boolean>('allowUnsafeCommands', false)) { return undefined; }

  const match = matchDestructivePattern(command);
  if (match) {
    return `Blocked: command matches dangerous pattern ${match}. Set copilot-mcp.allowUnsafeCommands to override.`;
  }
  return undefined;
}

async function runCommand(args: { command: string; timeout?: number; root?: string }): Promise<ToolResult> {
  const blocked = isCommandBlocked(args.command);
  if (blocked) { return { content: blocked, isError: true }; }

  const root = getWorkspaceRoot(args.root);
  const timeout = args.timeout ?? 30000;

  return new Promise((resolve) => {
    cp.exec(args.command, { cwd: root, timeout, maxBuffer: 1024 * 1024 }, (err, stdout, stderr) => {
      const output = [stdout, stderr].filter(Boolean).join('\n---stderr---\n');
      if (err && !stdout && !stderr) {
        resolve({ content: `Error: ${err.message}`, isError: true });
      } else {
        resolve({ content: output || '(no output)', isError: !!err });
      }
    });
  });
}

const SEVERITY_NAMES: Record<number, string> = {
  [vscode.DiagnosticSeverity.Error]: 'error',
  [vscode.DiagnosticSeverity.Warning]: 'warning',
  [vscode.DiagnosticSeverity.Information]: 'info',
  [vscode.DiagnosticSeverity.Hint]: 'hint',
};

async function getDiagnostics(args: { path?: string; severity?: string; root?: string }): Promise<ToolResult> {
  const minSeverityMap: Record<string, number> = {
    error: vscode.DiagnosticSeverity.Error,
    warning: vscode.DiagnosticSeverity.Warning,
    info: vscode.DiagnosticSeverity.Information,
    hint: vscode.DiagnosticSeverity.Hint,
  };
  const minSev = minSeverityMap[args.severity ?? 'error'];

  let entries: Array<[vscode.Uri, readonly vscode.Diagnostic[]]>;
  if (args.path) {
    const uri = resolveUri(args.path, args.root);
    entries = [[uri, vscode.languages.getDiagnostics(uri)]];
  } else {
    entries = vscode.languages.getDiagnostics();
  }

  const lines: string[] = [];
  for (const [uri, diagnostics] of entries) {
    const rel = vscode.workspace.asRelativePath(uri);
    for (const d of diagnostics) {
      if (d.severity > minSev) { continue; }
      const sev = SEVERITY_NAMES[d.severity] ?? 'unknown';
      const line = d.range.start.line + 1;
      const col = d.range.start.character + 1;
      const source = d.source ? `[${d.source}]` : '';
      lines.push(`${rel}:${line}:${col} ${sev}${source}: ${d.message}`);
    }
  }

  return { content: lines.join('\n') || 'No diagnostics found.' };
}

async function getSymbols(args: { path: string; root?: string }): Promise<ToolResult> {
  const uri = resolveUri(args.path, args.root);
  const symbols = await vscode.commands.executeCommand<vscode.DocumentSymbol[]>(
    'vscode.executeDocumentSymbolProvider',
    uri,
  );

  if (!symbols || symbols.length === 0) {
    return { content: 'No symbols found (language server may not support this file type).' };
  }

  const formatSymbol = (s: vscode.DocumentSymbol, depth = 0): string[] => {
    const kindName = vscode.SymbolKind[s.kind];
    const line = s.range.start.line + 1;
    const prefix = '  '.repeat(depth);
    const out = [`${prefix}${kindName} ${s.name} (line ${line})`];
    for (const child of s.children ?? []) {
      out.push(...formatSymbol(child, depth + 1));
    }
    return out;
  };

  const lines: string[] = [];
  for (const sym of symbols) { lines.push(...formatSymbol(sym)); }
  return { content: lines.join('\n') };
}

async function getDefinition(args: { path: string; line: number; character: number; root?: string }): Promise<ToolResult> {
  const uri = resolveUri(args.path, args.root);
  const position = new vscode.Position(args.line - 1, args.character);
  const locations = await vscode.commands.executeCommand<vscode.Location[]>(
    'vscode.executeDefinitionProvider',
    uri,
    position,
  );

  if (!locations || locations.length === 0) {
    return { content: 'No definition found.' };
  }

  const lines = locations.map(loc => {
    const rel = vscode.workspace.asRelativePath(loc.uri);
    return `${rel}:${loc.range.start.line + 1}:${loc.range.start.character + 1}`;
  });
  return { content: lines.join('\n') };
}

async function getHover(args: { path: string; line: number; character: number; root?: string }): Promise<ToolResult> {
  const uri = resolveUri(args.path, args.root);
  const position = new vscode.Position(args.line - 1, args.character);
  const hovers = await vscode.commands.executeCommand<vscode.Hover[]>(
    'vscode.executeHoverProvider',
    uri,
    position,
  );

  if (!hovers || hovers.length === 0) {
    return { content: 'No hover info available.' };
  }

  const parts: string[] = [];
  for (const h of hovers) {
    for (const c of h.contents) {
      if (typeof c === 'string') {
        parts.push(c);
      } else if ('value' in c) {
        parts.push(c.value);
      }
    }
  }
  return { content: parts.join('\n\n') };
}

const MAX_WEBFETCH_BYTES = 5 * 1024 * 1024; // 5MB

// Resolve hostname to IPs and check each resolved address against the blocklist.
// This catches DNS rebinding attacks where evil.com → 127.0.0.1 via attacker DNS.
async function checkHostnameSafe(hostname: string): Promise<string | undefined> {
  // First check the hostname string itself
  const stringCheck = isBlockedHost(hostname);
  if (stringCheck) { return stringCheck; }

  // If it's a literal IP, the string check already covered it
  if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(hostname)) { return undefined; }
  if (hostname.startsWith('[') && hostname.endsWith(']')) { return undefined; }

  // Resolve DNS and check each resolved address
  try {
    const addresses = await dns.lookup(hostname, { all: true, verbatim: true });
    for (const addr of addresses) {
      const ipCheck = isBlockedHost(addr.family === 6 ? `[${addr.address}]` : addr.address);
      if (ipCheck) {
        return `hostname resolves to blocked IP (${addr.address}: ${ipCheck})`;
      }
    }
  } catch (err) {
    return `DNS resolution failed: ${err instanceof Error ? err.message : String(err)}`;
  }
  return undefined;
}

async function webFetch(args: { url: string; timeout?: number }): Promise<ToolResult> {
  let parsed: URL;
  try {
    parsed = new URL(args.url);
  } catch {
    return { content: 'Error: invalid URL', isError: true };
  }

  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    return { content: 'Error: URL must use http or https', isError: true };
  }

  // SSRF protection: reject private/loopback/metadata IPs (including after DNS resolution)
  const blocked = await checkHostnameSafe(parsed.hostname);
  if (blocked) {
    return {
      content: `Error: URL blocked (${blocked}). webFetch does not allow requests to private networks, loopback, or cloud metadata endpoints.`,
      isError: true,
    };
  }

  const controller = new AbortController();
  const timeoutHandle = setTimeout(() => controller.abort(), args.timeout ?? 15000);

  try {
    // Manually follow redirects and validate each hop against the SSRF blocklist.
    // Default fetch() behavior (`redirect: 'follow'`) would bypass isBlockedHost
    // after the first hop — e.g., https://evil.com/r → 302 → http://169.254.169.254/
    let currentUrl = args.url;
    let res: Response;
    let redirectCount = 0;
    const MAX_REDIRECTS = 5;

    while (true) {
      res = await fetch(currentUrl, { signal: controller.signal, redirect: 'manual' });

      // Handle redirect responses manually
      if (res.status >= 300 && res.status < 400 && res.headers.get('location')) {
        redirectCount++;
        if (redirectCount > MAX_REDIRECTS) {
          return { content: `Error: too many redirects (>${MAX_REDIRECTS})`, isError: true };
        }

        const location = res.headers.get('location')!;
        let nextUrl: URL;
        try {
          nextUrl = new URL(location, currentUrl);
        } catch {
          return { content: `Error: invalid redirect location: ${location}`, isError: true };
        }

        if (nextUrl.protocol !== 'http:' && nextUrl.protocol !== 'https:') {
          return { content: `Error: redirect to non-http(s) protocol blocked: ${nextUrl.protocol}`, isError: true };
        }

        const hopBlocked = await checkHostnameSafe(nextUrl.hostname);
        if (hopBlocked) {
          return {
            content: `Error: redirect target blocked (${hopBlocked}): ${nextUrl.hostname}. SSRF protection prevents redirect chains ending at private networks or cloud metadata endpoints.`,
            isError: true,
          };
        }

        currentUrl = nextUrl.toString();
        continue;
      }

      break; // non-redirect response
    }

    // Stream response with a byte cap instead of buffering everything
    const reader = res.body?.getReader();
    if (!reader) {
      return { content: `Status: ${res.status} ${res.statusText}\n\n(no body)` };
    }

    const chunks: Uint8Array[] = [];
    let totalBytes = 0;
    let truncated = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) { break; }
      totalBytes += value.byteLength;
      if (totalBytes > MAX_WEBFETCH_BYTES) {
        truncated = true;
        reader.cancel();
        break;
      }
      chunks.push(value);
    }

    const body = Buffer.concat(chunks.map(c => Buffer.from(c))).toString('utf-8');
    const note = truncated ? `\n\n[truncated at ${MAX_WEBFETCH_BYTES} bytes, total ${totalBytes}+]` : '';
    return { content: `Status: ${res.status} ${res.statusText}\n\n${body}${note}` };
  } catch (err) {
    return { content: `Error: ${err instanceof Error ? err.message : String(err)}`, isError: true };
  } finally {
    clearTimeout(timeoutHandle);
  }
}

// Validation helpers (reqString/optString/reqInt/optInt/optBool/optEnum/ValidationError)
// are imported from ./pure so they can be unit-tested in plain Node without vscode.

export async function executeTool(name: string, args: Record<string, unknown>): Promise<ToolResult> {
  if (args === null || typeof args !== 'object') {
    return { content: `Error: arguments must be an object`, isError: true };
  }

  try {
    switch (name) {
      case 'listWorkspaceRoots':
        return listWorkspaceRoots();

      case 'readFile':
        return readFile({
          path: reqString(args, 'path'),
          root: optString(args, 'root'),
        });

      case 'listFiles':
        return listFiles({
          pattern: reqString(args, 'pattern'),
          maxResults: optInt(args, 'maxResults'),
          root: optString(args, 'root'),
        });

      case 'searchText':
        return searchText({
          query: reqString(args, 'query'),
          glob: optString(args, 'glob'),
          maxResults: optInt(args, 'maxResults'),
          root: optString(args, 'root'),
        });

      case 'editFile':
        return editFile({
          path: reqString(args, 'path'),
          old_text: reqString(args, 'old_text'),
          new_text: reqString(args, 'new_text'),
          replace_all: optBool(args, 'replace_all'),
          root: optString(args, 'root'),
        });

      case 'runCommand':
        return runCommand({
          command: reqString(args, 'command'),
          timeout: optInt(args, 'timeout'),
          root: optString(args, 'root'),
        });

      case 'getDiagnostics':
        return getDiagnostics({
          path: optString(args, 'path'),
          severity: optEnum(args, 'severity', ['error', 'warning', 'info', 'hint'] as const),
          root: optString(args, 'root'),
        });

      case 'getSymbols':
        return getSymbols({
          path: reqString(args, 'path'),
          root: optString(args, 'root'),
        });

      case 'getDefinition':
        return getDefinition({
          path: reqString(args, 'path'),
          line: reqInt(args, 'line'),
          character: reqInt(args, 'character'),
          root: optString(args, 'root'),
        });

      case 'getHover':
        return getHover({
          path: reqString(args, 'path'),
          line: reqInt(args, 'line'),
          character: reqInt(args, 'character'),
          root: optString(args, 'root'),
        });

      case 'webFetch':
        return webFetch({
          url: reqString(args, 'url'),
          timeout: optInt(args, 'timeout'),
        });

      default:
        return { content: `Unknown tool: ${name}`, isError: true };
    }
  } catch (err) {
    if (err instanceof ValidationError) {
      return { content: `Error: invalid arguments for ${name}: ${err.message}`, isError: true };
    }
    throw err;
  }
}
