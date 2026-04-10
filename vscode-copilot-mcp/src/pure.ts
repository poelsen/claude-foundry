// Pure functions with no VS Code dependencies — testable in plain Node.

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40);
}

export function generateSessionId(task: string, now: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  const ts = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
  const slug = slugify(task);
  return slug ? `${ts}-${slug}` : ts;
}

export const BLOCKED_PATTERNS: RegExp[] = [
  /\brm\s+(-[a-zA-Z]*f|-[a-zA-Z]*r|--force|--recursive)/,
  /\bmkfs\b/, /\bdd\b.*\bof=/, /\bformat\b/,
  /\bcurl\b.*\|\s*(sh|bash)/, /\bwget\b.*\|\s*(sh|bash)/,
  /\bchmod\b.*777/, /\bchown\b/,
  />\s*\/dev\/sd/, />\s*\/etc\//,
  /\bkill\s+-9/, /\bkillall\b/,
  /\breboot\b/, /\bshutdown\b/, /\bhalt\b/,
];

export function matchDestructivePattern(command: string): RegExp | undefined {
  for (const pattern of BLOCKED_PATTERNS) {
    if (pattern.test(command)) { return pattern; }
  }
  return undefined;
}

// Session IDs must be non-empty, reasonable length, and limited to safe
// filename characters. Our auto-generated IDs (YYYYMMDD-HHMMSS-slug) fit
// this pattern; external callers passing custom IDs must match it too.
const SESSION_ID_REGEX = /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,199}$/;

export function isValidSessionId(id: string): boolean {
  return typeof id === 'string' && SESSION_ID_REGEX.test(id);
}

export function isPathSafe(resolvedPath: string, rootPath: string, sep: string): boolean {
  return resolvedPath === rootPath || resolvedPath.startsWith(rootPath + sep);
}

export function truncate(content: string, maxLen: number): string {
  if (content.length <= maxLen) { return content; }
  return content.slice(0, maxLen) + `\n...[truncated, ${content.length} chars total]`;
}

// Runtime validation helpers for LLM-supplied tool arguments.
export class ValidationError extends Error {
  constructor(message: string) { super(message); this.name = 'ValidationError'; }
}

export function reqString(args: Record<string, unknown>, key: string): string {
  const v = args[key];
  if (typeof v !== 'string') { throw new ValidationError(`${key} must be a string`); }
  return v;
}

export function optString(args: Record<string, unknown>, key: string): string | undefined {
  const v = args[key];
  if (v === undefined || v === null) { return undefined; }
  if (typeof v !== 'string') { throw new ValidationError(`${key} must be a string`); }
  return v;
}

export function reqInt(args: Record<string, unknown>, key: string): number {
  const v = args[key];
  if (typeof v !== 'number' || !Number.isFinite(v) || !Number.isInteger(v)) {
    throw new ValidationError(`${key} must be an integer`);
  }
  return v;
}

export function optInt(args: Record<string, unknown>, key: string): number | undefined {
  const v = args[key];
  if (v === undefined || v === null) { return undefined; }
  if (typeof v !== 'number' || !Number.isFinite(v) || !Number.isInteger(v)) {
    throw new ValidationError(`${key} must be an integer`);
  }
  return v;
}

export function optBool(args: Record<string, unknown>, key: string): boolean | undefined {
  const v = args[key];
  if (v === undefined || v === null) { return undefined; }
  if (typeof v !== 'boolean') { throw new ValidationError(`${key} must be a boolean`); }
  return v;
}

export function optEnum<T extends string>(args: Record<string, unknown>, key: string, values: readonly T[]): T | undefined {
  const v = args[key];
  if (v === undefined || v === null) { return undefined; }
  if (typeof v !== 'string' || !values.includes(v as T)) {
    throw new ValidationError(`${key} must be one of: ${values.join(', ')}`);
  }
  return v as T;
}

