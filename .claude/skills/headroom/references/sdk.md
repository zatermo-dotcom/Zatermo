# Library and framework integrations

## `compress()`

```python
from headroom import compress
from openai import OpenAI

messages = [{"role": "user", "content": "Analyze these results"}]
result = compress(messages, model="gpt-4o")

client = OpenAI()
response = client.chat.completions.create(model="gpt-4o", messages=result.messages)
print(f"Saved {result.tokens_saved} tokens ({result.compression_ratio:.0%})")
```

```ts
import { compress } from 'headroom-ai';

const result = await compress(messages, { model: 'gpt-4o', tokenBudget: 100_000 });
// pass result.messages to your LLM client; result.tokensSaved has the delta
```

Compression costs well under a millisecond — ~0.21 ms p50 on a 10K-token JSON
search result, ~1.4 ms at 100K — so it does not show up in agent latency.

## `HeadroomClient` (Python)

```python
from headroom import HeadroomClient, OpenAIProvider, HeadroomConfig, SmartCrusherConfig, CacheAlignerConfig
from openai import OpenAI

client = HeadroomClient(
    original_client=OpenAI(),
    provider=OpenAIProvider(),
    default_mode="optimize",          # "audit" is the default — it only observes
    enable_cache_optimizer=True,
    enable_semantic_cache=False,
    model_context_limits={"gpt-4o": 128000},
    config=HeadroomConfig(
        smart_crusher=SmartCrusherConfig(min_tokens_to_crush=100),   # default 200
        cache_aligner=CacheAlignerConfig(enabled=True),
    ),
    # store_url="sqlite:////absolute/path/to/headroom.db",
)
```

`default_mode` defaults to `"audit"` — observation only. A client that reports
zero savings is usually still in audit mode.

```ts
import { HeadroomClient } from 'headroom-ai';

// reads HEADROOM_BASE_URL and HEADROOM_API_KEY automatically
const client = new HeadroomClient({
  baseUrl: 'http://localhost:8787',
  apiKey: 'your-api-key',
  timeout: 30_000,
  fallback: true,    // return original messages on failure instead of throwing
  retries: 2,
});
```

## Drop-in per stack

| Stack | Hook in with |
|---|---|
| Anthropic SDK (TS) | `import { withHeadroom } from 'headroom-ai/anthropic'` → `withHeadroom(new Anthropic())` |
| OpenAI SDK (TS) | `import { withHeadroom } from 'headroom-ai/openai'` → `withHeadroom(new OpenAI())` |
| Vercel AI SDK | `wrapLanguageModel({ model, middleware: headroomMiddleware() })` |
| LiteLLM | `from headroom.integrations.litellm_callback import HeadroomCallback` → `litellm.callbacks = [HeadroomCallback()]` (works across all LiteLLM providers) |
| LangChain | `from headroom.integrations import HeadroomChatModel` → `HeadroomChatModel(ChatOpenAI(model="gpt-4o"))` |
| Agno | `HeadroomAgnoModel(your_model)` |
| Strands | Model wrapping + hook-based tool-output compression |
| ASGI apps | `app.add_middleware(CompressionMiddleware)` |
| Multi-agent | `SharedContext().put / .get` |
| Any MCP client | `headroom mcp install` |

Framework adapters are **not** in `[all]` — install `headroom-ai[langchain]`,
`[agno]`, `[strands]`, `[anyllm]`, `[bedrock]` separately.

## Cross-session memory

```python
from openai import OpenAI
from headroom import with_memory

client = with_memory(OpenAI(), user_id="alice", session_id="morning-session")
```

`with_memory()` injects relevant memories into the user message, adds an
extraction instruction to the system prompt, parses the `<memory>` block out of
the response and stores it with embeddings + FTS index — then strips the block
before returning. Extraction is **inline**, so no extra API call and no extra
latency.

Four scopes, broadest to narrowest: **user** (all sessions, all time) →
**session** → **agent** (one agent within a session) → **turn** (ephemeral).
Stores are per-project SQLite + HNSW; there is no cross-project bleed. Manage
them with `headroom memory …` (see `cli.md`).

## SharedContext

```python
from headroom import SharedContext
ctx = SharedContext()
```

Compresses what moves between agents on handoff — typically ~80% of the tokens
a replayed context would cost.
