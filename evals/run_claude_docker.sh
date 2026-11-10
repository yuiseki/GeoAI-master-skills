#!/usr/bin/env bash
# Run Claude Code (claude -p) inside Docker on a workdir made by prepare_workdir.py.
#
# Same image toolchain and the same hard limits as run_codex_docker.sh, so the Claude, Codex and Gemini evals
# compare models, not environments. The container is the sandbox: the shell is free inside it
# (--dangerously-skip-permissions), and only the workdir is mounted, so none of the user's setup reaches the run
# (no ~/.claude settings, hooks, plugins, memory or CLAUDE.md; --strict-mcp-config, no MCP servers).
# Claude Code reads the workdir's AGENTS.md by itself (a built-in plugin, cc-plugin-agents-md, in 2.1.321).
#
# Auth: a long-lived token of the subscription, made once on the host with `claude setup-token` and saved as
# $EVAL_CLAUDE_HOME/oauth_token (mode 600). It is passed by the name of the variable CLAUDE_CODE_OAUTH_TOKEN, so it
# never appears in a command line or a --dry-run.
#
# --context FILE mounts FILE read-only as /CLAUDE.md, above /work: Claude Code reads it as a CLAUDE.md, the way
# the user's global rules reach an everyday session. For runs that measure such rules.
#
# Usage:
#   evals/run_claude_docker.sh [--prompt FILE] [--context FILE] [--dry-run] WORKDIR [claude args...]
# Arguments after WORKDIR go to claude as they are, e.g. --model claude-sonnet-5-5.
#
# Environment (defaults are the eval conditions):
#   EVAL_IMAGE=geoai-master-skills-evals-claude  EVAL_CPUSET=0-7  EVAL_CPUS=8  EVAL_MEMORY=16g  EVAL_PIDS=512
#   EVAL_CLAUDE_HOME=$HOME/.claude-evals   (never $HOME/.claude)
set -euo pipefail

IMAGE=${EVAL_IMAGE:-geoai-master-skills-evals-claude}
CPUSET=${EVAL_CPUSET:-0-7}
CPUS=${EVAL_CPUS:-8}
MEMORY=${EVAL_MEMORY:-16g}
PIDS=${EVAL_PIDS:-512}
CLAUDE_HOME_HOST=${EVAL_CLAUDE_HOME:-$HOME/.claude-evals}

dry=0 prompt="" context=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) dry=1; shift ;;
    --prompt) prompt=${2:?--prompt needs a file}; shift 2 ;;
    --context) context=${2:?--context needs a file}; shift 2 ;;
    --) shift; break ;;
    -*) echo "unknown option $1" >&2; exit 2 ;;
    *) break ;;
  esac
done
[[ $# -ge 1 ]] || { echo "usage: $0 [--prompt FILE] [--context FILE] [--dry-run] WORKDIR [claude args...]" >&2; exit 2; }
workdir=$(realpath "$1"); shift
[[ -d "$workdir" ]] || { echo "$workdir is not a directory" >&2; exit 2; }
if [[ -e "$workdir/evals" || -e "$workdir/.git" ]]; then
  echo "$workdir contains evals/ or .git; prepare it with evals/prepare_workdir.py" >&2; exit 2
fi
if [[ -e "$CLAUDE_HOME_HOST" && -e "$HOME/.claude" && "$(realpath "$CLAUDE_HOME_HOST")" == "$(realpath "$HOME/.claude")" ]]; then
  echo "EVAL_CLAUDE_HOME must not be the everyday \$HOME/.claude" >&2; exit 2
fi
TOKEN_FILE="$CLAUDE_HOME_HOST/oauth_token"
if [[ ! -s "$TOKEN_FILE" ]]; then
  echo "No token in $TOKEN_FILE. Make one with \`claude setup-token\` and save it there (chmod 600)." >&2; exit 2
fi
CLAUDE_CODE_OAUTH_TOKEN=$(tr -d '[:space:]' < "$TOKEN_FILE")
export CLAUDE_CODE_OAUTH_TOKEN

# Hard limits. --memory-swap equal to --memory leaves no swap to escape into.
docker_args=(
  run --rm
  --cpuset-cpus="$CPUSET" --cpus="$CPUS"
  --memory="$MEMORY" --memory-swap="$MEMORY"
  --pids-limit="$PIDS"
  --cap-drop=ALL --security-opt=no-new-privileges
  -e CLAUDE_CODE_OAUTH_TOKEN
  -v "$workdir":/work
)
[[ -n "$context" ]] && docker_args+=(-v "$(realpath "$context")":/CLAUDE.md:ro)

claude_args=(-p --output-format stream-json --verbose --dangerously-skip-permissions
             --strict-mcp-config --no-session-persistence)
cmd=(docker "${docker_args[@]}" -w /work -i "$IMAGE" claude "${claude_args[@]}" "$@")

if [[ $dry -eq 1 ]]; then echo "${cmd[*]}${prompt:+ < $prompt}"; exit 0; fi
if [[ -n "$prompt" ]]; then exec "${cmd[@]}" < "$(realpath "$prompt")"; fi
exec "${cmd[@]}"
