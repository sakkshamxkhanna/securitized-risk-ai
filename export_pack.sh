#!/usr/bin/env bash
# Regenerates the distributable surveillance pack (Excel workbook + slide deck)
# from the latest pipeline output. Run after `python -m src.agents.graph`.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${ROOT}/.venv/bin/python"

if [[ ! -f "${ROOT}/output/run_metrics.json" ]]; then
  echo "No pipeline output found. Run the pipeline first:" >&2
  echo "  ${PY} -m src.agents.graph" >&2
  exit 1
fi

echo "==> Building Excel workbook"
"$PY" -m src.excel_export

echo "==> Building slide deck"
(cd "$ROOT" && node tools/build_deck.js)

echo
echo "Pack ready:"
ls -lh "${ROOT}/output/surveillance_pack.xlsx" "${ROOT}/output/surveillance_deck.pptx" | awk '{print "  " $9 "  " $5}'
