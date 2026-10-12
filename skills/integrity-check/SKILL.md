---
name: integrity-check
description: Diagnoses and fixes Account Intelligence Engine validation results. Use when aie-integrity reports BLOCKED, when it reports warnings you need to explain to a CSM, or when asked what the validation gates check.
---

# Integrity check

`aie-integrity` is a second engine that shares no code with `aie`. It re-reads the raw inputs with its own parser, recomputes every metric from the pack spec, and compares the results. Nothing reaches a customer unless it passes.

```
gate 1  aie-integrity facts ACCOUNT --site SITE --period PERIOD   after `aie run`, before interpretation
gate 2  aie-integrity docs  ACCOUNT --site SITE --period PERIOD   after `aie render`, before release
```

Exit code `0` means VALIDATED and `1` means BLOCKED. Add `--strict` to block on warnings too.

## What gets checked

| Category | Examples |
|---|---|
| source | Required files present, columns present, every cell parses, row counts and date ranges match what the analysis read, rows dated inside the period, unique keys |
| provenance | Input file SHA-256 matches the facts, every metric names a real source file and columns, the document was rendered from the validated facts |
| classification | Row exclusion buckets (unknown employee, excluded classification, outlier) match |
| calculation | Every headline metric matches the recompute |
| aggregation | Every breakdown value, ranking, and membership. Department efficiencies recombine to the total. Reason totals don't exceed overall downtime. |
| history | Previous period, deltas, baselines, and z-scores match |
| signals | Each signal's evidence matches, and its rule condition actually holds on the recomputed data |
| source_system | Totals the source system reports about itself (warning only) |
| claims | Every marked number in a document matches its reference, and any number without a marker is flagged |
| workbook | Every value in `analysis.xlsx` matches |

## Levels

- **HARD FAIL**: the data is wrong or inconsistent. Output is blocked. Never work around it.
- **WARNING**: unusual or needs review. Output may proceed, but tell the user what it is and why.
- **INFO**: recorded for transparency (row buckets, literal numbers, claim counts).

## When gate 1 is BLOCKED

Read `validation/SITE/PERIOD.facts-check.md` and diagnose by category:

| Failure | Likely cause | Fix |
|---|---|---|
| `provenance ... sha256` | An input changed after analysis | Re-run `aie run` (with `--force` if new data was supplied) |
| `source ... cells_parse` | Bad or empty values in the export | Fix the source file, then re-run with `--force` |
| `calculation` or `aggregation` mismatch | A bug in the analysis code or the recompute, or a spec that is ambiguous | Find which engine disagrees with the spec. Fix the code, add a test, re-run both. Don't loosen tolerances to make it pass. |
| `history` mismatch | Periods processed out of order, or a period has inputs but no facts | Re-run the site's periods in chronological order |
| `signals ... condition` | Detection logic drifted from the spec | Fix `aie/detect.py` |

Then report to the user in plain terms: what failed, why, and what you changed. Include the before and after check counts.

## When gate 1 passes with warnings

| Warning | Meaning | What to tell the CSM |
|---|---|---|
| `labor.duplicate_rows` | Exact duplicate rows were dropped (usually overlapping exports) | Mention it. If the customer really does log identical shifts, the pack rule needs changing. |
| `labor.out_of_period_rows` / `dates_in_period` | Rows dated in another month were excluded | Those hours belong to their own month. Ask whether that month's data needs a re-run with `--force`. |
| `labor.roster_match` | Many labor rows match no employee on the roster | Usually an ID format mismatch or a stale roster. Don't present efficiency until it's explained. |

`source_system` warnings mean the customer's own system reports a different total than this analysis. That's usually because outliers or unknown employees were excluded here. Mention it to the CSM, since the customer may see the other number in their own tool and ask why it differs.

## When gate 2 is BLOCKED

A `.internal` failure means a document cites individual-level data the pack marks internal-only. Remove it. Otherwise it's usually a mis-copied number in `interpretation.md`. The report shows the displayed value, the reference, and the expected value. Fix the interpretation (see `site-analysis`), render again, and re-run gate 2. If `site_overview.facts_sha256` fails, the facts changed after rendering, so render again.

## Never

- Edit `history/*.facts.json`, `validation/*`, or `RELEASED` markers by hand.
- Change `integrity.tolerance_abs` in `pack.yaml` to get a pass.
- Hand a document to the user as customer-ready without a `RELEASED` marker.
