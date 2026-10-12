#!/usr/bin/env bash
# End-to-end demo: synthetic data -> analysis -> gate 1 -> render -> gate 2.
# Usage: bash examples/run_demo.sh [account_dir]
set -euo pipefail
cd "$(dirname "$0")/.."

ACCOUNT="${1:-examples/demo-account}"
DATA="examples/demo-data"
SITES=(site-01 site-02 site-03)
PERIODS=(2026-04 2026-05 2026-06 2026-07 2026-08 2026-09)
LATEST="${PERIODS[${#PERIODS[@]}-1]}"   # bash 3.2 safe (macOS)

python examples/generate_demo_data.py --out "$DATA"
rm -rf "$ACCOUNT"
aie init "$ACCOUNT" --name "Demo Co" --pack ops
aie name "$ACCOUNT" site-01 "Riverside plant" > /dev/null
aie name "$ACCOUNT" site-02 "Lakeview plant" > /dev/null
aie name "$ACCOUNT" site-03 "Hillcrest plant" > /dev/null

for site in "${SITES[@]}"; do
  for period in "${PERIODS[@]}"; do
    aie run "$ACCOUNT" --site "$site" --period "$period" --input "$DATA/$site/$period" > /dev/null
    result="$(aie-integrity facts "$ACCOUNT" --site "$site" --period "$period")"
    echo "${result%%$'\n'*}"   # first line only
  done
done

# Step 6 (interpretation) is Claude's job. The demo ships pre-written examples.
for site in "${SITES[@]}"; do
  example="examples/interpretations/${site}_${LATEST}.md"
  if [[ -f "$example" ]]; then
    cp "$example" "$ACCOUNT/briefings/$site/$LATEST.interpretation.md"
  fi
  aie render "$ACCOUNT" --site "$site" --period "$LATEST" > /dev/null
done
for site in "${SITES[@]}"; do
  aie-integrity docs "$ACCOUNT" --site "$site" --period "$LATEST"
  aie export "$ACCOUNT" --site "$site" --period "$LATEST" > /dev/null
done

echo
echo "Done. Start with:"
echo "  $ACCOUNT/briefings/site-02/$LATEST.briefing.md     (internal CSM briefing)"
echo "  $ACCOUNT/outputs/site-02/$LATEST/site_overview.customer.html  (customer copy, tags removed)"
echo "  $ACCOUNT/outputs/account_summary.md"
echo "  $ACCOUNT/validation/site-02/$LATEST.facts-check.md (integrity report)"
