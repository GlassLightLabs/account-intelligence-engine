#!/usr/bin/env bash
# Rebuild examples/sample-output/ from a fresh demo run, so the committed
# samples always match what the code actually produces.
# Usage: bash examples/refresh_samples.sh
set -euo pipefail
cd "$(dirname "$0")/.."

ACCOUNT="$(mktemp -d)/demo-account"
OUT="examples/sample-output"
bash examples/run_demo.sh "$ACCOUNT" > /dev/null

mkdir -p "$OUT" && find "$OUT" -type f ! -name README.md -delete
cp "$ACCOUNT/briefings/site-02/2026-09.briefing.md"            "$OUT/01-briefing-site-02-2026-09.md"
cp "$ACCOUNT/outputs/site-02/2026-09/site_overview.md"         "$OUT/02-site-overview-site-02-2026-09.md"
cp "$ACCOUNT/outputs/site-02/2026-09/analysis.xlsx"            "$OUT/02-analysis-site-02-2026-09.xlsx"
cp "$ACCOUNT/outputs/account_summary.md"                       "$OUT/03-account-summary.md"
cp "$ACCOUNT/validation/site-01/2026-07.facts-check.md"        "$OUT/04-integrity-facts-site-01-2026-07.md"
cp "$ACCOUNT/validation/site-02/2026-09.docs-check.md"         "$OUT/05-integrity-docs-site-02-2026-09.md"
aie status "$ACCOUNT"                                         > "$OUT/00-status.txt"

# A blocked run: tamper with one number in a finished document and re-check it.
python - "$ACCOUNT" <<'PY'
import sys
from pathlib import Path
doc = Path(sys.argv[1]) / "outputs/site-02/2026-09/site_overview.md"
text = doc.read_text()
doc.write_text(text.replace("29.1<!--claim:", "19.1<!--claim:", 1))
PY
aie-integrity docs "$ACCOUNT" --site site-02 --period 2026-09 > /dev/null || true
cp "$ACCOUNT/validation/site-02/2026-09.docs-check.md"         "$OUT/06-integrity-BLOCKED-example.md"

echo "Samples written to $OUT"
