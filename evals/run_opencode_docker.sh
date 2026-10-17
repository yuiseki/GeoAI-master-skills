#!/usr/bin/env bash
# Run OpenCode CLI inside Docker on a workdir made by prepare_workdir.py.
#
# Same conditions as run_codex_docker.sh and run_gemini_docker.sh, so that the evals compare agents and models,
# not environments: CPU, memory and process limits are enforced by Docker (cgroups), only the workdir is mounted,
# and baseline and skills-enabled runs must use the same image, limits and model. Only the workdir content differs.
#
# Usage:
#   evals/run_opencode_docker.sh [--prompt FILE] [--dry-run] WORKDIR [opencode args...]
#
# With --prompt, runs `opencode run --format json` non-interactively, with the file's content on stdin as the
# message (opencode reads piped stdin; an argument would hit the 128 KiB limit of one argv string), and writes
# the raw JSON events to stdout. Without it, starts the interactive OpenCode in /work. Arguments after WORKDIR go
# to opencode as they are and come after the defaults (e.g. --variant high).
#
# Nothing of the everyday OpenCode is brought in: no config, auth or state from $HOME is mounted and no
# OPENCODE_* variable is passed. The state lives in the container's home and goes with the container (--rm),
# so runs cannot see each other's sessions. The models used here (opencode/*-free) need no sign-in. The config
# is given inline: sharing off (a free-model session must not be published by accident), no update checks.
#
# Environment (defaults are the eval conditions):
#   EVAL_IMAGE=geoai-master-skills-evals-opencode  EVAL_CPUSET=0-7  EVAL_CPUS=8  EVAL_MEMORY=16g  EVAL_PIDS=512
#   EVAL_MODEL=opencode/deepseek-v4.1-flash-free   (also e.g. opencode/glm-5.3-flash-free)
set -euo pipefail

IMAGE=${EVAL_IMAGE:-geoai-master-skills-evals-opencode}
CPUSET=${EVAL_CPUSET:-0-7}
CPUS=${EVAL_CPUS:-8}
MEMORY=${EVAL_MEMORY:-16g}
PIDS=${EVAL_PIDS:-512}
MODEL=${EVAL_MODEL:-opencode/deepseek-v4.1-flash-free}
CONFIG='{"$schema":"https://opencode.ai/config.json","share":"disabled","autoupdate":false}'

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
[[ $# -ge 1 ]] || { echo "usage: $0 [--prompt FILE] [--dry-run] WORKDIR [opencode args...]" >&2; exit 2; }
workdir=$(realpath "$1"); shift
[[ -d "$workdir" ]] || { echo "$workdir is not a directory" >&2; exit 2; }
# Only the workdir is mounted. Evaluation material (evals/, the original repository) must not be in it.
if [[ -e "$workdir/evals" || -e "$workdir/.git" ]]; then
  echo "$workdir contains evals/ or .git; prepare it with evals/prepare_workdir.py" >&2; exit 2
fi
[[ -z "$prompt" || -f "$prompt" ]] || { echo "prompt file $prompt not found" >&2; exit 2; }

# Hard limits. --memory-swap equal to --memory leaves no swap to escape into.
docker_args=(
  run --rm
  --cpuset-cpus="$CPUSET" --cpus="$CPUS"
  --memory="$MEMORY" --memory-swap="$MEMORY"
  --pids-limit="$PIDS"
  --cap-drop=ALL --security-opt=no-new-privileges
  -e OPENCODE_CONFIG_CONTENT="$CONFIG"
  -v "$workdir":/work -w /work
)

# The container is the sandbox. In `opencode run`, a permission that would ask (a path outside /work, a call
# repeated three times) is rejected unless --auto approves it; explicit denials (.env files) still hold.
# --pure: no external plugins.
if [[ -n "$prompt" ]]; then
  cmd=(docker "${docker_args[@]}" -i "$IMAGE"
       opencode run --format json --auto --pure --dir /work --model "$MODEL" "$@")
  prompt_in=$(realpath "$prompt")
else
  cmd=(docker "${docker_args[@]}" -it "$IMAGE" opencode /work --model "$MODEL" "$@")
fi

if [[ $dry -eq 1 ]]; then printf '%q ' "${cmd[@]}"; echo; exit 0; fi
if [[ -n "${prompt_in:-}" ]]; then exec "${cmd[@]}" < "$prompt_in"; fi
exec "${cmd[@]}"
