#!/usr/bin/env bash
# Run a Gemini model through the Antigravity CLI (`agy`) inside Docker, on a workdir made by prepare_workdir.py.
#
# Same conditions as run_codex_docker.sh so that the Codex and Gemini evals compare models, not environments:
# CPU, memory and process limits are enforced by Docker (cgroups), only the workdir is mounted, and baseline
# and skills-enabled runs must use the same image, limits, model and effort. Only the workdir content differs.
#
# Usage:
#   evals/run_gemini_docker.sh --login                       # sign in with a Google account (OAuth); the token stays in $EVAL_GEMINI_HOME
#   evals/run_gemini_docker.sh [--auth oauth|api-key] [--prompt FILE] [--dry-run] WORKDIR [agy args...]
#
# With --prompt, runs `agy --print` non-interactively, reading the prompt from FILE, and writes the structured
# event log (stream-json) to stdout. Without it, starts the interactive agy in /work. Arguments after WORKDIR go to
# agy as they are and come after the defaults, so they win (e.g. --effort medium).
#
# Auth: --auth oauth uses the sign-in made with --login (no key is passed). --auth api-key uses the key below. Default: oauth
# when a token is in the state directory, api-key otherwise. Baseline and skills runs must use the same auth.
#
# API key: GEMINI_API_KEY (or GOOGLE_GENERATIVE_AI_API_KEY) from the shell environment or from $EVAL_ENV_FILE
# (default: .env at the repository root; see .env.example). Only those two names are read, and only passed by
# name with `docker run -e`; the key is never written to the image, /work or the command line.
#
# Environment (defaults are the eval conditions):
#   EVAL_IMAGE=geoai-master-skills-evals-gemini  EVAL_CPUSET=0-7  EVAL_CPUS=8  EVAL_MEMORY=16g  EVAL_PIDS=512
#   EVAL_MODEL (api-key: gemini-3.6-flash, oauth: gemini-3.8-flash-low)  EVAL_EFFORT (api-key only: low)  EVAL_GEMINI_HOME=$HOME/.gemini-evals (never $HOME/.gemini)
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
IMAGE=${EVAL_IMAGE:-geoai-master-skills-evals-gemini}
CPUSET=${EVAL_CPUSET:-0-7}
CPUS=${EVAL_CPUS:-8}
MEMORY=${EVAL_MEMORY:-16g}
PIDS=${EVAL_PIDS:-512}
STATE_HOST=${EVAL_GEMINI_HOME:-$HOME/.gemini-evals}
ENV_FILE=${EVAL_ENV_FILE:-$HERE/../.env}

dry=0 prompt="" login=0 auth=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) dry=1; shift ;;
    --login) login=1; shift ;;
    --auth) auth=${2:?--auth needs oauth or api-key}; shift 2 ;;
    --prompt) prompt=${2:?--prompt needs a file}; shift 2 ;;
    --) shift; break ;;
    -*) echo "unknown option $1" >&2; exit 2 ;;
    *) break ;;
  esac
