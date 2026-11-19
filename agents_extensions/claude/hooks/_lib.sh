#!/bin/bash
set -euo pipefail

detect_primary_dir() {
  local lib_dir primary project_dir

  primary=$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {sub(/^worktree /, ""); print; exit}' 2>/dev/null || true)
  if [ -n "$primary" ]; then
    printf '%s\n' "$primary"
    return 0
  fi

  project_dir="${CLAUDE_PROJECT_DIR:-}"
  if [ -n "$project_dir" ] && [ -d "$project_dir" ]; then
    printf '%s\n' "$project_dir"
    return 0
  fi

  if lib_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd -P); then
    if project_dir=$(cd "$lib_dir/../.." 2>/dev/null && pwd -P); then
      printf '%s\n' "$project_dir"
      return 0
    fi
  fi
}

normalize_path() {
  local path
  path=$1

  (cd "$path" 2>/dev/null && pwd -P) || printf '%s\n' "$path"
}

is_inside_primary() {
  local cwd primary
  cwd=$(normalize_path "$1")
  primary=$(normalize_path "$PRIMARY_DIR")

  case "$cwd/" in
    "$primary/.worktrees/"*)
      return 1
      ;;
  esac

  if [ "$cwd" = "$primary" ]; then
    return 0
  fi

  case "$cwd/" in
    "$primary/"*)
      return 0
      ;;
  esac

  return 1
}

read_tool_payload() {
  jq -er '[(.tool_input.command // ""), (.tool_input.cwd // .cwd // env.PWD)] | @tsv'
}

deny() {
  local allowlist_hint memory_ref rule_name
  rule_name=$1
  allowlist_hint=$2
  memory_ref=$3

  printf '[hook denied] %s\n  allowlist: %s\n  see: memory/%s\n' \
    "$rule_name" \
    "$allowlist_hint" \
    "$memory_ref" >&2
  exit 2
}
