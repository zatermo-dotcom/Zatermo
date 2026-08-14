# Pattern Selection

> Choose the simplest pattern that satisfies today's requirements. Preserve seams
> for tomorrow instead of building for it now.

## Application Structure

```
Do you have a proven domain boundary AND >1 team owning distinct areas?
├── No  → Monolith (or Modular Monolith once it grows). Default choice.
└── Yes → Split services along the domain boundaries you can name.
          One service per team-owned bounded context, not per noun.
```

- **Monolith** — one deployable. Best default. Fast to build, easy to reason about.
- **Modular Monolith** — internal module boundaries, still one deployable. The
  sweet spot for most Growth-tier products. Enforce boundaries with packages/interfaces.
- **Microservices** — separate deployables. Adopt only when independent scaling,
  independent deploy cadence, or team autonomy *forces* it. Each service owns its data.

## Data Storage

```
Relational data with clear schema and transactions? → Start with Postgres.
Key/value or cache needs?                           → Add Redis when measured.
Full-text / search-heavy?                           → Postgres FTS first; Elastic when it hurts.
Truly document-shaped, schema-fluid?                → Consider a document store.
Analytical / OLAP at scale?                         → Separate warehouse, not your OLTP DB.
```

Default: **one primary relational database.** Introduce a second datastore only
when a specific, measured need appears — not preemptively.

## Communication

```
Caller needs an immediate answer?          → Synchronous (HTTP/gRPC).
Work can happen later / fan-out / decouple? → Asynchronous (queue/events).
```

Prefer synchronous request/response until decoupling is proven necessary; async
adds delivery, ordering, and observability complexity.

## Caching

Add caching only after you can measure the hot path. Order of preference:
1. Do nothing (the DB is fast enough).
2. Application-level memoization / HTTP caching.
3. A shared cache (Redis) with an explicit invalidation strategy.

A cache without an invalidation plan is a future bug.

## Anti-Patterns to Avoid

| Anti-pattern | Why it hurts | Do instead |
|--------------|--------------|-----------|
| **Distributed monolith** | Services that must deploy together = worst of both | Keep it a monolith until boundaries are real |
| **Premature microservices** | Ops cost before product-market fit | Modular monolith |
| **Resume-driven design** | Tech chosen to be interesting, not to fit | Choose for team fit and requirements |
| **Database-per-feature** | Sprawl, no transactions across features | One primary DB; split only on proven need |
| **Golden hammer** | One tool for every problem | Match tool to the actual need |
| **Speculative generality** | Building for imagined future scale | Design for today, keep seams |
| **Shared mutable database across services** | Hidden coupling, no ownership | Each service owns its schema |

## Choosing Between Two Good Options

When patterns tie on requirements, break the tie in this order:
1. Simpler to operate.
2. More reversible.
3. Better team familiarity.
4. Lower ongoing cost.
