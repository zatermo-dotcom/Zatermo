# Troubleshooting and limits

Check the safety gates below **before** concluding a setup is broken. Most
"Headroom isn't working" reports are Headroom working as designed.

## "No token savings"

Diagnose first:

```python
stats = client.get_stats()
print(stats["config"]["mode"])                       # should be "optimize", not "audit"
print(stats["transforms"]["smart_crusher_enabled"])
```

Ordinary causes, in the order they actually occur:

1. SDK mode is `audit` — observation only. Set `default_mode="optimize"` or pass
   `headroom_mode="optimize"` per request.
2. The proxy is in **cache** mode (the default). Compression numbers are
   *supposed* to be small; the savings are cached-prefix reads. See below.
3. The messages carry no tool output, or the tool output is under the 200-token
   `min_tokens_to_crush` threshold. Lower it:
   `config.smart_crusher.min_tokens_to_crush = 100`.
4. The data is not compressible — high uniqueness, source code, grep results.

### The 0.31.0 "dashboard reads ~0" case

After 0.27 → 0.31 the Tokens Saved tile can read ~0 while total spend is flat or
lower. That is the `coding` profile shipping as the default and running the
proxy in cache mode: the prefix is frozen and only the newest delta is
compressed, deliberately avoiding a prompt-cache bust. Look at **Prefix Cache
Impact** and the **Compression vs Cache** tile instead — the headline tile counts
only compression and understates cache mode.

To get 0.27-style numbers back, for comparison rather than permanently:

```bash
headroom proxy --mode token
HEADROOM_SAVINGS_PROFILE=balanced headroom proxy   # ~70%
HEADROOM_SAVINGS_PROFILE=agent-90 headroom proxy   # ~90%
```

Remember `coding`'s `proxy_mode` overrides `--mode` — change the profile.

## Never compressed, by design

- Messages under `min_tokens_to_compress` (50 tokens by default; profiles set
  10–250). Blocks under `min_chars_for_block_compression` (500 chars). Both
  measured in tokens/characters, never words.
- **Source code in the last 4 messages** (`protect_recent_code=4`).
- **All code in the conversation** when the latest user message reads as
  analysis intent — "analyze", "review", "explain", "fix", "debug"
  (`protect_analysis_context=True`). Override with
  `protect_analysis_context=False` in `ContentRouterConfig`; needs
  `headroom-ai[code]` for tree-sitter.
- **System prompts** — preserved for prefix-cache compatibility.
- **Images** — counted at a fixed ~1,600 tokens, not compressed.
- **grep/search results** and RAG document contexts — already minimal.
- JSON: arrays under 5 items, content under 200 tokens, bool-only arrays,
  objects with no array values, nesting deeper than 5 levels.

Code mostly passing through is intentional: code is fetched because someone
wants to work with it, and compressing function bodies would remove exactly
what they need. Savings on code come from the live zone — newest tool outputs —
never from dropping history or stripping bodies.

## Safety gates

Every compressor fails **open**: on any problem it returns the original content
unchanged. Malformed JSON passes through with no error raised. NaN/Infinity are
filtered out before statistics. Blocks under `min_input_words` come back
byte-identical.

## Where savings actually come from

| Content | Single-sample compression |
|---|---|
| JSON arrays of numbers | ~97% |
| JSON arrays of strings | ~95% |
| JSON arrays of dicts | ~52% |
| Mixed-type arrays | ~45% |
| Plain text | needs the optional ML/Kompress path |
| Code, RAG contexts | passthrough |

Directional single samples, not a benchmark suite. For the user's own number:
`headroom savings`, or the seeded harness
`uv run python benchmarks/index_proof_table.py --seed 20260902`.

Good fit: long agent sessions with accumulated tool output, JSON-heavy
workflows, build/test output, multi-tool agents. Poor fit: short conversational
exchanges (overhead can exceed savings), code-only sessions, single-turn
requests with no accumulated context.

## Install problems

| Symptom | Cause and fix |
|---|---|
| `headroom: command not found` after `npm install` | The npm package is the TS SDK only. Install the PyPI package for the CLI |
| `CERTIFICATE_VERIFY_FAILED` during pip install | Corporate SSL inspection; `maturin` can't fetch rustup. Install Rust first (`rustup default stable`) or force a wheel: `pip install --only-binary headroom-ai headroom-ai` |
| C++ compilation error | You pulled `[vector]` (HNSW). Drop it or install a toolchain |
| pipx installed an old version | Pin the interpreter: `pipx install --python python3.13 "headroom-ai[all]"` |
| `ModuleNotFoundError: headroom` | Wrong interpreter — the CLI and your app are in different envs |
| Dashboard dollar figure stuck at `$0.00` | Python 3.14+; LiteLLM can't install there. `pipx reinstall headroom-ai --python python3.13`, restart the proxy |
| MCP host can't launch `headroom` | It doesn't inherit your `PATH`. Use the absolute path from `command -v headroom` |
| Windows: Defender blocks `sg.exe` | ast-grep bundled binary — allowlist it or skip the bundled tools |

## Proxy and agent issues

- **Connection refused** — nothing is listening on 8787. `headroom doctor`
  checks routing end to end, which a version check does not.
- **Claude Code's context window looks larger through the proxy** — expected;
  see the upstream troubleshooting page.
- **Claude Code caps at 200k through the proxy** — a custom `ANTHROPIC_BASE_URL`
  drops the `context-1m` beta header. Use `headroom wrap claude --1m`.
- **Local context inflates through the proxy** — Claude Code loads every tool
  schema eagerly behind a custom base URL. Use `--tool-search`.
- **Remote Control / server-managed settings unavailable** — a known consequence
  of a custom `ANTHROPIC_BASE_URL`.
- **An exported env var has no effect** — a reused proxy snapshotted its
  environment at launch. `headroom wrap` hot-syncs over `POST /admin/runtime-env`;
  otherwise restart the proxy.
- **Compression too aggressive** — raise thresholds, set `headroom_keep_turns`,
  or mark specific tools `{"skip_compression": True}` via `headroom_tool_profiles`.

## Debugging techniques

- `headroom inspect` — original vs compressed for recent proxy requests.
- `headroom perf` — proxy performance from logs.
- `client.chat.completions.simulate()` — returns the transform plan with no API
  call. The honest way to measure your own traffic.
- `headroom audit-reads` — find Read-tool traffic worth compressing.
