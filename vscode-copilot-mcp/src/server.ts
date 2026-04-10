import * as http from 'node:http';
import * as crypto from 'node:crypto';
import * as vscode from 'vscode';
import { runAgent, type AgentRequest } from './agent';
import { listSessions, deleteSession, loadSession } from './sessions';
import { startJob, getJob, listJobs, deleteJob, cancelJob } from './jobs';
import { log } from './logger';

interface ChatRequest {
  messages: Array<{ role: 'user' | 'assistant'; content: string }>;
  model?: string;
  family?: string;
  vendor?: string;
}

interface ChatResponse {
  content: string;
  model: string;
}

interface ErrorResponse {
  error: string;
}

export class Server {
  private httpServer: http.Server | undefined;
  private port: number;
  private token: string;

  constructor(port: number, token?: string) {
    this.port = port;
    this.token = token ?? crypto.randomBytes(32).toString('hex');
  }

  getToken(): string {
    return this.token;
  }

  async start(): Promise<number> {
    // Wrap handleRequest with a top-level catch so async throws become
    // 500 responses instead of unhandled promise rejections that crash the
    // extension host.
    this.httpServer = http.createServer((req, res) => {
      this.handleRequest(req, res).catch((err) => {
        log.error(`Unhandled error in request handler: ${err instanceof Error ? err.stack : String(err)}`);
        if (!res.headersSent) {
          try {
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'Internal server error' } satisfies ErrorResponse));
          } catch { /* response already closed */ }
        }
      });
    });
    return new Promise((resolve, reject) => {
      this.httpServer!.listen(this.port, '127.0.0.1', () => {
        const addr = this.httpServer!.address();
        const actualPort = typeof addr === 'object' && addr ? addr.port : this.port;
        resolve(actualPort);
      });
      this.httpServer!.on('error', reject);
    });
  }

  async stop(): Promise<void> {
    return new Promise((resolve) => {
      if (!this.httpServer) {
        resolve();
        return;
      }
      // close() stops accepting new connections but waits for existing
      // connections to drain — which can block forever if a client has an
      // open long-poll or a webFetch is downloading. Force-close active
      // sockets so stop() always returns promptly.
      const server = this.httpServer;
      server.close(() => resolve());
      // closeAllConnections() added in Node 18.2; guarded for safety
      if (typeof (server as any).closeAllConnections === 'function') {
        (server as any).closeAllConnections();
      }
    });
  }

  private safeDecodeSegment(segment: string): string | undefined {
    try {
      return decodeURIComponent(segment);
    } catch {
      return undefined;
    }
  }

  private async handleRequest(req: http.IncomingMessage, res: http.ServerResponse) {
    res.setHeader('Content-Type', 'application/json');

    // Parse URL once — use pathname only for routing (ignore query/fragment)
    let pathname: string;
    try {
      const parsed = new URL(req.url ?? '/', 'http://localhost');
      pathname = parsed.pathname;
    } catch {
      res.writeHead(400);
      res.end(JSON.stringify({ error: 'Invalid URL' } satisfies ErrorResponse));
      return;
    }

    // Health endpoint is unauthenticated (for connectivity checks)
    if (req.method === 'GET' && pathname === '/health') {
      res.writeHead(200);
      res.end(JSON.stringify({ status: 'ok' }));
      return;
    }

    // All other endpoints require Bearer token (timing-safe comparison)
    const authHeader = req.headers.authorization ?? '';
    const expected = `Bearer ${this.token}`;
    const authValid = authHeader.length === expected.length &&
      crypto.timingSafeEqual(Buffer.from(authHeader), Buffer.from(expected));
    if (!authValid) {
      res.writeHead(401);
      res.end(JSON.stringify({ error: 'Unauthorized' } satisfies ErrorResponse));
      return;
    }

    if (req.method === 'GET' && pathname === '/models') {
      await this.handleListModels(res);
      return;
    }

    if (req.method === 'POST' && pathname === '/chat') {
      await this.handleChat(req, res);
      return;
    }

    if (req.method === 'POST' && pathname === '/agent') {
      await this.handleAgent(req, res);
      return;
    }

    if (req.method === 'POST' && pathname === '/jobs') {
      await this.handleStartJob(req, res);
      return;
    }

    if (req.method === 'GET' && pathname === '/jobs') {
      const jobs = listJobs().map(j => ({
        id: j.id,
        status: j.status,
        startedAt: j.startedAt,
        finishedAt: j.finishedAt,
        task: j.request.task.slice(0, 100),
      }));
      res.writeHead(200);
      res.end(JSON.stringify({ jobs }));
      return;
    }

    if (req.method === 'GET' && pathname.startsWith('/jobs/')) {
      const id = this.safeDecodeSegment(pathname.slice('/jobs/'.length));
      if (id === undefined) {
        res.writeHead(400);
        res.end(JSON.stringify({ error: 'Malformed URL encoding' } satisfies ErrorResponse));
        return;
      }
      const job = getJob(id);
      if (!job) {
        res.writeHead(404);
        res.end(JSON.stringify({ error: 'Job not found' } satisfies ErrorResponse));
        return;
      }
      res.writeHead(200);
      res.end(JSON.stringify({
        id: job.id,
        status: job.status,
        startedAt: job.startedAt,
        finishedAt: job.finishedAt,
        elapsed: (job.finishedAt ?? Date.now()) - job.startedAt,
        result: job.result,
        error: job.error,
      }));
      return;
    }

    if (req.method === 'POST' && pathname.startsWith('/jobs/') && pathname.endsWith('/cancel')) {
      const id = this.safeDecodeSegment(pathname.slice('/jobs/'.length, -'/cancel'.length));
      if (id === undefined) {
        res.writeHead(400);
        res.end(JSON.stringify({ error: 'Malformed URL encoding' } satisfies ErrorResponse));
        return;
      }
      const cancelled = cancelJob(id);
      res.writeHead(cancelled ? 200 : 404);
      res.end(JSON.stringify({ cancelled }));
      return;
    }

    if (req.method === 'DELETE' && pathname.startsWith('/jobs/')) {
      const id = this.safeDecodeSegment(pathname.slice('/jobs/'.length));
      if (id === undefined) {
        res.writeHead(400);
        res.end(JSON.stringify({ error: 'Malformed URL encoding' } satisfies ErrorResponse));
        return;
      }
      const deleted = deleteJob(id);
      res.writeHead(deleted ? 200 : 404);
      res.end(JSON.stringify({ deleted }));
      return;
    }

    if (req.method === 'GET' && pathname === '/sessions') {
      res.writeHead(200);
      res.end(JSON.stringify({ sessions: await listSessions() }));
      return;
    }

    if (req.method === 'GET' && pathname.startsWith('/sessions/')) {
      const id = this.safeDecodeSegment(pathname.slice('/sessions/'.length));
      if (id === undefined) {
        res.writeHead(400);
        res.end(JSON.stringify({ error: 'Malformed URL encoding' } satisfies ErrorResponse));
        return;
      }
      const session = await loadSession(id);
      if (!session) {
        res.writeHead(404);
        res.end(JSON.stringify({ error: 'Session not found' } satisfies ErrorResponse));
        return;
      }
      res.writeHead(200);
      res.end(JSON.stringify(session));
      return;
    }

    if (req.method === 'DELETE' && pathname.startsWith('/sessions/')) {
      const id = this.safeDecodeSegment(pathname.slice('/sessions/'.length));
      if (id === undefined) {
        res.writeHead(400);
        res.end(JSON.stringify({ error: 'Malformed URL encoding' } satisfies ErrorResponse));
        return;
      }
      const deleted = await deleteSession(id);
      res.writeHead(deleted ? 200 : 404);
      res.end(JSON.stringify({ deleted }));
      return;
    }

    res.writeHead(404);
    res.end(JSON.stringify({ error: 'Not found' } satisfies ErrorResponse));
  }

  private static MAX_BODY = 1024 * 1024; // 1MB

  private async readBody(req: http.IncomingMessage): Promise<string | null> {
    const chunks: Buffer[] = [];
    let totalBytes = 0;
    for await (const chunk of req) {
      const buf = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
      totalBytes += buf.byteLength;
      if (totalBytes > Server.MAX_BODY) { return null; }
      chunks.push(buf);
    }
    return Buffer.concat(chunks).toString('utf-8');
  }

  private async handleListModels(res: http.ServerResponse) {
    try {
      const models = await vscode.lm.selectChatModels();
      const result = models.map(m => ({
        id: m.id,
        name: m.name,
        vendor: m.vendor,
        family: m.family,
        version: m.version,
        maxInputTokens: m.maxInputTokens,
        supportsImages: (m as any).capabilities?.supportsImageToText ?? false,
        supportsTools: (m as any).capabilities?.supportsToolCalling ?? false,
      }));
      res.writeHead(200);
      res.end(JSON.stringify(result));
    } catch (err) {
      res.writeHead(500);
      res.end(JSON.stringify({ error: String(err) } satisfies ErrorResponse));
    }
  }

  private async handleChat(req: http.IncomingMessage, res: http.ServerResponse) {
    const body = await this.readBody(req);
    if (body === null) {
      res.writeHead(413);
      res.end(JSON.stringify({ error: 'Request body too large' } satisfies ErrorResponse));
      return;
    }

    let chatReq: ChatRequest;
    try {
      chatReq = JSON.parse(body);
    } catch {
      res.writeHead(400);
      res.end(JSON.stringify({ error: 'Invalid JSON' } satisfies ErrorResponse));
      return;
    }

    if (!chatReq.messages?.length) {
      res.writeHead(400);
      res.end(JSON.stringify({ error: 'messages array required' } satisfies ErrorResponse));
      return;
    }

    try {
      const selector: vscode.LanguageModelChatSelector = {};
      if (chatReq.model) { selector.id = chatReq.model; }
      if (chatReq.family) { selector.family = chatReq.family; }
      (selector as any).vendor = chatReq.vendor ?? 'copilot';

      const models = await vscode.lm.selectChatModels(selector);
      if (models.length === 0) {
        res.writeHead(404);
        res.end(JSON.stringify({ error: 'No matching model found' } satisfies ErrorResponse));
        return;
      }

      const model = models[0];
      log.info(`Chat: using ${model.id} (${model.vendor}/${model.family})`);

      const messages = chatReq.messages.map(m =>
        m.role === 'user'
          ? vscode.LanguageModelChatMessage.User(m.content)
          : vscode.LanguageModelChatMessage.Assistant(m.content)
      );

      const tokenSource = new vscode.CancellationTokenSource();
      // Cancel the LM request if the HTTP client disconnects mid-stream
      const onClose = () => {
        log.info('Chat: client disconnected, cancelling');
        tokenSource.cancel();
      };
      req.on('close', onClose);

      let content = '';
      try {
        log.debug(`Chat: sending ${messages.length} message(s)`);
        const response = await model.sendRequest(messages, {}, tokenSource.token);
        log.debug(`Chat: streaming response`);

        let chunkCount = 0;
        for await (const chunk of response.text) {
          chunkCount++;
          content += chunk;
        }
        log.info(`Chat done: ${chunkCount} chunks, ${content.length} chars`);
      } finally {
        req.removeListener('close', onClose);
        tokenSource.dispose();
      }

      const result: ChatResponse = { content, model: model.id };
      res.writeHead(200);
      res.end(JSON.stringify(result));
    } catch (err) {
      res.writeHead(500);
      res.end(JSON.stringify({ error: String(err) } satisfies ErrorResponse));
    }
  }

  private async handleStartJob(req: http.IncomingMessage, res: http.ServerResponse) {
    const body = await this.readBody(req);
    if (body === null) {
      res.writeHead(413);
      res.end(JSON.stringify({ error: 'Request body too large' } satisfies ErrorResponse));
      return;
    }

    let agentReq: AgentRequest;
    try {
      agentReq = JSON.parse(body);
    } catch {
      res.writeHead(400);
      res.end(JSON.stringify({ error: 'Invalid JSON' } satisfies ErrorResponse));
      return;
    }

    if (!agentReq.task) {
      res.writeHead(400);
      res.end(JSON.stringify({ error: 'task field required' } satisfies ErrorResponse));
      return;
    }

    const jobId = startJob(agentReq);
    log.info(`Job ${jobId} started: ${agentReq.task.slice(0, 100)}`);
    res.writeHead(202);
    res.end(JSON.stringify({ jobId, status: 'running' }));
  }

  private async handleAgent(req: http.IncomingMessage, res: http.ServerResponse) {
    const body = await this.readBody(req);
    if (body === null) {
      res.writeHead(413);
      res.end(JSON.stringify({ error: 'Request body too large' } satisfies ErrorResponse));
      return;
    }

    let agentReq: AgentRequest;
    try {
      agentReq = JSON.parse(body);
    } catch {
      res.writeHead(400);
      res.end(JSON.stringify({ error: 'Invalid JSON' } satisfies ErrorResponse));
      return;
    }

    if (!agentReq.task) {
      res.writeHead(400);
      res.end(JSON.stringify({ error: 'task field required' } satisfies ErrorResponse));
      return;
    }

    // Cancel the agent run if the HTTP client disconnects
    const tokenSource = new vscode.CancellationTokenSource();
    const onClose = () => {
      log.info('Agent sync: client disconnected, cancelling');
      tokenSource.cancel();
    };
    req.on('close', onClose);

    try {
      log.info(`Agent task (sync): ${agentReq.task.slice(0, 100)}`);
      const result = await runAgent(agentReq, tokenSource.token);
      res.writeHead(200);
      res.end(JSON.stringify(result));
    } catch (err) {
      res.writeHead(500);
      res.end(JSON.stringify({ error: String(err) } satisfies ErrorResponse));
    } finally {
      req.removeListener('close', onClose);
      tokenSource.dispose();
    }
  }
}
