#!/usr/bin/env bash
#
# awesome-copilot installer
# -------------------------
# Installs GitHub Copilot customizations from github/awesome-copilot
# (agents, instructions, skills, hooks, workflows, plugins) into a project's
# `.github/` directory.
#
# Usage:
#   ./install.sh list [CATEGORY]              List available items
#   ./install.sh search TERM                  Search item names/descriptions
#   ./install.sh install CATEGORY/NAME ...    Install one or more items
#   ./install.sh install-all CATEGORY         Install every item in a category
#   ./install.sh remove CATEGORY/NAME ...     Remove installed items
#   ./install.sh installed                    Show what this project has installed
#   ./install.sh update                       Refresh the local cache of the repo
#
# Options (may appear anywhere):
#   --dest DIR    Target project root       (default: current directory)
#   --ref  REF    awesome-copilot git ref   (default: main)
#   --force       Overwrite existing files without prompting
#   -h, --help    Show this help
#
# Categories: agents  instructions  skills  hooks  workflows  plugins
#
set -euo pipefail

REPO_URL="https://github.com/github/awesome-copilot.git"
CACHE_DIR="${AWESOME_COPILOT_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/awesome-copilot}"
CATEGORIES=(agents instructions skills hooks workflows plugins)

DEST="."
REF="main"
FORCE=0

# ---- pretty output --------------------------------------------------------
if [ -t 1 ]; then
  C_BOLD=$'\033[1m'; C_DIM=$'\033[2m'; C_GRN=$'\033[32m'
  C_YEL=$'\033[33m'; C_RED=$'\033[31m'; C_RST=$'\033[0m'
else
  C_BOLD=""; C_DIM=""; C_GRN=""; C_YEL=""; C_RED=""; C_RST=""
fi
info()  { printf '%s%s%s\n' "$C_DIM" "$*" "$C_RST"; }
ok()    { printf '%s✓%s %s\n' "$C_GRN" "$C_RST" "$*"; }
warn()  { printf '%s!%s %s\n' "$C_YEL" "$C_RST" "$*" >&2; }
die()   { printf '%s✗ %s%s\n' "$C_RED" "$*" "$C_RST" >&2; exit 1; }

usage() { sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'; }

# ---- argument parsing -----------------------------------------------------
ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --dest)  DEST="${2:?--dest needs a value}"; shift 2 ;;
    --ref)   REF="${2:?--ref needs a value}"; shift 2 ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    --) shift; while [ $# -gt 0 ]; do ARGS+=("$1"); shift; done ;;
    -*) die "unknown option: $1" ;;
    *)  ARGS+=("$1"); shift ;;
  esac
