import * as crypto from 'node:crypto';
import * as vscode from 'vscode';
import { runAgent, type AgentRequest, type AgentResponse } from './agent';
import { log } from './logger';

export interface Job {
  id: string;
  status: 'running' | 'done' | 'failed' | 'cancelled';
  request: AgentRequest;
  startedAt: number;
  finishedAt?: number;
  result?: AgentResponse;
  error?: string;
  cancelSource: vscode.CancellationTokenSource;
}

const jobs = new Map<string, Job>();

export function startJob(req: AgentRequest): string {
  const id = crypto.randomBytes(8).toString('hex');
  const cancelSource = new vscode.CancellationTokenSource();
  const job: Job = {
    id,
    status: 'running',
    request: req,
    startedAt: Date.now(),
    cancelSource,
  };
  jobs.set(id, job);

  // Run in background — don't await
  runAgent(req, cancelSource.token).then(
    (result) => {
      // If already cancelled, status was already set; don't overwrite
      if (job.status === 'running') {
        job.status = 'done';
        job.finishedAt = Date.now();
        job.result = result;
        log.info(`Job ${id} done: ${result.iterations} iterations, ${result.toolCalls.length} tool calls`);
      }
      cancelSource.dispose();
    },
    (err) => {
      if (job.status === 'running') {
        // Distinguish cancellation from real failure
        const msg = err instanceof Error ? err.message : String(err);
        const isCancel = cancelSource.token.isCancellationRequested || /cancel/i.test(msg);
        job.status = isCancel ? 'cancelled' : 'failed';
        job.finishedAt = Date.now();
        job.error = msg;
        if (job.status === 'cancelled') { log.info(`Job ${id} cancelled: ${msg}`); }
        else { log.error(`Job ${id} failed: ${msg}`); }
      }
      cancelSource.dispose();
    },
  );

  return id;
}

export function getJob(id: string): Job | undefined {
  return jobs.get(id);
}

export function listJobs(): Job[] {
  return Array.from(jobs.values());
}

export function cancelJob(id: string): boolean {
  const job = jobs.get(id);
  if (!job) { return false; }
  if (job.status !== 'running') { return false; }
  job.cancelSource.cancel();
  job.status = 'cancelled';
  job.finishedAt = Date.now();
  job.error = 'Cancelled by user';
  log.info(`Job ${id} cancelled by user`);
  return true;
}

export function deleteJob(id: string): boolean {
  const job = jobs.get(id);
  if (!job) { return false; }
  // If still running, cancel first
  if (job.status === 'running') {
    job.cancelSource.cancel();
  }
  return jobs.delete(id);
}
