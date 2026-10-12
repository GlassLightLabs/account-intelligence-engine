# Integrity report: site-01 2026-07 (facts)

**Result: VALIDATED**. 4,780 checks, 4,776 passed, 0 hard failures, 3 warnings, 1 info.

| Category | Pass | Hard fail | Warning | Info |
|---|---|---|---|---|
| aggregation | 83 | 0 | 0 | 0 |
| calculation | 7 | 0 | 0 | 0 |
| classification | 7 | 0 | 0 | 1 |
| history | 65 | 0 | 0 | 0 |
| provenance | 64 | 0 | 0 | 0 |
| signals | 4 | 0 | 0 | 0 |
| source | 4,545 | 0 | 0 | 0 |
| source_system | 1 | 0 | 3 | 0 |

## Warnings

- **[source_system] paid_hours**: source system reports 6,089.4300, independent recompute is 5,805.2700. Likely cause: this analysis excluded 13 problem rows (outliers 13, unknown employee 0, duplicates 0, out of period 0) that the source system may include. `{"reported": 6089.43, "recomputed": 5805.27}`
- **[source_system] earned_hours**: source system reports 5,181.0700, independent recompute is 5,086.3000. Likely cause: this analysis excluded 13 problem rows (outliers 13, unknown employee 0, duplicates 0, out of period 0) that the source system may include. `{"reported": 5181.07, "recomputed": 5086.3}`
- **[source_system] efficiency**: source system reports 0.8508, independent recompute is 0.8762. Likely cause: this analysis excluded 13 problem rows (outliers 13, unknown employee 0, duplicates 0, out of period 0) that the source system may include. `{"reported": 0.8508, "recomputed": 0.8761521858587111}`

## Info

- **[classification] pack_note**: eligible 702, policy-excluded 110, outliers 13, unknown employee 0, duplicates 0, out of period 0, corrections 0
