# Site overview: Lakeview plant (site-02), 2026-09

**Demo Co** | Prepared 2026-10-12 | Data validated: 4,734<!--literal--> independent checks, 0<!--literal--> failures

## Key metrics

| Metric | 2026-09 | 2026-08 | Change |
|---|---|---|---|
| Labor efficiency | 78.2%<!--claim:site-02@2026-09:efficiency--> | 82.2%<!--claim:site-02@2026-08:efficiency--> | -4.0 pts<!--claim:site-02@2026-09:delta:efficiency--> |
| Earned hours | 4,467.1<!--claim:site-02@2026-09:earned_hours--> | 4,451.7<!--claim:site-02@2026-08:earned_hours--> | +15.4<!--claim:site-02@2026-09:delta:earned_hours--> |
| Paid hours | 5,710.5<!--claim:site-02@2026-09:paid_hours--> | 5,413.5<!--claim:site-02@2026-08:paid_hours--> | +297.0<!--claim:site-02@2026-09:delta:paid_hours--> |
| Lost hours | 1,243.5<!--claim:site-02@2026-09:lost_hours--> | 961.9<!--claim:site-02@2026-08:lost_hours--> | +281.6<!--claim:site-02@2026-09:delta:lost_hours--> |
| Downtime hours | 55.9<!--claim:site-02@2026-09:downtime_hours--> | 55.2<!--claim:site-02@2026-08:downtime_hours--> | +0.7<!--claim:site-02@2026-09:delta:downtime_hours--> |
| Active headcount | 38<!--claim:site-02@2026-09:active_headcount--> | 38<!--claim:site-02@2026-08:active_headcount--> | +0<!--claim:site-02@2026-09:delta:active_headcount--> |

Labor efficiency target: 85.0%<!--claim:target:efficiency-->

## Efficiency by department

| | Value |
|---|---|
| packing | 80.0%<!--claim:site-02@2026-09:efficiency_by_department[packing]--> |
| processing | 72.7%<!--claim:site-02@2026-09:efficiency_by_department[processing]--> |
| receiving | 80.2%<!--claim:site-02@2026-09:efficiency_by_department[receiving]--> |
| shipping | 80.8%<!--claim:site-02@2026-09:efficiency_by_department[shipping]--> |

## Downtime hours by reason

| | Value |
|---|---|
| conveyor jam | 29.1<!--claim:site-02@2026-09:downtime_by_reason[conveyor jam]--> |
| changeover | 15.5<!--claim:site-02@2026-09:downtime_by_reason[changeover]--> |
| material shortage | 6.0<!--claim:site-02@2026-09:downtime_by_reason[material shortage]--> |
| planned maintenance | 2.8<!--claim:site-02@2026-09:downtime_by_reason[planned maintenance]--> |
| quality hold | 2.6<!--claim:site-02@2026-09:downtime_by_reason[quality hold]--> |

## What changed

- Labor efficiency moved from 82.2%<!--claim:site-02@2026-08:efficiency--> in 2026-08 to 78.2%<!--claim:site-02@2026-09:efficiency--> (-4.0 pts<!--claim:site-02@2026-09:delta:efficiency-->).
- Labor efficiency is 78.2%<!--claim:site-02@2026-09:efficiency--> against a target of 85.0%<!--claim:target:efficiency-->.
- Lost hours came in at 1,243.5<!--claim:site-02@2026-09:lost_hours-->, well above the recent baseline of 825.4<!--claim:site-02@2026-09:baseline:lost_hours-->.
- Labor efficiency has fallen every month since 2026-05, from 87.2%<!--claim:site-02@2026-05:efficiency--> to 78.2%<!--claim:site-02@2026-09:efficiency-->.
- Downtime hours has not recovered: 55.9<!--claim:site-02@2026-09:downtime_hours--> this period versus 28.2<!--claim:site-02@2026-08:baseline:downtime_hours--> before the issue began (average of 2026-05 to 2026-07).
- 'conveyor jam' is still the leading item in downtime hours by reason (29.1<!--claim:site-02@2026-09:downtime_by_reason[conveyor jam]-->).

## What this means

**Fact.** Labor efficiency fell to 78.2%<!--claim:site-02@2026-09:efficiency--> this month, down 4.0 pts<!--claim:site-02@2026-09:absdelta:efficiency--> from August and the second large monthly decline in a row. The site is now well under the 85.0%<!--claim:site-02@2026-09:target:efficiency--> target.

**Fact.** The decline started abruptly. Weekly efficiency went from 87.2%<!--claim:site-02@2026-07:weekly_efficiency[2026-07-27]--> in the last week of July to 83.1%<!--claim:site-02@2026-08:weekly_efficiency[2026-08-03]--> the week of August 3, and has kept sliding since.

**Fact.** Conveyor jams first appeared that same week and were the largest downtime reason this month at 29.1<!--claim:site-02@2026-09:downtime_by_reason[conveyor jam]--> hours. But processing ran at 72.7%<!--claim:site-02@2026-09:downtime_day_efficiency[conveyor jam: event days]--> on jam days and 72.8%<!--claim:site-02@2026-09:downtime_day_efficiency[conveyor jam: other days]--> on other days, so the jams do not explain the efficiency level.

**Observation.** Every department is below target, not only processing, which is the weakest at 72.7%<!--claim:site-02@2026-09:efficiency_by_department[processing]-->. Lost hours reached 1,243.5<!--claim:site-02@2026-09:lost_hours-->, far above the recent baseline of 825.4<!--claim:site-02@2026-09:baseline:lost_hours-->, while paid hours rose and earned hours stayed flat.

**Hypothesis.** Something changed site-wide around the week of August 3, such as labor standards, product mix, staffing, or how earned hours are credited. The conveyor is a real but separate problem. Confirming what changed that week is the priority; fixing the conveyor alone is unlikely to restore efficiency.

**Recommended next steps**

- Ask the site what changed in the week of August 3 across all departments.
- Get a repair plan for the conveyor as a separate item.
- Re-check weekly efficiency after any change to see whether it steps back up.

## Data notes

- Labor rows excluded as data errors: 0<!--claim:site-02@2026-09:excluded_rows-->
- Outlier labor rows: 0<!--claim:site-02@2026-09:outlier_rows-->
- Labor rows with unknown employee: 0<!--claim:site-02@2026-09:unmatched_rows-->
- Duplicate labor rows dropped: 0<!--claim:site-02@2026-09:duplicate_rows-->
- Labor rows dated outside the period: 0<!--claim:site-02@2026-09:out_of_period_rows-->
- Sources: `employees.csv`, `labor.csv`, `downtime.csv`, `source_summary.csv`.

<!-- facts-sha256:42d19e9f6e6cc5ca9d5b51d002ddf92c4e08397be5def538beaea26bffbbaa7a -->