// SSRF protection — reject URLs pointing at loopback, private networks,
// link-local, and cloud metadata endpoints.
export function isBlockedHost(hostname: string): string | undefined {
  if (!hostname) { return 'empty hostname'; }

  const lower = hostname.toLowerCase();

  // Cloud metadata endpoints by hostname
  if (lower === 'metadata.google.internal') { return 'GCP metadata endpoint'; }
  if (lower === 'metadata' || lower === 'metadata.local') { return 'metadata endpoint'; }
  // Alibaba cloud, Oracle cloud, DigitalOcean all use 169.254.169.254 — caught by IP check below

  // Loopback hostnames
  if (lower === 'localhost' || lower === 'ip6-localhost' || lower === 'ip6-loopback') {
    return 'loopback hostname';
  }

  // IPv4 literal check
  const ipv4 = lower.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (ipv4) {
    const [, a, b, c, d] = ipv4;
    const oct = [a, b, c, d].map(Number);
    if (oct.some(n => n < 0 || n > 255)) { return 'invalid IPv4'; }

    // 127.0.0.0/8 — loopback
    if (oct[0] === 127) { return 'IPv4 loopback'; }
    // 10.0.0.0/8 — private
    if (oct[0] === 10) { return 'IPv4 private (10/8)'; }
    // 172.16.0.0/12 — private
    if (oct[0] === 172 && oct[1] >= 16 && oct[1] <= 31) { return 'IPv4 private (172.16/12)'; }
    // 192.168.0.0/16 — private
    if (oct[0] === 192 && oct[1] === 168) { return 'IPv4 private (192.168/16)'; }
    // 169.254.0.0/16 — link-local (includes 169.254.169.254 cloud metadata)
    if (oct[0] === 169 && oct[1] === 254) { return 'IPv4 link-local (includes cloud metadata)'; }
    // 0.0.0.0/8 — "this network"
    if (oct[0] === 0) { return 'IPv4 0.0.0.0/8'; }
    // 224.0.0.0/4 — multicast
    if (oct[0] >= 224 && oct[0] <= 239) { return 'IPv4 multicast'; }
  }

  // IPv6 checks — basic coverage
  if (lower.startsWith('[') && lower.endsWith(']')) {
    const ipv6 = lower.slice(1, -1);
    if (ipv6 === '::1' || ipv6 === '0:0:0:0:0:0:0:1') { return 'IPv6 loopback'; }
    if (ipv6 === '::' || ipv6 === '0:0:0:0:0:0:0:0') { return 'IPv6 unspecified'; }
    if (ipv6.startsWith('fc') || ipv6.startsWith('fd')) { return 'IPv6 unique local (fc00::/7)'; }
    if (ipv6.startsWith('fe80:') || ipv6.startsWith('fe8') || ipv6.startsWith('fe9') ||
        ipv6.startsWith('fea') || ipv6.startsWith('feb')) { return 'IPv6 link-local (fe80::/10)'; }
    // IPv4-mapped IPv6 dotted form (e.g., ::ffff:127.0.0.1)
    const mappedDotted = ipv6.match(/^::ffff:(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$/i);
    if (mappedDotted) { return isBlockedHost(mappedDotted[1]); }
    // IPv4-mapped IPv6 hex form — Node's URL parser normalizes dotted form
    // to hex: [::ffff:127.0.0.1] → [::ffff:7f00:1]. Must check this too or
    // SSRF protection is bypassed for canonical URL hostnames.
    const mappedHex = ipv6.match(/^::ffff:([0-9a-f]{1,4}):([0-9a-f]{1,4})$/i);
    if (mappedHex) {
      const hi = parseInt(mappedHex[1], 16);
      const lo = parseInt(mappedHex[2], 16);
      if (!isNaN(hi) && !isNaN(lo)) {
        const a = (hi >> 8) & 0xff;
        const b = hi & 0xff;
        const c = (lo >> 8) & 0xff;
        const d = lo & 0xff;
        return isBlockedHost(`${a}.${b}.${c}.${d}`);
      }
    }
    // IPv6 ::ffff: prefix with no address (malformed) — block to be safe
    if (/^::ffff:/i.test(ipv6)) {
      return 'IPv6 mapped (unrecognized form)';
    }
  }

  return undefined;
}
