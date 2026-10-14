#!/usr/bin/env bash
# Run a Gemini model through the Antigravity CLI (`agy`) inside Docker, on a workdir made by prepare_workdir.py.
#
# Same conditions as run_codex_docker.sh so that the Codex and Gemini evals compare models, not environments:
# CPU, memory and process limits are enforced by Docker (cgroups), only the workdir is mounted, and baseline
# and skills-enabled runs must use the same image, limits, model and effort. Only the workdir content differs.
#
# Usage:
#   evals/run_gemini_docker.sh [--prompt FILE] [--dry-run] WORKDIR [agy args...]
#
# With --prompt, runs `agy --print` non-interactively, reading the prompt from FILE, and writes the structured
# event log (stream-json) to stdout. Without it, starts the interactive agy in /work. Arguments after WORKDIR go to
# agy as they are and come after the defaults, so they win (e.g. --effort medium).
#
# API key: GEMINI_API_KEY (or GOOGLE_GENERATIVE_AI_API_KEY) from the shell environment or from $EVAL_ENV_FILE
# (default: .env at the repository root; see .env.example). Only those two names are read, and only passed by
# name with `docker run -e`; the key is never written to the image, /work or the command line.
#
# Environment (defaults are the eval conditions):
#   EVAL_IMAGE=geoai-skills-evals-gemini  EVAL_CPUSET=0-7  EVAL_CPUS=8  EVAL_MEMORY=16g  EVAL_PIDS=512
#   EVAL_MODEL=gemini-3.6-flash  EVAL_EFFORT=low  EVAL_GEMINI_HOME=$HOME/.gemini-evals (never $HOME/.gemini)
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
IMAGE=${EVAL_IMAGE:-geoai-skills-evals-gemini}
CPUSET=${EVAL_CPUSET:-0-7}
CPUS=${EVAL_CPUS:-8}
MEMORY=${EVAL_MEMORY:-16g}
PIDS=${EVAL_PIDS:-512}
MODEL=${EVAL_MODEL:-gemini-3.6-flash}
EFFORT=${EVAL_EFFORT:-low}
STATE_HOST=${EVAL_GEMINI_HOME:-$HOME/.gemini-evals}
ENV_FILE=${EVAL_ENV_FILE:-$HERE/../.env}

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
[[ $# -ge 1 ]] || { echo "usage: $0 [--prompt FILE] [--dry-run] WORKDIR [agy args...]" >&2; exit 2; }
workdir=$(realpath "$1"); shift
[[ -d "$workdir" ]] || { echo "$workdir is not a directory" >&2; exit 2; }

if [[ -e "$STATE_HOST" && -e "$HOME/.gemini" && "$(realpath "$STATE_HOST")" == "$(realpath "$HOME/.gemini")" ]]; then
  echo "EVAL_GEMINI_HOME must not be the everyday \$HOME/.gemini" >&2; exit 2
fi
# Only the workdir is mounted. Evaluation material (evals/, the original repository) must not be in it.
if [[ -e "$workdir/evals" || -e "$workdir/.git" ]]; then
  echo "$workdir contains evals/ or .git; prepare it with evals/prepare_workdir.py" >&2; exit 2
fi
[[ -n "$prompt" && ! -f "$prompt" ]] && { echo "prompt file $prompt not found" >&2; exit 2; }

# Read only the two key names from the env file, without sourcing it (it may hold other secrets).
read_key() { [[ -f "$ENV_FILE" ]] && sed -n "s/^\(export \)\{0,1\}$1=//p" "$ENV_FILE" | tail -1 | sed "s/^[\"']//; s/[\"']\$//" || true; }
if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  GEMINI_API_KEY=$(read_key GEMINI_API_KEY)
  [[ -n "$GEMINI_API_KEY" ]] || GEMINI_API_KEY=${GOOGLE_GENERATIVE_AI_API_KEY:-$(read_key GOOGLE_GENERATIVE_AI_API_KEY)}
fi
if [[ -z "$GEMINI_API_KEY" ]]; then
  echo "No GEMINI_API_KEY or GOOGLE_GENERATIVE_AI_API_KEY in the environment or in $ENV_FILE (see .env.example)" >&2; exit 2
fi
export GEMINI_API_KEY

# The state directory is the CLI's home for this eval; settings are rewritten every run so they cannot drift.
mkdir -p "$STATE_HOST/antigravity-cli"
printf '{"modelProvider": "gemini"}\n' > "$STATE_HOST/antigravity-cli/settings.json"

docker_args=(
  run --rm
  --cpuset-cpus="$CPUSET" --cpus="$CPUS"
  --memory="$MEMORY" --memory-swap="$MEMORY"
  --pids-limit="$PIDS"
  --cap-drop=ALL --security-opt=no-new-privileges
  -e GEMINI_API_KEY
  -v "$STATE_HOST":/home/geo/.gemini
  -v "$workdir":/work -w /work
)
# The container is the sandbox, so agy's own permission prompts are skipped.
agy_args=(--model "$MODEL" --effort "$EFFORT" --dangerously-skip-permissions)

if [[ -n "$prompt" ]]; then
  cmd=(docker "${docker_args[@]}" -i "$IMAGE" agy --print - --output-format stream-json "${agy_args[@]}" "$@")
else
  cmd=(docker "${docker_args[@]}" -it "$IMAGE" agy "${agy_args[@]}" "$@")
fi

if [[ $dry -eq 1 ]]; then printf '%q ' "${cmd[@]}"; echo; exit 0; fi
if [[ -n "$prompt" ]]; then exec "${cmd[@]}" < "$prompt"; fi
exec "${cmd[@]}"