done
[[ -z "$auth" || "$auth" == oauth || "$auth" == api-key ]] || { echo "--auth must be oauth or api-key" >&2; exit 2; }
if [[ $login -eq 0 ]]; then
  [[ $# -ge 1 ]] || { echo "usage: $0 [--auth oauth|api-key] [--prompt FILE] [--dry-run] WORKDIR [agy args...]" >&2; exit 2; }
  workdir=$(realpath "$1"); shift
  [[ -d "$workdir" ]] || { echo "$workdir is not a directory" >&2; exit 2; }
fi

if [[ -e "$STATE_HOST" && -e "$HOME/.gemini" && "$(realpath "$STATE_HOST")" == "$(realpath "$HOME/.gemini")" ]]; then
  echo "EVAL_GEMINI_HOME must not be the everyday \$HOME/.gemini" >&2; exit 2
fi
# Only the workdir is mounted. Evaluation material (evals/, the original repository) must not be in it.
if [[ $login -eq 0 ]] && [[ -e "$workdir/evals" || -e "$workdir/.git" ]]; then
  echo "$workdir contains evals/ or .git; prepare it with evals/prepare_workdir.py" >&2; exit 2
fi
[[ -z "$prompt" || -f "$prompt" ]] || { echo "prompt file $prompt not found" >&2; exit 2; }

TOKEN="$STATE_HOST/antigravity-cli/antigravity-oauth-token"
if [[ $login -eq 1 ]]; then auth=oauth
elif [[ -z "$auth" ]]; then if [[ -e "$TOKEN" ]]; then auth=oauth; else auth=api-key; fi; fi
echo "auth: $auth" >&2

# Read only the two key names from the env file, without sourcing it (it may hold other secrets).
read_key() { [[ -f "$ENV_FILE" ]] && sed -n "s/^\(export \)\{0,1\}$1=//p" "$ENV_FILE" | tail -1 | sed "s/^[\"']//; s/[\"']\$//" || true; }
if [[ $auth == api-key && -z "${GEMINI_API_KEY:-}" ]]; then
  GEMINI_API_KEY=$(read_key GEMINI_API_KEY)
  [[ -n "$GEMINI_API_KEY" ]] || GEMINI_API_KEY=${GOOGLE_GENERATIVE_AI_API_KEY:-$(read_key GOOGLE_GENERATIVE_AI_API_KEY)}
fi
if [[ $auth == api-key && -z "${GEMINI_API_KEY:-}" ]]; then
  echo "No GEMINI_API_KEY or GOOGLE_GENERATIVE_AI_API_KEY in the environment or in $ENV_FILE (see .env.example)" >&2; exit 2
fi
[[ $auth == api-key ]] && export GEMINI_API_KEY

# The state directory is the CLI's home for this eval; settings are rewritten every run so they cannot drift.
mkdir -p "$STATE_HOST/antigravity-cli"
if [[ $auth == api-key ]]; then printf '{"modelProvider": "gemini"}\n'; else printf '{}\n'; fi > "$STATE_HOST/antigravity-cli/settings.json"

docker_args=(
  run --rm
  --cpuset-cpus="$CPUSET" --cpus="$CPUS"
  --memory="$MEMORY" --memory-swap="$MEMORY"
  --pids-limit="$PIDS"
  --cap-drop=ALL --security-opt=no-new-privileges
  -v "$STATE_HOST":/home/geo/.gemini
)
[[ $auth == api-key ]] && docker_args+=(-e GEMINI_API_KEY)
[[ $login -eq 1 ]] || docker_args+=(-v "$workdir":/work -w /work)
# The container is the sandbox, so agy's own permission prompts are skipped.
# The catalogs differ: with an API key, model and effort are separate (gemini-3.6-flash + low); with OAuth the
# effort is part of the model name (gemini-3.8-flash-low) and 3.6 Flash is not offered. Check with `agy models`.
if [[ $auth == api-key ]]; then
  agy_args=(--model "${EVAL_MODEL:-gemini-3.6-flash}" --effort "${EVAL_EFFORT:-low}")
else
  agy_args=(--model "${EVAL_MODEL:-gemini-3.8-flash-low}")
fi
agy_args+=(--dangerously-skip-permissions)

if [[ $login -eq 1 ]]; then
  cmd=(docker "${docker_args[@]}" -it "$IMAGE" agy)
elif [[ -n "$prompt" ]]; then
  # `--print -` would take "-" as the prompt; the file's content is given to --print through the shell instead.
  cmd=(docker "${docker_args[@]}" -i "$IMAGE" bash -c 'exec agy --print="$(cat)" --output-format stream-json "$@"' agy
       "${agy_args[@]}" "$@")
else
  cmd=(docker "${docker_args[@]}" -it "$IMAGE" agy "${agy_args[@]}" "$@")
fi

if [[ $dry -eq 1 ]]; then printf '%q ' "${cmd[@]}"; echo; exit 0; fi
if [[ -n "$prompt" ]]; then exec "${cmd[@]}" < "$prompt"; fi
exec "${cmd[@]}"
