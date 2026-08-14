# Choosing council & chairman models

The council queries models through **OpenRouter**, so any model id that
OpenRouter serves is valid. Ids use the `provider/model` form, e.g.
`openai/gpt-5.1` or `anthropic/claude-sonnet-4.5`. Browse the current catalog and
exact ids at https://openrouter.ai/models.

## Defaults (upstream)

```
Council:  openai/gpt-5.1
          google/gemini-3-pro-preview
          anthropic/claude-sonnet-4.5
          x-ai/grok-4
Chairman: google/gemini-3-pro-preview
```

Set per-call:

```bash
python3 scripts/council.py \
  --models "openai/gpt-5.1,anthropic/claude-sonnet-4.5,google/gemini-3-pro-preview" \
  --chairman "anthropic/claude-sonnet-4.5" \
  "your question"
```

## Guidelines

- **Diversity beats size.** A council of models from *different* providers
  surfaces more blind spots than several models from one family. Mixing OpenAI +
  Anthropic + Google + xAI is the point.
- **3–5 members** is the sweet spot. Fewer than 3 and peer review is thin; many
  more and you pay a lot for diminishing returns.
- **Chairman choice matters.** The chairman writes the final answer, so pick a
  strong reasoning/synthesis model. It may be a council member or a separate
  model; the default reuses a council member.
- **Anonymization** in Stage 2 means a model can rank its own answer — that's
  intentional and fine; the aggregate averages over all voters.

## Cost & latency

Each full run makes **`2 · N + 1`** model calls (N first opinions + N rankings +
1 chairman synthesis), where N is the number of council members. Rankings feed
every other answer into each model, so Stage 2 prompts are large. To economize:

- Use `--stage 1` (just parallel opinions) or `--stage 2` (opinions + ranking,
  no chairman) when you don't need a synthesized answer.
- Trim the council to 3 members.
- Pick cheaper model tiers for the council and reserve a premium model for the
  chairman.

Ensure the OpenRouter account has credits (or auto top-up) before running, or
calls will fail with an HTTP 402/403 and the affected models will be skipped.

## Failure behavior

- A model that errors (bad id, rate limit, timeout, no credits) is **skipped**;
  its error prints to stderr and the council continues with the rest.
- If **every** council model fails, Stage 1 is empty, the script prints an error
  and exits non-zero.
- If the chairman fails, Stage 3 reports an error string but Stages 1–2 are still
  returned.
