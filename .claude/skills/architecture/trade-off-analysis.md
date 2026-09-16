# Trade-off Analysis & ADRs

> Every significant decision gets an explicit trade-off analysis and an ADR.

## What Counts as "Significant"?

Write an ADR when a decision is:
- **Hard to reverse** (data model, primary datastore, sync vs async core, language/runtime).
- **Cross-cutting** (auth, multi-tenancy, deployment topology).
- **Contested** (the team disagreed, or a simpler option was rejected).

Skip ADRs for routine, easily reversible choices (a helper library, a lint rule).

## Trade-off Framework

For each decision, evaluate options against the dimensions that matter for the
project tier. Score qualitatively (— / ○ / ✓ / ✓✓), not with false precision.

| Dimension | Ask |
|-----------|-----|
| Simplicity | How much cognitive load / moving parts does this add? |
| Time to build | How fast can the team ship it? |
| Operability | Can this team run it in production, on-call included? |
| Scalability | Does it meet the *projected* (not imagined) load? |
| Cost | Infra + people + opportunity cost. |
| Reversibility | How expensive is it to change our mind later? |
| Team fit | Does the team already know this, or must they learn it? |

Rule: when two options are close, **pick the simpler and more reversible one.**

### Example Comparison

Decision: session storage for a Growth-tier SaaS.

| Option | Simplicity | Operability | Scalability | Reversibility |
|--------|-----------|-------------|-------------|---------------|
| Signed cookies (stateless) | ✓✓ | ✓✓ | ✓✓ | ✓ |
| DB-backed sessions | ✓ | ✓ | ✓ | ✓✓ |
| Redis sessions | ○ | ○ | ✓✓ | ✓ |

→ Start with signed cookies; revisit only if per-request revocation is required.

## ADR Template

Store ADRs in `docs/adr/NNNN-short-title.md`, numbered sequentially.

```markdown
# ADR-000N: <Short Decision Title>

- Status: Proposed | Accepted | Superseded by ADR-XXXX | Deprecated
- Date: YYYY-MM-DD
- Deciders: <names / roles>

## Context
What problem are we solving? What constraints and requirements apply?
Link to discovery notes.

## Decision
The choice we are making, stated plainly in one or two sentences.

## Alternatives Considered
- **Option A** — why rejected.
- **Option B** — why rejected.
(Include the trade-off table if it clarifies.)

## Consequences
- Positive: what this buys us.
- Negative / costs: what we accept.
- Follow-ups: seams to preserve, metrics to watch, revisit triggers.
```

## Lightweight Variant

For fast-moving MVPs, a 5-line ADR is fine:

```markdown
# ADR-000N: <Title> — Accepted YYYY-MM-DD
Context: <one line>
Decision: <one line>
Why not the alternatives: <one line>
Revisit when: <trigger>
```

## Superseding

Never delete an ADR. When a decision changes, add a new ADR and set the old
one's status to `Superseded by ADR-XXXX`. The history is the value.
