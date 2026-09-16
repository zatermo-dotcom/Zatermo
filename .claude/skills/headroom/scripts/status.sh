#!/usr/bin/env bash
# Report whether Headroom is actually live: CLI, proxy, MCP registration.
# Read-only — starts nothing, changes nothing.
set -uo pipefail

PORT="${HEADROOM_PORT:-8787}"

echo "== CLI =="
if command -v headroom >/dev/null 2>&1; then
  printf '  path    %s\n' "$(command -v headroom)"
  printf '  version %s\n' "$(headroom --version 2>&1 | head -1)"
else
  echo "  not on PATH — the plugin hooks and MCP server cannot run"
  echo '  install: uv tool install --python 3.13 "headroom-ai[all]"'
  exit 1
fi

echo
echo "== Python =="
printf '  %s\n' "$(python3 -c 'import sys; print(sys.version.split()[0])' 2>/dev/null || echo unknown)"
echo "  (3.14+ keeps token savings but leaves the dashboard dollar tile at \$0.00)"

echo
echo "== Proxy (port $PORT) =="
if curl -fsS --max-time 3 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "  responding — dashboard: http://127.0.0.1:${PORT}/dashboard"
else
  echo "  not responding — start one with 'headroom proxy' or 'headroom wrap <agent>'"
fi

echo
echo "== MCP registration =="
headroom mcp status 2>&1 | sed 's/^/  /'

echo
echo "== Routing =="
echo "  run 'headroom doctor' for the end-to-end check"
