#!/usr/bin/env bash
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$SKILL_DIR/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "venv not found. Run: python3 -m venv \"$SKILL_DIR/.venv\" && \"$SKILL_DIR/.venv/bin/pip\" install -r \"$SKILL_DIR/requirements.txt\"" >&2
  exit 2
fi
export PYTHONIOENCODING=utf-8
exec "$PY" "$SKILL_DIR/scripts/lecture.py" "$@"
