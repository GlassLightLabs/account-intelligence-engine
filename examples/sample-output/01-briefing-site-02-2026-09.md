# Briefing: site-02, 2026-09

Account: **Demo Co** | Pack: `ops` | Generated 2026-10-12T18:30:42+00:00

> Internal working document for the CSM and Claude. Not customer-facing.

## 1. Current state

Compared with previous period: **2026-08**

| Metric | Current | Previous | Change | Assessment |
|---|---|---|---|---|
| Labor efficiency | 78.2% | 82.2% | -4.0 pts | worse |
| Paid hours | 5,710.5 | 5,413.5 | +297.0 | up |
| Earned hours | 4,467.1 | 4,451.7 | +15.4 | stable |
| Lost hours | 1,243.5 | 961.9 | +281.6 | worse |
| Average paid hours per shift | 8.26 | 8.26 | -0.00 | stable |
| Downtime hours | 55.9 | 55.2 | +0.7 | stable |
| Active headcount | 38 | 38 | +0 | stable |
| Labor rows excluded as data errors | 0 | 0 | +0 | stable |
| Outlier labor rows | 0 | 0 | +0 | stable |
| Labor rows with unknown employee | 0 | 0 | +0 | stable |
| Duplicate labor rows dropped | 0 | 0 | +0 | stable |
| Labor rows dated outside the period | 0 | 0 | +0 | stable |
| Payroll correction rows | 0 | 0 | +0 | stable |
| Labor rows excluded by classification | 109 | 98 | +11 | up |

**Trend** (oldest to newest)

| Metric | 2026-04 | 2026-05 | 2026-06 | 2026-07 | 2026-08 | 2026-09 |
|---|---|---|---|---|---|---|
| Labor efficiency | 86.0% | 87.2% | 86.8% | 86.6% | 82.2% | 78.2% |
| Earned hours | 4,853.4 | 4,753.5 | 4,819.3 | 5,048.8 | 4,451.7 | 4,467.1 |
| Paid hours | 5,644.0 | 5,453.9 | 5,554.4 | 5,828.0 | 5,413.5 | 5,710.5 |
| Lost hours | 790.5 | 700.4 | 735.1 | 779.2 | 961.9 | 1,243.5 |
| Downtime hours | 28.2 | 26.3 | 29.1 | 29.2 | 55.2 | 55.9 |
| Active headcount | 38 | 38 | 38 | 38 | 38 | 38 |

