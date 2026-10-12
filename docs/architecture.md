# Architecture

## Components

| Component | Kind | Responsibility |
|---|---|---|
| Orchestration (`skills/account-intelligence`) | Skill | Works out the task type, loads only what's needed, routes to the right workflow |
| Ingestion and analysis (`aie.ingest`, `aie.packs.*.analyzer`) | Python | Normalize, validate, calculate, structure |
| Account state (`aie.store`) | Files | Facts history, current state, investigations, events, documents |
| Comparison and detection (`aie.compare`, `aie.detect`) | Python + rules | Changes vs. previous period and baseline, declarative signal rules |
| Investigations (`aie.investigations`) | Python | Open, watching, and resolved items that persist across periods |
| Interpretation (`skills/site-analysis`) | Claude | Meaning, significance, fact vs. observation vs. hypothesis, CSM guidance |
| Validation (`aie_integrity`) | Python, independent | Recomputes everything and gates release |
| Customer output (`aie.render`) | Python | Site overview (Markdown), analysis workbook (Excel), account summary |

## The loop

| Step | What happens | Where |
|---|---|---|
| 1. New data | Raw files are copied into `inputs/SITE/PERIOD/` and hashed. Existing inputs are immutable. | `ingest.stage_inputs` |
| 2. Ingest & analyze | Column checks, type coercion (`str`, `cat`, `float`, `date`), key uniqueness, then the pack's analyzer | `ingest.load_frames`, `packs/*/analyzer.py` |
| 3. Current state | Facts with a source trail per metric go to `history/SITE/PERIOD.facts.json`, and `state/current.json` is updated | `pipeline.run` |
| 4. Compare | Previous period, delta, trailing baseline, z-score, and an assessment (better / worse / stable) for every metric. New and dropped breakdown items. | `compare.py` |
| 5a. Detect | Rules from `pack.yaml`: `delta`, `target`, `zscore`, `new_top_item`, `trend` | `detect.py` |
| 5b. Maintain | Signals with `investigate: true` open or update investigations. When a rule goes quiet, the item moves to watching (and then resolved) only if the metric has returned toward its pre-problem reference. Otherwise it stays open and is marked NOT RECOVERED. | `investigations.py` |
| 6. Interpret | Claude writes `interpretation.md` with claim-marked numbers | skill |
| 7. Update account | Facts, current state, investigations, and events are written. The account summary is archived on change. | store, render |
| 8. CSM action | The briefing's "needs attention", "questions to ask", and "wins" sections | `brief.py` |

## File contract

Both engines rely on this layout. It's the only thing they share besides the pack spec.

```
ACCOUNT/
  account.yaml                               name, pack, created
  pack.yaml                                  frozen pack spec
  inputs/SITE/PERIOD/<file>.(csv|xlsx)       immutable raw inputs
  history/SITE/PERIOD.facts.json             analysis output (see below)
  state/current.json                         latest snapshot per site
  state/investigations.json                  investigation items
  state/events.jsonl                         append-only event log
  briefings/SITE/PERIOD.briefing.(md|json)   internal briefing
  briefings/SITE/PERIOD.interpretation.md    Claude's interpretation
  validation/SITE/PERIOD.facts-check.(json|md)
  validation/SITE/PERIOD.docs-check.(json|md)
  outputs/SITE/PERIOD/site_overview.md
  outputs/SITE/PERIOD/analysis.xlsx
  outputs/SITE/PERIOD/RELEASED               written only by gate 2
  outputs/SITE/PERIOD/site_overview.customer.(md|html)   clean copies from `aie export`
  outputs/account_summary.md (+ archive/, account_summary.RELEASED)
```

### facts.json

```jsonc
{
  "schema": 1, "account": "Demo Co", "site": "site-02", "period": "2026-09",
  "pack": "ops", "pack_version": 1, "engine": "aie 0.1.0", "generated_at": "...",
  "inputs": { "labor": { "file": "labor.csv", "sha256": "...", "rows": 803,
                         "columns": [...], "date_min": "2026-09-01", "date_max": "2026-09-30" } },
  "metrics": { "efficiency": { "value": 0.7823,
               "source": { "file": "labor.csv", "columns": ["earned_hours", "paid_hours"],
                           "rule": "sum(earned_hours) / sum(paid_hours), eligible rows" } } },
  "breakdowns": { "downtime_by_reason": { "items": [{ "key": "conveyor jam", "value": 29.1 }], "source": {...} } },
  "source_reported": { "efficiency": 0.7823 },
  "comparison": { "previous_period": "2026-08", "baseline_periods": [...], "metrics": {...}, "breakdowns": {...} },
  "signals": [{ "id": "site-02:2026-09:efficiency_drop", "rule": "efficiency_drop", "kind": "risk",
                "severity": "high", "evidence": {...}, "questions": [...] }]
}
```

Values are stored unrounded. Rounding happens only at display time, and gate 2 checks displayed values against the rounding they show.

## Independence of the validation engine

`aie-integrity` is useful only if it can disagree with `aie`. So:

- **No shared code.** It never imports `aie`, and a test parses every module's imports to enforce this.
- **A different parser.** It uses the standard library `csv` module and `openpyxl`, never pandas.
- **A different math path.** It does `math.fsum` over Python lists instead of pandas group-bys.
- **No shared cache.** It reads raw inputs from disk and never reads intermediate engine state except the facts it's checking.
- **A shared spec, not shared logic.** Both engines implement `pack.yaml`. Where the spec is ambiguous, they will disagree, and that's how ambiguity gets found.

## Validation rule types

| Level | Meaning | Effect |
|---|---|---|
| HARD FAIL | The data is wrong or inconsistent | Blocks rendering and release |
| WARNING | Unusual or needs review | Proceeds unless you use `--strict` |
| INFO | Not a problem, but worth recording | Recorded only |

Gate 1 (`facts`) covers source ingestion, provenance, classification, calculations, aggregations, history, signals, and the source system's own totals. Gate 2 (`docs`) checks that the facts are unchanged since gate 1, that the document hash ties back to the validated facts, every claim marker, unmarked numbers, and every value in the workbook.
