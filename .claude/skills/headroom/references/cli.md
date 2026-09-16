# Headroom CLI

`headroom --version` · `-?` works as a help alias everywhere in the tree.
Settings from `settings.json` are applied to the process environment before
flags are parsed; explicit shell exports stay authoritative.

## Command map

| Command | What it does |
|---|---|
| `headroom proxy` | Start the compression proxy (default port 8787) |
| `headroom dashboard` | Open the savings dashboard — **requires a running proxy** |
| `headroom wrap <agent>` | Start proxy + configure + launch a coding agent |
| `headroom unwrap <agent>` | Undo durable wrapping |
| `headroom deploy` | Turnkey local deployment + configure detected tools |
| `headroom init <agent>` | Install durable integrations (`claude`, `copilot`, `codex`, `openclaw`) |
| `headroom install …` | Manage persistent deployments: `apply`, `status`, `start`, `stop`, `restart`, `remove` |
| `headroom mcp …` | `install`, `uninstall`, `status`, `reconcile`, `serve` |
| `headroom memory …` | `list`, `show`, `stats`, `edit`, `delete`, `prune`, `purge`, `reindex`, `export`, `import`, `repair-supersession` |
| `headroom doctor` | Health check — confirms proxy and client routing actually work |
| `headroom savings` | Durable compression savings over time |
| `headroom output-savings` | Estimated/measured output-token reduction |
| `headroom agent-savings` | Render or verify Codex/Claude/Cursor savings settings |
| `headroom inspect` | Original vs compressed for recent proxy requests |
| `headroom audit-reads` | Audit Read-tool traffic for compression opportunities |
| `headroom perf` | Analyze proxy performance from logs |
| `headroom learn` | Mine failed sessions into context-file corrections |
| `headroom evals …` | Memory, compression-robustness and retention evals |
| `headroom capture …` | Capture/compare network traffic for investigations |
| `headroom rollout …` | Inspect runtime feature-rollout policy (not package releases) |
| `headroom recover codex` | Recover Codex state left in a temporary Headroom home |
| `headroom copilot-auth …` | Copilot OAuth token management |
| `headroom update` | Upgrade in place; `--check`, `--pre` |
| `headroom sg` / `diff` / `loc` | Bundled ast-grep / difftastic / scc passthrough; `headroom tools list` |

`headroom init hook ensure` is the hidden helper the Claude Code plugin hooks
call — it checks for a matching durable deployment and starts it if needed.

## proxy

```bash
headroom proxy --port 8787          # HEADROOM_PORT
headroom proxy --host 127.0.0.1     # HEADROOM_HOST
headroom proxy --mode token         # see configuration.md — a profile can override this
headroom proxy --telemetry          # anonymous telemetry, off by default
```

Point any OpenAI/Anthropic-compatible client at `http://127.0.0.1:8787`.
The proxy prints an "update available" notice at startup at most once a day,
in the background; `HEADROOM_UPDATE_CHECK=off` opts out.

## wrap

```bash
headroom wrap claude
headroom wrap codex | copilot | cursor | aider | opencode | cline | continue \
                    | goose | openhands | openclaw | vibe | omp | zcode | grok | kimi
headroom wrap vscode           # GitHub Copilot in VS Code
headroom wrap vscode-claude    # Claude Code extension in VS Code
headroom unwrap claude         # also: copilot, codex, grok, kimi, omp, opencode, openclaw, zcode
```

Wrapping starts a local proxy, installs [Serena](https://github.com/oraios/serena)
for semantic code navigation, and launches the agent routed through Headroom.
**Serena is registered at user scope** (`~/.claude.json` for Claude Code), so it
stays in your other projects until `headroom unwrap`. Skip it with
`--code-memory none`.

Launch a wrapped session every time — that is what runs the setup.

### `wrap claude` flags

| Flag | Effect |
|---|---|
| `--port N` | Proxy port (default 8787) |
| `--memory` | Persistent cross-session memory |
| `--code-memory serena\|none` | Code-memory MCP choice |
| `--code-graph` | Proxy's live code-graph file watcher for this project |
| `--learn` | Live traffic learning (patterns saved to `MEMORY.md`) |
| `--tool-search MODE` | Keep Claude Code's on-demand tool loading through the proxy. `true` (default), `auto`, `auto:N`, `false`. Without it a custom `ANTHROPIC_BASE_URL` makes Claude Code load every tool schema eagerly, inflating local context |
| `--1m` | Preserve the 1M context window — behind a custom base URL Claude Code drops the `context-1m` beta header and caps at 200k; this sets `ANTHROPIC_MODEL=<opus>[1m]` on the launched process |
| `--no-mcp` | Skip Headroom MCP registration (compression markers become unactionable) |
| `--no-proxy` | Use an existing proxy instead of starting one |
| `--backend` / `--region` | API backend (`anthropic` default, `litellm-vertex_ai`, …) and cloud region. For Vertex prefer `CLAUDE_CODE_USE_VERTEX=1` over a litellm backend |
| `-v` | Verbose |

Trailing args after the flags pass through to the agent:
`headroom wrap copilot --subscription -- --model gpt-4o`.

### Runtime env hot-sync

Switches like `HEADROOM_OUTPUT_SHAPER` are read live per request, but a proxy
that `wrap` **reused** rather than started snapshotted its environment at launch
and will not see a later `export`. `headroom wrap` hot-syncs current settings to
a running proxy over a loopback `POST /admin/runtime-env` — no restart, no
dropped requests. On a shared proxy these overrides are global; last explicit
setting wins.

## learn

```bash
headroom learn                      # dry run, current project
headroom learn --apply              # write the recommendations
headroom learn --all                # every discovered project
headroom learn --target CLAUDE.md   # team-shared file instead of CLAUDE.local.md
headroom learn --agent auto         # claude | codex | gemini | grok | auto
headroom learn --model claude-sonnet-4-6   # analysis model; auto-detected from API keys
headroom learn -j 4                 # parallel session scanners (default: min(cpu, 8))
headroom learn --main-only          # skip nested subagent/workflow transcripts
headroom learn --verbosity [--llm-judge] [--apply]   # learn OUTPUT terseness instead
```

Default target is `CLAUDE.local.md` (personal, gitignored). Other agents map to
`AGENTS.md`, `GEMINI.md`, `GROK.md`.

## update

```bash
headroom update          # detects pip / pip --user / pipx / uv tool and upgrades
headroom update --check  # report latest release only
headroom update --pre    # include pre-releases
```

For git checkouts, editable installs, Docker images and PEP 668 system Pythons it
prints the correct manual step instead of guessing.
