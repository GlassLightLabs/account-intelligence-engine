# Writing a domain pack

A pack teaches the engine a new kind of data. The core handles state, comparison, detection, investigations, gating, and claim checks for any pack.

## 1. Write the spec: `src/aie/packs/<name>/pack.yaml`

Start from `src/aie/packs/ops/pack.yaml`. The sections:

| Section | Purpose |
|---|---|
| `files` | Input files by stem (`.csv` or `.xlsx`), whether required, optional unique `key`, and column types: `str`, `id` (uppercased), `cat` (lowercased, `-`/`_` become spaces), `cat?` (blank becomes `(blank)`), `key` (identifier, spaces become `_`), `float`, `date`. The `ops` spec header documents the reading rules both engines implement. |
| `total_row_pattern`, `date_formats` | Report-total rows to skip, and accepted date formats in priority order |
| `rules` | Pack-specific parameters, plus `top_n` and `baseline_periods`, which the core uses |
| `metrics` | Every headline number: `label`, `format` (`pct1`, `num1`, `int`), and optional `higher_is_better` |
| `breakdowns` | Lists of `{key, value}`. `ranked: true` means sorted descending and cut to `top_n`. `internal: true` keeps it out of customer documents (gate 2 hard-fails a citation). |
| `targets` | Optional targets per metric |
| `signals` | Detection rules (see below) |
| `investigations` | `resolve_after_clean_periods` |
| `integrity` | `tolerance_abs` for facts vs. recompute. `source_summary_tolerance_rel` for source-system totals. |
| `report` | What customer documents show: `headline_metric`, `key_metrics`, `breakdowns`, `summary_metrics` (account summary columns), `data_notes`. Defaults to everything. |

Write the metric definitions as comments in plain words. Two people should be able to implement them without talking to each other and get the same answer. That's the test of a good spec.

### Signal rule types

| Type | Fires when | Fields |
|---|---|---|
| `delta` | `current - previous` crosses `threshold` (a negative threshold catches drops) | `metric`, `threshold` |
| `target` | current is below or above `targets[metric]` | `metric`, `direction` |
| `zscore` | `(current - baseline) / stdev` crosses `threshold`, with at least `min_history` periods, and optionally at least `min_change_rel` relative change | `metric`, `threshold`, `min_history`, `min_change_rel` |
| `new_top_item` | a key enters the top `top_k` of a ranked breakdown | `breakdown`, `top_k` |
| `trend` | the metric moved in `direction` for at least `periods` consecutive periods, totaling at least `min_total` | `metric`, `direction`, `periods`, `min_total` |

Investigations opened by a rule store a pre-problem reference (the previous value, the baseline, or the trend's start), and resolve only when the metric returns toward it.

Common fields: `kind` (risk, anomaly, improvement, opportunity), `severity` (high, medium, low), `investigate`, `title`, and `questions`. Titles and questions can use `{site}`, `{period}`, and `{item}`.

## 2. Write the analyzer: `src/aie/packs/<name>/analyzer.py`

```python
def analyze(frames: dict[str, pd.DataFrame], spec: dict, input_meta: dict) -> dict:
    return {
        "metrics": {name: {"value": float | int | None,
                           "source": {"file": ..., "columns": [...], "rule": "..."}}},
        "breakdowns": {name: {"items": [{"key": str, "value": float}], "source": {...}}},
        "source_reported": {metric: float},   # optional: totals the source system reports itself
    }
```

`frames` arrive already type-coerced and normalized by the core.

## 3. Write the independent recompute: `src/aie_integrity/packs/<name>/recompute.py`

```python
def recompute(tables: dict[str, list[dict] | None], spec: dict) -> dict:
    return {"values": {metric: value}, "breakdowns": {name: [(key, value), ...]},
            "department_weights": {}}   # optional pack-specific extras
```

`tables` hold parsed rows from the integrity engine's own reader. Write this from the spec, not from the analyzer. Don't import pandas or `aie`, because the independence test will fail the build.

Optional hooks in the same module, picked up automatically by the core validator:

| Hook | Returns | Used for |
|---|---|---|
| `notes(mine)` | `list[str]` | INFO lines in the report (for example, how rows were classified) |
| `cross_checks(facts, mine, tol)` | `list[{"check", "ok", "message", "detail"?}]` | Pack-specific consistency rules, such as department values recombining to the total |
| `explain_source_mismatch(mine)` | `str` | A likely cause appended to source-system warnings |

## 4. Test it

Add a synthetic data generator with planted stories, and assert that the engine finds them and that both gates pass. Then tamper with a fact, an input, and a document, and assert each one gets blocked. See `tests/test_end_to_end.py`.
