#!/bin/bash
# Bootstrap oh-my-claudecode (OMC) for Claude Code on the web.
#
# Remote/web containers are ephemeral: the global ~/.claude install of OMC is
# wiped whenever the container is recycled. This SessionStart hook reinstalls
# and re-syncs OMC on each fresh container so the framework is always available.
#
# Idempotent and non-interactive. Web sessions only (skipped locally so it does
# not clobber a developer's own OMC install).
set -euo pipefail

# Only run in Claude Code on the web / remote environments.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Install the OMC CLI globally if it is not already present.
if ! command -v omc >/dev/null 2>&1; then
  npm install -g oh-my-claude-sisyphus@latest
fi

# Sync agents, skills, hooks and statusline into ~/.claude (quiet, non-fatal).
omc setup --quiet || true
