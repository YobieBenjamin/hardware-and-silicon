#!/usr/bin/env bash
# Reproduce the committed results from a clean checkout and show the diff against what is in git.
set -euo pipefail
cd "$(dirname "$0")"
./run.sh
echo "== diff against committed report (machine/python lines are expected to differ) =="
git --no-pager diff --stat -- results/ || true
