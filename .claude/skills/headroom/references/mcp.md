# Headroom MCP server

Compression, retrieval and stats as MCP tools for any MCP host. No proxy
required — but the proxy and the MCP server complement each other: the proxy
compresses *all* traffic automatically, the MCP tools let the model compress
and retrieve *on demand*.

```bash
pip install "headroom-ai[mcp]"      # tools only
pip install "headroom-ai[proxy]"    # with the proxy
```

## Register with Claude Code

```bash
headroom mcp install
headroom mcp install --proxy-url http://host:9000   # non-default proxy
headroom mcp install --force                        # overwrite existing
headroom mcp status
headroom mcp uninstall
headroom mcp reconcile
```

For both automatic and on-demand compression, run the proxy too:

```bash
# terminal 1
headroom proxy
# terminal 2
ANTHROPIC_BASE_URL=http://127.0.0.1:8787 claude
```

## Tools

### `headroom_compress`

Shrink large content before reasoning over it.

- **`content`** (required) — text to compress: files, JSON, logs, search results.

Returns `compressed`, `hash`, `original_tokens`, `compressed_tokens`,
`savings_percent`, `transforms` (which algorithms fired, e.g. `router:search:0.27`).

The original is stored locally for **1 hour**. Keep the `hash` if there is any
chance the full text is needed later.

### `headroom_retrieve`

Get the original back.

- **`hash`** (required) — from a previous compression.
- **`query`** (optional) — search inside the original and return only matching items.

Returns `original_content` (full) or `results` (filtered), plus `source`
(`"local"` or `"proxy"`). Retrieval checks the local store first, then the
proxy's; hashes from either work transparently.

### `headroom_stats`

Session statistics: `compressions`, `retrievals`, `tokens_saved`,
`savings_percent`, `estimated_cost_saved_usd`, `recent_events` (last 10),
`sub_agents`, `combined`, and `proxy` (request count, cache hits, cost saved —
only if a proxy is running). Sub-agent stats aggregate through
`~/.headroom/session_stats.jsonl`.

## Host configuration

```json
{
  "mcpServers": {
    "headroom": {
      "type": "stdio",
      "command": "headroom",
      "args": ["mcp", "serve", "--proxy-url", "http://127.0.0.1:8787"]
    }
  }
}
```

One stdio server per proxy instance — register `headroom-azure` pointing at
`:8788` alongside the default if you run two.

**`command = "headroom"` only works when the host starts with a `PATH` that
includes the uv tool directory.** Codex and several other hosts do not inherit
an interactive shell `PATH`; use the absolute path from `command -v headroom`:

```toml
[mcp_servers.headroom]
command = "/Users/you/.local/bin/headroom"
args = ["mcp", "serve"]
```

Streamable HTTP instead of stdio:

```bash
headroom mcp serve --transport http --host 127.0.0.1 --port 8788 --path /mcp
headroom mcp serve --debug
```

Registry authors should consume the canonical `server.json` in the repo root
rather than reconstructing the `headroom mcp serve` contract from prose.
