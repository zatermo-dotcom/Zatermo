# Headroom plugin

Source: https://github.com/headroomlabs-ai/headroom

`.claude/settings.json` registers the repo's `headroom-marketplace`
(`.claude-plugin/marketplace.json`) and enables its single plugin, `headroom`
(`plugins/headroom-agent-hooks`). Claude Code fetches the plugin from GitHub on
session start; nothing is vendored into this repo.

The plugin contributes two hooks, both running `headroom init hook ensure`
(15s timeout):

- `SessionStart` — matcher `startup|resume`
- `PreToolUse` — matcher `Bash|PowerShell`

Both need the `headroom` CLI on `PATH`. It ships only in the PyPI package:

```bash
uv tool install --python 3.13 "headroom-ai[all]"   # or: pip install "headroom-ai[all]"
headroom doctor
```

The npm `headroom-ai` package is the TypeScript SDK and provides no `headroom`
command. Without the CLI the hooks fail harmlessly, but the plugin does nothing.

Equivalent interactive install:

```
/plugin marketplace add headroomlabs-ai/headroom
/plugin install headroom@headroom-marketplace
```

Note: the repository ships no Claude Code skills (no `SKILL.md` files) — the
plugin hooks above are the whole of its Claude Code surface.
