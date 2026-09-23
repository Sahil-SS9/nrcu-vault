#!/usr/bin/env bash
set -euo pipefail

H3_HOME="${H3_HOME:-/home/kensei/comfyui-h3}"
COMFYUI_HOME="${COMFYUI_HOME:-$H3_HOME/ComfyUI}"
H3_BASE="${H3_BASE:-$H3_HOME/base}"
H3_INPUT="${H3_INPUT:-$H3_HOME/inputs}"
H3_OUTPUT="${H3_OUTPUT:-$H3_HOME/outputs}"
H3_MODEL_PATHS="${H3_MODEL_PATHS:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/extra_model_paths.yaml}"
H3_HOST="${H3_HOST:-127.0.0.1}"
H3_PORT="${H3_PORT:-8189}"
H3_TEMP="${H3_TEMP:-}"
H3_DATABASE_URL="${H3_DATABASE_URL:-}"
PYTHON="${H3_PYTHON:-$COMFYUI_HOME/venv/bin/python}"

if [[ -n "$H3_DATABASE_URL" && "$H3_DATABASE_URL" != sqlite:///* ]]; then
  printf 'H3_DATABASE_URL must use local SQLite\n' >&2
  exit 2
fi

for required in "$PYTHON" "$COMFYUI_HOME/main.py" "$H3_MODEL_PATHS"; do
  if [[ ! -e "$required" ]]; then
    printf 'Missing required H3 path: %s\n' "$required" >&2
    exit 2
  fi
done
mkdir -p "$H3_BASE" "$H3_INPUT" "$H3_OUTPUT"

command=(
  "$PYTHON" "$COMFYUI_HOME/main.py"
  --listen "$H3_HOST"
  --port "$H3_PORT"
  --base-directory "$H3_BASE"
  --output-directory "$H3_OUTPUT"
  --input-directory "$H3_INPUT"
  --extra-model-paths-config "$H3_MODEL_PATHS"
)
if [[ -n "$H3_TEMP" ]]; then
  command+=(--temp-directory "$H3_TEMP")
fi
if [[ -n "$H3_DATABASE_URL" ]]; then
  command+=(--database-url "$H3_DATABASE_URL")
fi

if [[ "${H3_DRY_RUN:-0}" == "1" ]]; then
  printf '%q ' "${command[@]}"
  printf '\n'
  exit 0
fi

cd "$COMFYUI_HOME"
exec "${command[@]}"
