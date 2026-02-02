# Security: Enterprise/Production

Strict security for customer-facing and production systems.

## Mandatory Checks - BLOCK commit if violated
- [ ] No hardcoded secrets (use secret manager)
- [ ] All user inputs validated and sanitized
- [ ] SQL injection prevention (parameterized queries only)
- [ ] XSS prevention (CSP headers, output encoding)
- [ ] CSRF protection on all state-changing endpoints
- [ ] Authentication on all endpoints (explicit public allowlist)
- [ ] Authorization checks (RBAC/ABAC)
- [ ] Rate limiting on all public endpoints
- [ ] Error messages leak nothing (generic user messages)
- [ ] All dependencies scanned for CVEs
- [ ] Secrets scanned in CI (gitleaks/git-secrets)

## Data Protection
- Encrypt at rest and in transit (TLS 1.3)
- PII handling compliant with GDPR/privacy reqs
- Audit logging for sensitive operations
- Data retention policies enforced

## Incident Response
If security issue found:
1. STOP immediately
2. Use **security-reviewer** agent
3. Fix CRITICAL issues before ANY other work
4. Rotate exposed secrets immediately
5. Review entire codebase for similar issues
6. Document in security log
