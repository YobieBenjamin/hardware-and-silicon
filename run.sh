#!/usr/bin/env bash
# One command: create a venv, install, self-validate (pytest), run the attack sweep, write the report.
#
#   ./run.sh              # venv, install, 28 tests, 53-attack sweep → results/report.md   (well under a minute)
#   ./run.sh demo         # the above, then the narrated end-to-end flow
#
# Requires Python >= 3.11; the newest python3.x on PATH is used unless PYTHON is set. No GPU, no network
# beyond PyPI on first run, no keys to provision — every key is generated inside the simulated node.
set -euo pipefail
cd "$(dirname "$0")"
MODE="${1:-sweep}"

pick_python() {
  if [ -n "${PYTHON:-}" ]; then echo "$PYTHON"; return; fi
  for p in python3.14 python3.13 python3.12 python3.11 python3; do
    if command -v "$p" >/dev/null 2>&1 && "$p" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
      echo "$p"; return
    fi
  done
  echo "no Python >= 3.11 found on PATH (set PYTHON=/path/to/python3.x)" >&2; exit 1
}
PY="$(pick_python)"

if [ ! -d .venv ]; then "$PY" -m venv .venv; fi
# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install -q -U pip
python -m pip install -q -e ".[dev]"
echo "== self-validation =="
python -m pytest -q tests
echo "== attack sweep =="
python -m hardware_ref sweep --out results
if [ "$MODE" = "demo" ]; then
  echo "== demo =="
  python -m hardware_ref demo
fi
