#!/usr/bin/env bash
# Dubplates.net Client: run from source (macOS / Linux). First start: makes .venv, installs PyTorch + the engine, builds the UI.
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
if [ ! -x .venv/bin/python ]; then
  echo "Making .venv ..."
  "$PY" -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  if command -v nvidia-smi >/dev/null 2>&1; then
    .venv/bin/python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
  else
    .venv/bin/python -m pip install torch torchaudio      # macOS: Apple GPU (MPS) build
  fi
  .venv/bin/python -m pip install -r requirements.txt
fi
if [ ! -f ui/dist/index.html ]; then
  (cd ui && npm install && npx vite build)
fi
exec .venv/bin/python -m dubplates_client.main
