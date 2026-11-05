#!/usr/bin/env bash
# Run the categorizer on a CSV, score it against an answer key (optional) and open the results page.
# usage: tools/demo.sh <listings.csv> [answer_key.csv]
set -euo pipefail
input="$1"; gold="${2:-}"
stem="$(basename "$input" .csv)"
cd "$(dirname "$0")/.."
uv run categorize "$input" --out-dir out/
if [ -n "$gold" ]; then
  uv run python -m categorizer.evaluate "out/${stem}_categorized.csv" "$gold" --out "out/${stem}_eval.json"
  uv run python tools/view_results.py "out/${stem}_categorized.csv" --gold "$gold" --out "out/${stem}_results.html"
else
  uv run python tools/view_results.py "out/${stem}_categorized.csv" --out "out/${stem}_results.html"
fi
open "out/${stem}_results.html" 2>/dev/null || xdg-open "out/${stem}_results.html"
