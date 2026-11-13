#!/usr/bin/env bash
# Uso: bash run.sh "problema"   |   bash run.sh --self-test   |   bash run.sh --serve
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
if [ ! -d .venv ]; then
  "$PY" -m venv .venv
  .venv/bin/pip install -q -e ".[dev]"
fi
exec .venv/bin/python -m omega_meta "$@"
