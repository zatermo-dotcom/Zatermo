# Patterns Quick Reference

> Fast lookup. For decision logic see `pattern-selection.md`; for trade-off
> scoring see `trade-off-analysis.md`.

## Structural Patterns

| Pattern | Use When | Avoid When | Cost |
|---------|----------|------------|------|
| Monolith | Default; small team; one deploy | Teams need independent deploy at scale | Low |
| Modular Monolith | Growth stage; boundaries emerging | Truly independent scaling required | Low–Med |
| Microservices | Real domain boundaries + team autonomy | Before product-market fit | High |
| Serverless / FaaS | Spiky/low traffic, event-driven glue | Steady high throughput; long tasks | Med |

## Data Patterns

| Pattern | Use When | Avoid When | Cost |
|---------|----------|------------|------|
| Single relational DB | Default; transactions; clear schema | Extreme write scale on one entity | Low |
| Read replicas | Read-heavy, stale-tolerant reads | Strong read-after-write everywhere | Low–Med |
| CQRS | Read/write models diverge sharply | Simple CRUD | High |
| Event sourcing | Full audit history is a requirement | You just need current state | High |
| Polyglot persistence | A measured need a second store solves | "Might be useful" | Med–High |
| Sharding | One table outgrows a single node | Before you've measured the limit | High |

## Communication Patterns

| Pattern | Use When | Avoid When | Cost |
|---------|----------|------------|------|
| Sync request/response | Immediate answer needed | Long-running / decoupled work | Low |
| Message queue | Decouple, retry, smooth spikes | Simple in-request work | Med |
| Pub/Sub events | Fan-out, multiple consumers | Single known consumer | Med |
| API Gateway | Many clients / cross-cutting concerns | A single service | Med |

## Resilience Patterns

| Pattern | Purpose |
|---------|---------|
| Timeout | Never wait forever on a dependency |
| Retry (with backoff + jitter) | Ride out transient failures |
| Circuit breaker | Stop hammering a failing dependency |
| Bulkhead | Isolate failures to one pool |
| Idempotency keys | Make retries safe |
| Graceful degradation | Serve reduced function over none |

## Cross-Cutting

| Concern | Sensible Default |
|---------|------------------|
| AuthN | Managed identity provider / OIDC |
| AuthZ | Centralized policy, checked at the edge and in-service |
| Config | Environment + secrets manager; never in code |
| Observability | Structured logs + metrics + tracing from day one |
| Deployments | CI/CD, small reversible changes, feature flags |

## One-Line Heuristics

- Simplest thing that meets today's requirements wins.
- Measure before you cache, shard, or split.
- Reversible decisions deserve less deliberation; make them and move on.
- Each service owns its data, or it isn't a service.
- Design for the load you can project, keep seams for the load you imagine.
