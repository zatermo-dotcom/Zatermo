# Zatermo

Claude Code configuration for this project (skills, agents, and MCP servers).

## MCP Servers

### blender

[BlenderMCP](https://github.com/ahujasid/blender-mcp) connects Blender to Claude
through the Model Context Protocol, letting Claude inspect and drive a running
Blender scene (create/modify objects and materials, run Blender Python, fetch
assets from PolyHaven/Sketchfab/Hyper3D, and more).

Configured in [`.mcp.json`](.mcp.json) and launched with
[`uvx`](https://docs.astral.sh/uv/). It is pre-approved for this project via
[`.claude/settings.json`](.claude/settings.json), so Claude Code loads it without
prompting.

**Prerequisites**

- [uv](https://docs.astral.sh/uv/) (do **not** `pip install uv`):
  - macOS: `brew install uv`
  - Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows: see the [uv install docs](https://docs.astral.sh/uv/getting-started/installation/)
- Blender 3.0+
- Python 3.10+ (3.11 recommended)

**One-time Blender addon setup**

1. Download [`addon.py`](https://github.com/ahujasid/blender-mcp/blob/main/addon.py)
   from the BlenderMCP repo.
2. In Blender: **Edit → Preferences → Add-ons → Install…**, select `addon.py`.
3. Enable the **"Interface: Blender MCP"** checkbox.
4. In the 3D viewport, press `N` to open the sidebar, open the **BlenderMCP**
   tab, and click **Connect to Claude**.

**Usage**

With Blender open and connected, Claude can call the `blender` tools directly.
The server talks to the addon over a local socket, so Blender must be running on
the same machine as Claude Code.
