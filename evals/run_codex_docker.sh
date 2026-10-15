#!/usr/bin/env bash
# Run Codex CLI inside Docker on a workdir made by prepare_workdir.py.
#
# The CPU, memory and process limits are enforced by Docker (cgroups), and they are part of the eval
# condition: baseline and skills-enabled runs must use the same image, the same limits and the same
# Codex arguments. Only the workdir content differs.
#
# Usage:
#   evals/run_codex_docker.sh --login                       # first time: sign in, state in $EVAL_CODEX_HOME
#   evals/run_codex_docker.sh [--prompt FILE] [--dry-run] WORKDIR [codex args...]
#
# With --prompt, runs `codex exec` non-interactively with the file's content as the prompt.
# Without it, starts the interactive Codex in /work. Arguments after WORKDIR go to Codex as they are,
# e.g. -m gpt-6-luna -c model_reasoning_effort=medium.
#
# Environment (defaults are the eval conditions):
#   EVAL_IMAGE=geoai-master-skills-evals-codex  EVAL_CPUSET=0-7  EVAL_CPUS=8  EVAL_MEMORY=16g  EVAL_PIDS=512
#   EVAL_CODEX_HOME=$HOME/.codex-evals   (never $HOME/.codex)
set -euo pipefail

IMAGE=${EVAL_IMAGE:-geoai-master-skills-evals-codex}
CPUSET=${EVAL_CPUSET:-0-7}
CPUS=${EVAL_CPUS:-8}
MEMORY=${EVAL_MEMORY:-16g}
PIDS=${EVAL_PIDS:-512}
CODEX_HOME_HOST=${EVAL_CODEX_HOME:-$HOME/.codex-evals}

login=0 dry=0 prompt=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --login) login=1; shift ;;
    --dry-run) dry=1; shift ;;
    --prompt) prompt=${2:?--prompt needs a file}; shift 2 ;;
    --) shift; break ;;
    -*) echo "unknown option $1" >&2; exit 2 ;;
    *) break ;;
  esac
done

if [[ -e "$CODEX_HOME_HOST" && "$(realpath "$CODEX_HOME_HOST")" == "$(realpath "$HOME/.codex")" ]]; then
  echo "EVAL_CODEX_HOME must not be the everyday \$HOME/.codex" >&2; exit 2
fi
mkdir -p "$CODEX_HOME_HOST"

# Hard limits. --memory-swap equal to --memory leaves no swap to escape into.
docker_args=(
  run --rm
  --cpuset-cpus="$CPUSET" --cpus="$CPUS"
  --memory="$MEMORY" --memory-swap="$MEMORY"
  --pids-limit="$PIDS"
  --cap-drop=ALL --security-opt=no-new-privileges
  -v "$CODEX_HOME_HOST":/home/geo/.codex
)

if [[ $login -eq 1 ]]; then
  cmd=(docker "${docker_args[@]}" -it "$IMAGE" codex login --device-auth)
else
  [[ $# -ge 1 ]] || { echo "usage: $0 [--prompt FILE] WORKDIR [codex args...]" >&2; exit 2; }
  workdir=$(realpath "$1"); shift
  [[ -d "$workdir" ]] || { echo "$workdir is not a directory" >&2; exit 2; }
  if [[ ! -e "$CODEX_HOME_HOST/auth.json" ]]; then
    echo "No Codex login in $CODEX_HOME_HOST. Run: $0 --login" >&2; exit 2
  fi
  # Only the workdir is mounted. Evaluation material (evals/, the original repository) must not be in it.
  if [[ -e "$workdir/evals" || -e "$workdir/.git" ]]; then
    echo "$workdir contains evals/ or .git; prepare it with evals/prepare_workdir.py" >&2; exit 2
  fi
  # The container is the sandbox: Codex's own sandbox needs privileges that --cap-drop=ALL removes.
  codex_args=(--dangerously-bypass-approvals-and-sandbox --skip-git-repo-check -C /work)
  if [[ -n "$prompt" ]]; then
    cmd=(docker "${docker_args[@]}" -v "$workdir":/work -w /work -i "$IMAGE"
         codex exec "${codex_args[@]}" "$@" -)
    prompt_in=$(realpath "$prompt")
  else
    cmd=(docker "${docker_args[@]}" -v "$workdir":/work -w /work -it "$IMAGE"
         codex "${codex_args[@]}" "$@")
  fi
fi

if [[ $dry -eq 1 ]]; then printf '%q ' "${cmd[@]}"; echo; exit 0; fi
if [[ -n "${prompt_in:-}" ]]; then exec "${cmd[@]}" < "$prompt_in"; fi
exec "${cmd[@]}"