done
[ ${#ARGS[@]} -gt 0 ] || { usage; exit 1; }

command -v git >/dev/null 2>&1 || die "git is required but not found on PATH"

# ---- cache management ------------------------------------------------------
sync_cache() {
  if [ -d "$CACHE_DIR/.git" ]; then
    info "Updating cache ($REF) ..."
    git -C "$CACHE_DIR" fetch --depth 1 origin "$REF" >/dev/null 2>&1 \
      || die "failed to fetch ref '$REF' from awesome-copilot"
    git -C "$CACHE_DIR" checkout -q FETCH_HEAD
  else
    info "Cloning awesome-copilot ($REF) into cache ..."
    mkdir -p "$(dirname "$CACHE_DIR")"
    git clone --depth 1 --branch "$REF" "$REPO_URL" "$CACHE_DIR" >/dev/null 2>&1 \
      || git clone --depth 1 "$REPO_URL" "$CACHE_DIR" >/dev/null 2>&1 \
      || die "failed to clone awesome-copilot"
  fi
}

ensure_cache() { [ -d "$CACHE_DIR/.git" ] || sync_cache; }

is_category() {
  local c
  for c in "${CATEGORIES[@]}"; do [ "$c" = "$1" ] && return 0; done
  return 1
}

# Resolve a "CATEGORY/NAME" spec to the source path inside the cache.
# NAME may be given with or without its extension.
resolve_src() {
  local cat="$1" name="$2" base="$CACHE_DIR/$1"
  [ -d "$base" ] || die "unknown category: $cat"
  local cand
  for cand in "$base/$name" "$base/$name.md" \
              "$base/$name.agent.md" "$base/$name.instructions.md" \
              "$base/$name.prompt.md" "$base/$name.chatmode.md"; do
    [ -e "$cand" ] && { printf '%s' "$cand"; return 0; }
  done
  return 1
}

manifest_path() { printf '%s/.github/.awesome-copilot-manifest.txt' "$DEST"; }

record() { # category/name relpath
  local mf; mf="$(manifest_path)"
  mkdir -p "$(dirname "$mf")"
  grep -qxF "$1" "$mf" 2>/dev/null || printf '%s\n' "$1" >> "$mf"
}
unrecord() {
  local mf; mf="$(manifest_path)"
  [ -f "$mf" ] || return 0
  grep -vxF "$1" "$mf" > "$mf.tmp" 2>/dev/null || true
  mv "$mf.tmp" "$mf"
}

# ---- commands -------------------------------------------------------------
cmd_list() {
  ensure_cache
  local cats=("${CATEGORIES[@]}")
  [ $# -ge 1 ] && { is_category "$1" || die "unknown category: $1"; cats=("$1"); }
  local cat entry n
  for cat in "${cats[@]}"; do
    [ -d "$CACHE_DIR/$cat" ] || continue
    n=$(find "$CACHE_DIR/$cat" -mindepth 1 -maxdepth 1 | wc -l | tr -d ' ')
    printf '\n%s%s%s (%s)\n' "$C_BOLD" "$cat" "$C_RST" "$n"
    for entry in "$CACHE_DIR/$cat"/*; do
      [ -e "$entry" ] || continue
      printf '  %s\n' "$(basename "$entry")"
    done
  done
}

cmd_search() {
  ensure_cache
  local term="${1:?search needs a term}"
  info "Searching for '$term' ..."
  local cat entry name desc
  for cat in "${CATEGORIES[@]}"; do
    [ -d "$CACHE_DIR/$cat" ] || continue
    for entry in "$CACHE_DIR/$cat"/*; do
      [ -e "$entry" ] || continue
      name="$(basename "$entry")"
      desc=""
      if [ -f "$entry" ]; then
        desc="$(grep -m1 -i 'description:' "$entry" 2>/dev/null || true)"
      elif [ -f "$entry/SKILL.md" ]; then
        desc="$(grep -m1 -i 'description:' "$entry/SKILL.md" 2>/dev/null || true)"
      fi
      if printf '%s %s' "$name" "$desc" | grep -qi -- "$term"; then
        printf '  %s%s/%s%s  %s%s%s\n' "$C_BOLD" "$cat" "$name" "$C_RST" \
          "$C_DIM" "$(printf '%s' "$desc" | sed 's/^ *description: *//I' | cut -c1-80)" "$C_RST"
      fi
    done
  done
}

install_one() { # CATEGORY/NAME
  local spec="$1" cat name src target
  case "$spec" in
    */*) cat="${spec%%/*}"; name="${spec#*/}" ;;
    *)   die "expected CATEGORY/NAME, got '$spec'" ;;
  esac
  is_category "$cat" || die "unknown category: $cat"
  src="$(resolve_src "$cat" "$name")" || die "not found: $spec"

  local destdir="$DEST/.github/$cat"
  mkdir -p "$destdir"
  target="$destdir/$(basename "$src")"

  if [ -e "$target" ] && [ "$FORCE" -ne 1 ]; then
    warn "exists, skipping (use --force): .github/$cat/$(basename "$src")"
    return 0
  fi
  rm -rf "$target"
  cp -R "$src" "$target"
  record "$cat/$(basename "$src")"
  ok "installed .github/$cat/$(basename "$src")"
}

cmd_install() {
  [ $# -ge 1 ] || die "install needs at least one CATEGORY/NAME"
  ensure_cache
  local spec
  for spec in "$@"; do install_one "$spec"; done
}

cmd_install_all() {
  local cat="${1:?install-all needs a CATEGORY}"
  is_category "$cat" || die "unknown category: $cat"
  ensure_cache
  local entry
  for entry in "$CACHE_DIR/$cat"/*; do
    [ -e "$entry" ] || continue
    install_one "$cat/$(basename "$entry")"
  done
}

cmd_remove() {
  [ $# -ge 1 ] || die "remove needs at least one CATEGORY/NAME"
  local spec cat name target
  for spec in "$@"; do
    cat="${spec%%/*}"; name="${spec#*/}"
    is_category "$cat" || die "unknown category: $cat"
    target="$DEST/.github/$cat/$name"
    if [ -e "$target" ]; then
      rm -rf "$target"; unrecord "$cat/$name"; ok "removed .github/$cat/$name"
    else
      warn "not installed: $spec"
    fi
  done
}

cmd_installed() {
  local mf; mf="$(manifest_path)"
  [ -f "$mf" ] || { info "nothing installed yet"; return 0; }
  printf '%sInstalled from awesome-copilot:%s\n' "$C_BOLD" "$C_RST"
  sed 's/^/  /' "$mf"
}

# ---- dispatch -------------------------------------------------------------
cmd="${ARGS[0]}"
rest=("${ARGS[@]:1}")
case "$cmd" in
  list)        cmd_list "${rest[@]}" ;;
  search)      cmd_search "${rest[@]}" ;;
  install)     cmd_install "${rest[@]}" ;;
  install-all) cmd_install_all "${rest[@]}" ;;
  remove)      cmd_remove "${rest[@]}" ;;
  installed)   cmd_installed ;;
  update)      sync_cache; ok "cache updated ($REF)" ;;
  *)           die "unknown command: $cmd (try --help)" ;;
esac
