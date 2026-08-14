# Reference Examples

> Three worked examples, one per project tier. Use them as starting points, not
> templates to copy blindly — always re-run discovery for the real project.

## Example 1 — MVP / Prototype

**Scenario:** Solo founder + 1 engineer validating a booking product. <500 users
expected in the first quarter. Deadline in 6 weeks.

**Architecture:**
- Single monolith (server-rendered or SPA + one API).
- One managed Postgres instance.
- Managed platform hosting (PaaS); no Kubernetes.
- Auth via a managed provider or signed-cookie sessions.
- Background jobs via an in-process/simple queue only if needed.

**Explicitly deferred:** caching layer, service split, message broker, multi-region.

**Key ADRs:** monolith over services; Postgres as single store; managed hosting.

**Revisit triggers:** sustained >5k users, or the team grows past ~4 engineers.

---

## Example 2 — Growth / SaaS

**Scenario:** 20k active users, 8 engineers across 2 loose teams, product-market
fit reached. Daily deploys wanted. Some tenants ask about data export/compliance.

**Architecture:**
- **Modular monolith** with enforced module boundaries (billing, core domain,
  notifications). One or two supporting services only where scaling differs.
- Primary Postgres + Redis for caching and rate limiting (added after measuring).
- Async queue for email/notifications and export jobs.
- CI/CD pipeline, feature flags, structured logging + metrics + tracing.
- Multi-tenancy via a tenant_id column with row-level scoping (revisit if a
  tenant needs isolation).

**Explicitly deferred:** full microservices, multi-region active-active.

**Key ADRs:** modular monolith vs microservices; shared-DB multi-tenancy model;
Redis introduction justified by measured latency.

**Revisit triggers:** a module needs independent scaling/deploy; a tenant needs
hard data isolation; team grows past ~15.

---

## Example 3 — Enterprise / Scale

**Scenario:** 500k+ users, 40 engineers in 6 teams, strict SLAs and regulatory
audit requirements.

**Architecture:**
- Services aligned to **bounded contexts**, each owned by one team and owning its
  own datastore. No shared mutable database.
- Async event backbone for cross-context integration; sync APIs where an
  immediate answer is required.
- Platform team provides paved-road CI/CD, observability, secrets, and IaC.
- Data warehouse separate from OLTP stores for analytics.
- Explicit SLOs per service with error budgets.

**Explicitly deferred:** splitting a service further than a team can own.

**Key ADRs:** context boundaries and ownership; event backbone choice; data
ownership rules; SLO/error-budget policy.

**Revisit triggers:** an SLO is chronically missed; a context's ownership becomes
ambiguous; cross-service transactions start appearing (a boundary is wrong).

---

## Reading the Examples

Notice the progression is driven by **team size and proven load**, not ambition.
Each tier explicitly names what it *defers*. The point of an architecture is as
much what you choose not to build as what you build.
