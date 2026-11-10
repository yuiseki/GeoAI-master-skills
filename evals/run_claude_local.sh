#!/usr/bin/env bash
# Run Claude Code (claude -p) on the host, on a workdir made by prepare_workdir.py.
#
# Not in Docker: Claude Code signs in with the user's subscription (OAuth) from $HOME/.claude, and --bare, which
# would skip all of the user's setup, takes only an API key (paid). So the condition is set with flags instead:
#   --setting-sources project   no user settings, so none of the user's hooks, plugins or permissions
#   --strict-mcp-config         no MCP servers
#   --no-session-persistence    nothing saved for a later session
# and by the place of the workdir: Claude Code reads every CLAUDE.md in the folders above it and the user's
# $HOME/.claude/CLAUDE.md. Both are refused here, so a run never carries rules nobody chose. --context FILE puts
# FILE as CLAUDE.md in the folder just above the workdir, for runs that measure such rules (keep that folder for
# this run only). Auto-memory is kept per folder, so a new workdir starts with none. Claude Code reads the
# workdir's AGENTS.md by itself (a built-in plugin, cc-plugin-agents-md, seen in 2.1.321).
#
# Only reading tools are allowed (the request is to choose the steps without running anything); a denied call
# shows in the log as a permission_denied event.
# This is not the condition of the Docker runners, whose shell is free inside the container: Claude Code also
# refuses any path outside the workdir (ls ..), and on 2026-11-10 one run gave up after its first ls was refused and
# answered without opening a skill. Claude Code's own sandbox, which would free the shell safely, does not start on
# this host (Ubuntu's AppArmor stops bubblewrap's user namespaces), and allowing all of Bash lets it write outside.
#
# Usage:
#   evals/run_claude_local.sh [--prompt FILE] [--context FILE] [--dry-run] WORKDIR [claude args...]
# Arguments after WORKDIR go to claude as they are, e.g. --model claude-sonnet-5-5.
set -euo pipefail

TOOLS="Read,Grep,Glob,Bash(cat:*),Bash(sed:*),Bash(head:*),Bash(tail:*),Bash(ls:*),Bash(grep:*),Bash(find:*),Bash(wc:*)"

dry=0 prompt="" context=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) dry=1; shift ;;
    --prompt) prompt=$2; shift 2 ;;
    --context) context=$2; shift 2 ;;
    *) break ;;
  esac
done
[[ $# -ge 1 ]] || { echo "usage: $0 [--prompt FILE] [--context FILE] [--dry-run] WORKDIR [claude args...]" >&2; exit 2; }
work=$(cd "$1" && pwd); shift

if [[ -e $HOME/.claude/CLAUDE.md ]]; then
  echo "refusing: $HOME/.claude/CLAUDE.md would be read by every run" >&2; exit 2
fi
d=$(dirname "$work")
while :; do
  if [[ -e $d/CLAUDE.md ]]; then
    echo "refusing: $d/CLAUDE.md is above the workdir and would be read (move the workdir, or use --context)" >&2
    exit 2
  fi
  [[ $d == / ]] && break
  d=$(dirname "$d")
done
if [[ -n $context ]]; then
  cp "$context" "$(dirname "$work")/CLAUDE.md"
fi

cmd=(claude -p --setting-sources project --strict-mcp-config --no-session-persistence
     --output-format stream-json --verbose --allowedTools "$TOOLS" "$@")
if [[ $dry == 1 ]]; then
  echo "cd $work && ${cmd[*]}${prompt:+ < $prompt}"
  exit 0
fi
cd "$work"
if [[ -n $prompt ]]; then
  exec "${cmd[@]}" < "$prompt"
fi
exec "${cmd[@]}"
