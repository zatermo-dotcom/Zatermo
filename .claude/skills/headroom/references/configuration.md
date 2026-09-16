# Configuration

Precedence: explicit flag → environment variable → `settings.json` → default.
The CLI applies `settings.json` to the process environment before parsing, and
shell exports stay authoritative over the stored file.

## Savings profiles

`HEADROOM_SAVINGS_PROFILE` seeds the whole compression posture — proxy mode,
keep-ratio, which messages get compressed, `force_kompress` — at proxy startup.
Read by `headroom proxy` and by `headroom wrap` subprocesses. Unset → `coding`.

| Profile | Target | Mode | Notes |
|---|---|---|---|
| `coding` | emergent ~50% | `cache` | **Default.** Delta-only compression, ~0 prefix-cache busts. `protect_reads=True` — file reads are never lossy-compressed. What `headroom wrap` uses |
| `balanced` | ~70% | `token` | Standard lossless pipeline, 30% keep-ratio, protects 4 recent turns |
| `agent-90` | ~90% | `token` | Forces Kompress at a 0.10 keep-ratio, ignores the lossless path. Compresses user *and* system messages |
| `general` | emergent ~60% | `token` | Non-coding chat; no turn protection, does not compress user/system messages |

An unrecognized value logs a warning and falls back to `coding` — a bad profile
name never stops the proxy from starting.

## Cache mode vs token mode

- `--mode cache` (default) freezes prior turns so the provider's prefix cache
  survives. Savings show up as cheap cached-prefix reads, not as a big
  compression number.
- `--mode token` maximizes visible compression by rewriting prior turns, which
  costs prefix-cache hits.

**A profile's `proxy_mode` overrides `--mode`.** Under the default `coding`
profile, `--mode token` has no effect — switch profile instead. Mode precedence
otherwise: explicit `--mode` → `HEADROOM_MODE` (seeded by the profile) → `cache`.

These are *not* the SDK modes. `HeadroomClient(default_mode=…)` and per-request
`headroom_mode=…` take `audit` (observe and log only), `optimize` (apply
transforms) or `simulate` (return the plan without calling the API). The proxy
accepts none of those three.

## Environment variables

**Server**: `HEADROOM_HOST`, `HEADROOM_PORT`, `HEADROOM_WORKERS`,
`HEADROOM_MODE`, `HEADROOM_LIMIT_CONCURRENCY`, `HEADROOM_MAX_CONNECTIONS`,
`HEADROOM_MAX_KEEPALIVE`, `HEADROOM_KEEPALIVE_EXPIRY`, `HEADROOM_REQUEST_TIMEOUT`,
`HEADROOM_HTTP_PROXY`, `HEADROOM_UPSTREAM_ALLOWED_HOSTS`,
`HEADROOM_STRIP_INTERNAL_HEADERS` / `HEADROOM_PROXY_STRIP_INTERNAL_HEADERS`.

**Client / SDK**: `HEADROOM_BASE_URL`, `HEADROOM_API_KEY`.

**Compression**: `HEADROOM_SAVINGS_PROFILE`, `HEADROOM_PROXY_COMPRESSION`,
`HEADROOM_BUDGET`, `HEADROOM_MODEL_LIMITS`, `HEADROOM_LOSSLESS_COMPACTION`,
`HEADROOM_DEDUPE`, `HEADROOM_COLD_RECOMPACT`, `HEADROOM_THINKING_COMPACT`,
`HEADROOM_THINKING_COMPACT_KEEP_LAST`, `HEADROOM_KOMPRESS_BACKEND`,
`HEADROOM_KOMPRESS_ENDPOINT` (+ `_TOKEN`), `HEADROOM_EMBEDDER_RUNTIME`
(`pytorch_mps` for Apple-GPU offload), `HEADROOM_MAGIKA_INIT_TIMEOUT_SECS`.

**Output shaping**: `HEADROOM_OUTPUT_SHAPER=1` (off by default),
`HEADROOM_OUTPUT_HOLDOUT=0.1` (hold out 10% of conversations unshaped so the
dashboard's Output Tokens Saved reads `measured` rather than `estimated`).

**Paths and state**: `HEADROOM_CONFIG_DIR`, `HEADROOM_WORKSPACE`,
`HEADROOM_WORKSPACE_DIR`, `HEADROOM_SAVINGS_PATH`, `HEADROOM_TOIN_PATH`,
`HEADROOM_SUBSCRIPTION_STATE_PATH`, `HEADROOM_STATELESS`,
`HEADROOM_MEMORY_INJECTION_MODE`, `HEADROOM_CACHE_TTL_LEARN`.

**Routing / rollout**: `HEADROOM_MODEL_ROUTER_ENABLED`, `HEADROOM_MODEL_ROUTES`,
`HEADROOM_ROLLOUT_CHANNEL` (`stable` default, also `beta`/`canary`/`dev`),
`HEADROOM_FEATURES`, `HEADROOM_DISABLE_FEATURES` (disable always wins),
`HEADROOM_UNSAFE_ALLOW_UNSTABLE_FEATURES` (break-glass only).

**Misc**: `HEADROOM_TELEMETRY` (anonymous, off by default; `on` to opt in),
`HEADROOM_UPDATE_CHECK=off`, `HEADROOM_BETA_HEADER_STICKY`,
`HEADROOM_PROXY_BETA_HEADER_STICKY`, `HEADROOM_BETA_TRACKER_MAX_SESSIONS`,
`HEADROOM_PERIODIC_TOIN_STATS`, `HEADROOM_PROXY_PYTHON_FORWARDER_MODE`.

## Per-request overrides (Python)

```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[...],
    headroom_mode="audit",                 # override the client default
    headroom_output_buffer_tokens=8000,    # reserve more room for output
    headroom_keep_turns=5,                 # keep last N turns uncompressed
    headroom_tool_profiles={"important_tool": {"skip_compression": True}},
)
```

TypeScript takes the same idea through `compress(messages, { model, tokenBudget, timeout })`.

## Install extras

`[all]` covers the core stack: `[proxy]`, `[mcp]`, `[ml]` (Kompress-v2-base),
`[code]` (tree-sitter), `[memory]`, `[relevance]`, `[image]`, `[evals]`.
Not in `[all]`: `[vector]` (HNSW, needs a C++ toolchain), `[pytorch-mps]`, and
the framework adapters — `[langchain]`, `[agno]`, `[strands]`, `[anyllm]`,
`[bedrock]`. Python 3.10+.

x86/x86_64 note: the ONNX-backed paths (Magika detection, embedding relevance)
need **AVX2**. Without it Headroom falls back to BM25 relevance and heuristic
detection rather than crashing. arm64/Apple Silicon needs no AVX2.
