# Style: Backend Services

## Reliability

- Retry with exponential backoff + jitter
- Circuit breakers for external dependencies
- Timeouts on all external calls
- Idempotent operations where possible

## Observability

- Structured logging with correlation IDs
- Log actionable events, not noise
- Health checks and readiness probes
- Never log secrets or PII

## Data Handling

- Validate all external input (schema validation)
- Strong types at API boundaries
- Graceful degradation over hard failures

## Concurrency

- Document thread-safety assumptions
- Bulkhead isolation for resource pools

## Checklist

- [ ] Retries have backoff and limits
- [ ] External calls have timeouts
- [ ] Errors logged with correlation ID
- [ ] Input validated at API boundary
