---
name: llm-council
description: "Convene a council of multiple LLMs to answer a hard question, instead of trusting a single model. Runs karpathy's 3-stage deliberation via OpenRouter: every council model answers independently (Stage 1), each model reviews and ranks the others' anonymized answers (Stage 2), then a Chairman model synthesizes one final answer (Stage 3). Use for high-stakes questions, contested judgment calls, research/analysis, side-by-side model comparison, or when the user says 'ask the council', 'get a second opinion', 'poll the models', or uses /llm-council."
argument-hint: "[--stage 1|2|3] [--models a,b,c] [--chairman m] <your question>"
metadata:
  version: "1.0.0"
  source: "https://github.com/karpathy/llm-council"
  upstream-author: karpathy
  requires: "OPENROUTER_API_KEY"
---

# LLM Council — deliberation across multiple models

Port of [karpathy/llm-council](https://github.com/karpathy/llm-council) as a
Claude skill. Instead of asking one LLM, convene a **council** and let the
models critique and rank each other before a **Chairman** writes the final
answer. It surfaces disagreement, catches single-model blind spots, and shows
you which models the *other* models trusted most.

## When to use this

- The question is high-stakes, contested, or benefits from multiple viewpoints.
- The user asks to "ask the council", "poll the models", "get a second opinion",
  "compare what different models say", or invokes `/llm-council`.
- You want anonymized peer ranking of answers, not just parallel answers.

For a quick factual lookup or a task you can answer directly, you do **not** need
the council — just answer.

## Prerequisites

1. **OpenRouter API key.** Get one at https://openrouter.ai/ (buy credits or
   enable auto top-up — each run makes `2·N + 1` model calls).
2. Provide the key by either:
   - `export OPENROUTER_API_KEY=sk-or-v1-...`, or
   - a `.env` file in the project root containing `OPENROUTER_API_KEY=sk-or-v1-...`
     (the script auto-loads `.env` from the CWD and parent directories).
3. **Python 3** only — the script uses the standard library, no `pip install`.

If the key is missing, the script exits with a clear message. Relay it and ask
the user to set the key; do not invent one.

## How to run it

The whole skill is one self-contained script. Always call it with an absolute
path so it works from any directory:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/council.py "the user's question"
```

Common invocations:

| Goal | Command |
|------|---------|
| Full 3-stage council (default) | `python3 .../council.py "question"` |
| Just first opinions (Stage 1) | `python3 .../council.py --stage 1 "question"` |
| Opinions + peer ranking (Stage 2) | `python3 .../council.py --stage 2 "question"` |
| Custom council | `python3 .../council.py --models "openai/gpt-5.1,anthropic/claude-sonnet-4.5,google/gemini-3-pro-preview" "question"` |
| Custom chairman | `python3 .../council.py --chairman "anthropic/claude-sonnet-4.5" "question"` |
| Machine-readable output | `python3 .../council.py --json "question"` |
| Quiet (no progress on stderr) | `python3 .../council.py --quiet "question"` |

Progress lines are written to **stderr**; the result (text or JSON) goes to
**stdout**. Runs can take a minute or more because it waits on several models.

## The three stages (what the script does)

1. **Stage 1 — First opinions.** The query is sent to every council model in
   parallel. Failed models are dropped; the council continues with whoever
   answered (graceful degradation).
2. **Stage 2 — Review.** Each model receives the *other* answers, **anonymized**
   as "Response A/B/C…" so it can't play favorites, and ranks them from best to
   worst using a strict `FINAL RANKING:` format. The script parses each ranking
   and computes an **aggregate ranking** (average position across all voters).
3. **Stage 3 — Final response.** The **Chairman** model gets all answers plus all
   rankings and synthesizes one final answer representing the council's
   collective wisdom.

## Defaults (from upstream `backend/config.py`)

- Council: `openai/gpt-5.1`, `google/gemini-3-pro-preview`,
  `anthropic/claude-sonnet-4.5`, `x-ai/grok-4`
- Chairman: `google/gemini-3-pro-preview`

Override per-call with `--models` / `--chairman`. See
`references/models.md` for how to pick models and manage cost. If a model id is
rejected by OpenRouter, that model is skipped (its error prints to stderr) and
the council proceeds with the rest.

## Presenting results to the user

Default to the human-readable output. When you relay it:

1. **Lead with the Stage 3 Chairman answer** — that's the deliverable.
2. Offer the **aggregate ranking** as a one-line summary of which model the
   council rated highest.
3. Mention Stage 1/Stage 2 detail only if the user wants to see the individual
   opinions or the disagreement, or if the models notably diverged.
4. If some models failed, say which and that the council continued without them.
5. Never present the council's answer as ground truth — it's a synthesis of
   several models and can still be wrong. Flag genuine disagreement rather than
   papering over it.

Use `--json` when you need to post-process the result yourself (e.g. build a
comparison table or save the conversation).

## Reference

- `references/models.md` — choosing council/chairman models, cost, and OpenRouter
  model ids.

## Attribution

This skill is a faithful port of **karpathy/llm-council**
(https://github.com/karpathy/llm-council), which the author describes as a
"99% vibe coded" Saturday hack provided as-is. Stage prompts are preserved
verbatim from the original `backend/council.py`.