**Efficiency by department** (oldest to newest; blank = not in that period's list)

| | 2026-04 | 2026-05 | 2026-06 | 2026-07 | 2026-08 | 2026-09 |
|---|---|---|---|---|---|---|
| packing | 85.3% | 88.1% | 87.7% | 87.8% | 83.1% | 80.0% |
| processing | 84.2% | 84.2% | 84.3% | 84.3% | 79.9% | 72.7% |
| receiving | 87.8% | 90.5% | 88.8% | 88.2% | 84.6% | 80.2% |
| shipping | 87.0% | 85.1% | 85.9% | 86.1% | 80.9% | 80.8% |

**Downtime hours by reason** (oldest to newest; blank = not in that period's list)

| | 2026-04 | 2026-05 | 2026-06 | 2026-07 | 2026-08 | 2026-09 |
|---|---|---|---|---|---|---|
| changeover | 14.7 | 14.2 | 17.1 | 17.9 | 13.5 | 15.5 |
| planned maintenance | 5.4 | 2.1 | 2.9 | 3.0 | 3.2 | 2.8 |
| material shortage | 4.4 | 6.3 | 7.0 | 6.0 | 5.1 | 6.0 |
| quality hold | 3.6 | 3.6 | 2.2 | 2.3 | 3.8 | 2.6 |
| conveyor jam |  |  |  |  | 29.7 | 29.1 |

## 2. What changed

- **Labor efficiency** worse: 82.2% -> 78.2% (-4.0 pts)
- **Paid hours** up: 5,413.5 -> 5,710.5 (+297.0)
- **Lost hours** worse: 961.9 -> 1,243.5 (+281.6)
- **Labor rows excluded by classification** up: 98 -> 109 (+11)
- **Efficiency by department**: packing 83.1% -> 80.0% (-3.2 pts); processing 79.9% -> 72.7% (-7.1 pts); receiving 84.6% -> 80.2% (-4.4 pts)
  - unchanged: shipping
- **Lost hours by employee (internal only, never customer-facing)**: new entries B1025, B1017, B1013
- **Lost hours by employee (internal only, never customer-facing)**: top item changed from B1005 to B1025
- Stable: Earned hours, Average paid hours per shift, Downtime hours, Active headcount, Labor rows excluded as data errors, Outlier labor rows, Labor rows with unknown employee, Duplicate labor rows dropped, Labor rows dated outside the period, Payroll correction rows

## 2b. Drivers (root-cause evidence)

Use this before writing any hypothesis about cause. If efficiency is about the same on event days and other days, that downtime reason does **not** explain the efficiency level, even if it is large.

- **conveyor jam** (processing): event days 72.7% vs other days 72.8% -> no meaningful difference: not an explanation for the efficiency level. Cite as `<!--claim:downtime_day_efficiency[conveyor jam: event days]-->`.
- **changeover** (packing, processing, receiving, shipping): event days 78.1% vs other days 78.8% -> no meaningful difference: not an explanation for the efficiency level. Cite as `<!--claim:downtime_day_efficiency[changeover: event days]-->`.
- **material shortage** (packing, processing, receiving, shipping): event days 78.6% vs other days 77.9% -> no meaningful difference: not an explanation for the efficiency level. Cite as `<!--claim:downtime_day_efficiency[material shortage: event days]-->`.
- **planned maintenance** (packing, receiving, shipping): event days 80.5% vs other days 80.2% -> no meaningful difference: not an explanation for the efficiency level. Cite as `<!--claim:downtime_day_efficiency[planned maintenance: event days]-->`.
- **quality hold** (packing, processing, receiving, shipping): event days 78.2% vs other days 78.2% -> no meaningful difference: not an explanation for the efficiency level. Cite as `<!--claim:downtime_day_efficiency[quality hold: event days]-->`.

**Breadth (internal, individual-level):** of 33 employees with data in both 2026-08 and 2026-09, 24 fell by at least 1 pt and 4 rose by at least 1 pt; median change -3.4 pts. Most people moving the same way points to a site-wide cause; a few people moving a lot points to individuals.

**By day of week:** mon 78.3%, tue 78.2%, wed 77.9%, thu 78.3%, fri 78.5%. A flat pattern rules out day-specific causes (a shift, a delivery day).

**Weekly efficiency** (week starting; a week that spans two months appears once per month, each with that month's days only)

| Period | Week of | Efficiency |
|---|---|---|
| 2026-07 | 2026-06-29 | 86.8% |
| 2026-07 | 2026-07-06 | 86.6% |
| 2026-07 | 2026-07-13 | 85.9% |
| 2026-07 | 2026-07-20 | 86.7% |
| 2026-07 | 2026-07-27 | 87.2% |
| 2026-08 | 2026-08-03 | 83.1% |
| 2026-08 | 2026-08-10 | 82.3% |
| 2026-08 | 2026-08-17 | 81.5% |
| 2026-08 | 2026-08-24 | 82.0% |
| 2026-08 | 2026-08-31 | 82.2% |
| 2026-09 | 2026-08-31 | 79.2% |
| 2026-09 | 2026-09-07 | 78.3% |
| 2026-09 | 2026-09-14 | 78.2% |
| 2026-09 | 2026-09-21 | 78.1% |
| 2026-09 | 2026-09-28 | 77.2% |

Largest week-to-week move: week of 2026-07-27 -> week of 2026-08-03 (-4.1 pts). A sharp step suggests a specific event or change around that date; a gradual slope suggests drift.

## 3. Signals

- [RISK / high] **Efficiency dropped at site-02**: current 78.2%; previous 82.2% (2026-08); change -4.0 pts
- [RISK / medium] **site-02 is below the efficiency target**: current 78.2%; target 85.0%
- [ANOMALY / medium] **Lost hours are unusually high at site-02**: current 1,243.5; baseline 825.4 over 2026-06, 2026-07, 2026-08; z = 3.48
- [RISK / medium] **Efficiency has been sliding at site-02**: current 78.2%; down 4 periods in a row since 2026-05 (87.2%), total -8.9 pts

## 4. Investigations

- **INV-0001** (open; opened 2026-08, last fired 2026-09): Efficiency dropped at site-02
- **INV-0002** (open; opened 2026-08, last fired 2026-09): site-02 is below the efficiency target
- **INV-0003** (open, NOT RECOVERED: rule went quiet but now 55.9 vs 28.2 (average of 2026-05 to 2026-07); cite the earlier level as `<!--claim:site-02@2026-08:baseline:downtime_hours-->`; opened 2026-08, last fired 2026-08): Downtime is unusually high at site-02
- **INV-0004** (open; opened 2026-08, last fired 2026-09): Lost hours are unusually high at site-02
- **INV-0005** (open, NOT RECOVERED: rule went quiet but 'conveyor jam' is still a top item; opened 2026-08, last fired 2026-08): New top downtime reason at site-02
- **INV-0006** (open; opened 2026-08, last fired 2026-09): Efficiency has been sliding at site-02

## 5. For interpretation (Claude)

Write `briefings/site-02/2026-09.interpretation.md`. Label every point as **Fact**, **Observation**, or **Hypothesis**. Every number must carry a claim marker, for example `81.2%<!--claim:efficiency-->`, `down 4.0 pts<!--claim:absdelta:efficiency-->`, or `72.7%<!--claim:efficiency_by_department[processing]-->`. Numbers without markers will be flagged by the integrity check.

## 6. CSM action

**Needs attention**

- Efficiency dropped at site-02
- site-02 is below the efficiency target
- Lost hours are unusually high at site-02
- Efficiency has been sliding at site-02
- Still not recovered: Downtime is unusually high at site-02 (now 55.9 vs 28.2 (average of 2026-05 to 2026-07))
- Still not recovered: New top downtime reason at site-02 ('conveyor jam' is still a top item)

**Questions to ask**

- Were there staffing, shift, or schedule changes at site-02 during 2026-09?
- Did product mix or order volume change?
- Is there an equipment issue behind the downtime pattern?
- Does the customer agree the target is still right for site-02?
- Which departments drove the lost hours, and was it planned?
- Is there a slow change at site-02 (staffing, equipment wear, product mix) that no single month shows?

**Wins to share**

- None at this site this period. Run `aie status` for other sites.
