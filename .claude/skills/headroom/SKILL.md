---
name: headroom
description: "Context compression layer for AI agents — Headroom (headroomlabs-ai/headroom). Use for ANY request about cutting token spend, compressing prompts/tool output/logs/RAG chunks, running the Headroom proxy or MCP server, wrapping a coding agent (claude, codex, copilot, cursor, opencode…), reading the savings dashboard, cross-agent memory, or `headroom learn`. Triggers on: headroom, compress context, reduce tokens, token savings, shrink prompt, proxy compression, headroom wrap, headroom proxy, headroom_compress, headroom_retrieve, CCR, kompress, cache mode vs token mode, savings profile."
argument-hint: "[install|wrap|proxy|mcp|savings|learn|memory|diagnose] <agent or question>"
metadata:
  version: "0.37.0"
  upstream: "https://github.com/headroomlabs-ai/headroom"
  docs: "https://docs.headroomlabs.ai/docs"
  license: "Apache-2.0"
---

# Headroom — context compression for agents

Headroom compresses what an agent reads — tool outputs, logs, RAG chunks, files,
conversation history — before it reaches the model. Compression runs locally; no
prompt or file content leaves the machine. Apache 2.0.

Four surfaces, one pipeline:

| Surface | Entry point | Use when |
|---|---|---|
| Proxy | `headroom proxy --port 8787` | Any OpenAI/Anthropic-compatible client, zero code change |
| Agent wrap | `headroom wrap <agent>` | A coding agent (Claude Code, Codex, Copilot…) |
| Library | `compress(messages)` (Python / TS) | Inline in your own app |
| MCP server | `headroom mcp install` | Agent calls compression as a tool |

Pipeline: `CacheAligner → ContentRouter → {SmartCrusher (JSON) · CodeCompressor
(AST) · Kompress-v2-base (prose)} → CCR`. CCR keeps the original locally so the
model can call `headroom_retrieve` and get the full text back — compression is
reversible, not lossy-by-fiat.

## Before you act

Read the reference that matches the request. Do not answer CLI flags, env vars
or SDK signatures from memory — this file only carries the shape.

| Request is about | Read |
|---|---|
| Any `headroom …` command, wrapping an agent, `unwrap` | `references/cli.md` |
| `headroom_compress` / `_retrieve` / `_stats`, MCP host config | `references/mcp.md` |
| Env vars, savings profiles, cache vs token mode, per-request overrides | `references/configuration.md` |
| `compress()` in Python/TS, SDK wrappers, LangChain/Agno/LiteLLM/Vercel | `references/sdk.md` |
| "no savings", proxy won't start, install failures, what it won't compress | `references/troubleshooting.md` |

## Install (the part people get wrong)

```bash
uv tool install --python 3.13 "headroom-ai[all]"   # CLI, isolated env — preferred
pip install "headroom-ai[all]"                     # also ships the CLI
```

Three rules worth stating up front, because each one produces a confused user:

1. **The `headroom` CLI ships only in the PyPI package.** `npm install headroom-ai`
   is the TypeScript SDK — a library you import. It provides no `headroom` command.
2. **Pick Python 3.13 for the dollar figure.** The dashboard prices savings with
   LiteLLM, which does not install on 3.14+. Token counts still track; the dollar
   tile stays `$0.00`.
3. **MCP hosts often don't inherit your shell `PATH`.** Configure the absolute
   path from `command -v headroom`, not the bare name.

Verify with `headroom doctor` — it confirms routing actually works, which a
version check does not.

## The default that surprises everyone

Out of the box Headroom runs the `coding` savings profile, which runs the proxy
in **cache** mode: it freezes prior turns and compresses only the newest delta,
so the provider's prefix cache is never busted. Consequence: the dashboard's
headline **Tokens Saved** tile can read near zero while real cost drops, because
the savings moved to cheap cached-prefix reads.

- Savings are in the **Prefix Cache Impact** panel and the **Compression vs Cache** tile.
- Want big visible compression numbers? `headroom proxy --mode token`, or
  `HEADROOM_SAVINGS_PROFILE=agent-90`. Use it to compare or diagnose, not as a
  permanent setting — on long coding sessions prefix-cache stability usually wins.
- A profile's `proxy_mode` **overrides** `--mode`. Under `coding`, `--mode token`
  does nothing. Change the profile, not the flag.

## Setting expectations honestly

Headroom pays off on long agent sessions with heavy tool output. It does very
little on short exchanges, prose, and already-dense payloads. Quote ranges, not
promises, and point at `headroom savings` for the number that applies to the
user's own traffic.

Never compressed, by design: messages under `min_tokens_to_compress` (50 tokens),
source code in the last 4 messages, code at all when the latest user message
reads as analysis intent ("analyze", "review", "explain", "fix", "debug"),
system prompts (prefix-cache), images (fixed ~1,600-token cost). Malformed JSON
passes through silently rather than erroring. `references/troubleshooting.md`
has the full gate list — read it before telling someone their setup is broken.

## Typical flows

**Wrap Claude Code for a session.** `headroom wrap claude` starts the proxy,
registers the Headroom MCP server, installs Serena for code memory at *user*
scope (`~/.claude.json` — it persists into other projects until `headroom unwrap
claude`), and launches the agent routed through the proxy. Useful flags:
`--memory`, `--code-graph`, `--1m` (keeps the 1M window, which a custom
`ANTHROPIC_BASE_URL` otherwise caps at 200k), `--tool-search` (keeps on-demand
tool loading alive through the proxy), `--code-memory none` (skip Serena).
Launch a wrapped session each time — that is what runs the setup.

**Watch the savings.** `headroom dashboard` (needs a running proxy), or
`headroom savings` for durable history, `headroom output-savings` for the
output-side estimate, `headroom inspect` to see original vs compressed for
recent requests.

**Trim what the model writes back.** `HEADROOM_OUTPUT_SHAPER=1` — off by
default. Verbosity steering appends a terseness note to the *end* of the system
prompt (cache-safe); effort routing lowers thinking effort when a turn is only
the model resuming after a tool result. `headroom learn --verbosity` infers the
level from past sessions; `--apply` persists it.

**Mine failures into rules.** `headroom learn` reads past sessions and writes
corrections to `CLAUDE.local.md` by default (personal, gitignored). `--target
CLAUDE.md` writes the team-shared file instead. Default is a dry run; `--apply`
writes.

## This repository

`.claude/settings.json` already registers the `headroom-marketplace` and enables
the `headroom` plugin, whose SessionStart and PreToolUse hooks run
`headroom init hook ensure` (see `.claude/HEADROOM.md`). Those hooks need the CLI
on `PATH`; without it they fail harmlessly and nothing is compressed.

`scripts/status.sh` reports whether the CLI, the proxy and the MCP registration
are actually live — run it before debugging anything else.
