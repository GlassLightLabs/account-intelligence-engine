# Integrity report: site-02 2026-09 (docs)

**Result: BLOCKED**. 160 checks, 155 passed, 1 hard failure, 0 warnings, 4 info.

| Category | Pass | Hard fail | Warning | Info |
|---|---|---|---|---|
| claims | 70 | 1 | 0 | 4 |
| gate | 3 | 0 | 0 | 0 |
| provenance | 1 | 0 | 0 | 0 |
| workbook | 81 | 0 | 0 | 0 |

## Hard failures

- **[claims] site_overview#24**: '19.1' does not match site-02@2026-09:downtime_by_reason[conveyor jam] `{"ref": "site-02@2026-09:downtime_by_reason[conveyor jam]", "expected": 29.061666666666667, "shown": "19.1"}`

## Info

- **[claims] site_overview.literal**: literal number '4,734' (not a data claim)
- **[claims] site_overview.literal**: literal number '0' (not a data claim)
- **[claims] site_overview.claim_count**: 56 claims checked
- **[claims] account_summary.claim_count**: 13 claims checked
