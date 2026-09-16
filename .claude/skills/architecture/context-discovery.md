# Context Discovery

> Gather requirements and constraints *before* proposing any architecture.

## Discovery Questions

### Product & Users
- What problem does this system solve, and for whom?
- How many users at launch? In 12 months? Realistic growth curve.
- What are the core user journeys that must never break?
- What is the acceptable latency / availability for those journeys?

### Data
- What are the primary entities and their relationships?
- Read-heavy, write-heavy, or balanced?
- Consistency needs: strong, eventual, or per-operation?
- Data volume today and projected. Retention requirements.
- Any regulatory constraints (PII, GDPR, HIPAA, PCI, residency)?

### Team & Operations
- How many engineers? What are their strengths?
- What have they operated in production before?
- On-call maturity: is there a rotation, dashboards, runbooks?
- Deployment cadence expected: daily, weekly, monthly?

### Constraints
- Budget ceiling (infra + people).
- Deadline / time-to-market pressure.
- Existing systems this must integrate with.
- Cloud / vendor commitments already made.

## Project Classification

Use answers above to place the project into one of these tiers. The tier sets
the *default* complexity budget — spend more only with justification.

| Tier | Signals | Default Posture |
|------|---------|-----------------|
| **MVP / Prototype** | <1k users, 1–3 engineers, validating an idea, tight deadline | Monolith, single database, managed hosting. Optimize for speed of change. |
| **Growth / SaaS** | 1k–100k users, 3–15 engineers, product-market fit found | Modular monolith or a few services, primary DB + cache, CI/CD, observability. |
| **Enterprise / Scale** | 100k+ users, 15+ engineers, strict SLAs/compliance | Service boundaries by domain, per-service data ownership, strong platform tooling. |

## Red Flags During Discovery

- "We might need to scale to millions someday" with 50 users today → design for
  today, keep seams for tomorrow.
- Choosing microservices before a clear domain boundary exists.
- No named owner for operations.
- Requirements that are actually solutions in disguise ("we need Kafka") — dig
  for the underlying need.

## Output of This Phase

A short written summary: project tier, top 3–5 requirements, top 3–5 constraints,
and the 2–3 decisions that will most shape the architecture. Feed these into
`pattern-selection.md` and `trade-off-analysis.md`.
