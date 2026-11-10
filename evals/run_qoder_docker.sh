#!/usr/bin/env bash
# Run the Qoder CLI (qodercli -p) inside Docker on a workdir made by prepare_workdir.py.
#
# Same image toolchain and the same hard limits as run_codex_docker.sh and run_claude_docker.sh, so the evals
# compare models, not environments. The container is the sandbox: the shell is free inside it
# (--dangerously-skip-permissions), and only the workdir is mounted, so none of the user's setup reaches the run
# (no ~/.qoder settings, sessions or memory; --strict-mcp-config, no MCP servers). The image's own
# ~/.qoder/settings.json only turns the auto-update off.
#
# Auth: a personal access token, made once at https://qoder.com/account/integrations and saved as
# $EVAL_QODER_HOME/pat (mode 600). It is passed by the name of the variable QODER_PERSONAL_ACCESS_TOKEN, so it
# never appears in a command line or a --dry-run.
#
# Usage:
#   evals/run_qoder_docker.sh [--prompt FILE] [--dry-run] WORKDIR [qodercli args...]
# Arguments after WORKDIR go to qodercli as they are, e.g. --model auto.
#
# Environment (defaults are the eval conditions):
#   EVAL_IMAGE=geoai-master-skills-evals-qoder  EVAL_CPUSET=0-7  EVAL_CPUS=8  EVAL_MEMORY=16g  EVAL_PIDS=512
#   EVAL_QODER_HOME=$HOME/.qoder-evals   (never $HOME/.qoder)
set -euo pipefail

IMAGE=${EVAL_IMAGE:-geoai-master-skills-evals-qoder}
CPUSET=${EVAL_CPUSET:-0-7}
CPUS=${EVAL_CPUS:-8}
MEMORY=${EVAL_MEMORY:-16g}
PIDS=${EVAL_PIDS:-512}
QODER_HOME_HOST=${EVAL_QODER_HOME:-$HOME/.qoder-evals}

dry=0 prompt=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) dry=1; shift ;;
    --prompt) prompt=${2:?--prompt needs a file}; shift 2 ;;
    --) shift; break ;;
    -*) echo "unknown option $1" >&2; exit 2 ;;
    *) break ;;
  esac
done
[[ $# -ge 1 ]] || { echo "usage: $0 [--prompt FILE] [--dry-run] WORKDIR [qodercli args...]" >&2; exit 2; }
workdir=$(realpath "$1"); shift
[[ -d "$workdir" ]] || { echo "$workdir is not a directory" >&2; exit 2; }
if [[ -e "$workdir/evals" || -e "$workdir/.git" ]]; then
  echo "$workdir contains evals/ or .git; prepare it with evals/prepare_workdir.py" >&2; exit 2
fi
if [[ -e "$QODER_HOME_HOST" && -e "$HOME/.qoder" && "$(realpath "$QODER_HOME_HOST")" == "$(realpath "$HOME/.qoder")" ]]; then
  echo "EVAL_QODER_HOME must not be the everyday \$HOME/.qoder" >&2; exit 2
fi
TOKEN_FILE="$QODER_HOME_HOST/pat"
if [[ ! -s "$TOKEN_FILE" ]]; then
  echo "No token in $TOKEN_FILE. Make one at https://qoder.com/account/integrations and save it there (chmod 600)." >&2
  exit 2
fi
QODER_PERSONAL_ACCESS_TOKEN=$(tr -d '[:space:]' < "$TOKEN_FILE")
export QODER_PERSONAL_ACCESS_TOKEN

# Hard limits. --memory-swap equal to --memory leaves no swap to escape into.
docker_args=(
  run --rm
  --cpuset-cpus="$CPUSET" --cpus="$CPUS"
  --memory="$MEMORY" --memory-swap="$MEMORY"
  --pids-limit="$PIDS"
  --cap-drop=ALL --security-opt=no-new-privileges
  -e QODER_PERSONAL_ACCESS_TOKEN
  -v "$workdir":/work
)

qoder_args=(-p --output-format stream-json --dangerously-skip-permissions --strict-mcp-config
            --no-session-persistence)
cmd=(docker "${docker_args[@]}" -w /work -i "$IMAGE" qodercli "${qoder_args[@]}" "$@")

if [[ $dry -eq 1 ]]; then echo "${cmd[*]}${prompt:+ < $prompt}"; exit 0; fi
if [[ -n "$prompt" ]]; then exec "${cmd[@]}" < "$(realpath "$prompt")"; fi
exec "${cmd[@]}"
