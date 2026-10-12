---
name: site-analysis
description: Interprets one site's analyzed period for the Account Intelligence Engine. Use after `aie run` and a passing gate 1, to read the briefing, write the interpretation file with claim-marked numbers, and prepare customer-ready language and CSM next steps.
---

# Site analysis and interpretation

The engine has already computed the numbers, compared them to history, fired signals, and updated investigations. Your job is step 6: **what does it mean, why does it matter, and what is fact versus hypothesis.**

## Inputs

Everything is in `aie context ACCOUNT --site SITE`: the briefing with trends, breakdown history, Drivers, investigations with notes, and the claim reference for any problem that hasn't recovered. Read `history/SITE/PERIOD.facts.json` only for a value it doesn't show, and last period's `interpretation.md` if you want your story to stay consistent. Gate 1 must be VALIDATED first.

## Test causes before you name them

A hypothesis is only worth writing if the evidence doesn't already rule it out. Before writing one:

1. **Read the Drivers section.**
   - **Event days vs other days:** for each top downtime reason, efficiency on days with that event against other days. If they're about equal, that reason does **not** explain the efficiency level, however large it is.
   - **Breadth:** how many employees moved and which way. Most people moving together points to a site-wide cause.
   - **Day of week:** a flat pattern rules out day-specific causes.
   - **Weekly table:** a sharp step points to a specific week; name it. A gradual slope is drift.
   - Average paid hours per shift (in the current-state table) tells you whether extra hours came from longer shifts.
2. **If you still need evidence the engine doesn't compute**, write a short read-only pandas script against the staged copies in `inputs/SITE/PERIOD/` and read only its printed result. Never edit inputs. Keep scratch scripts in a `scratch/` folder next to the account, not inside it.
   - In your reply to the CSM, label these results **exploratory (not validated)**.
   - Don't put exploratory numbers in customer documents. Gate 2 can only verify engine facts. Describe the direction in words, or propose adding the metric to the pack.

Example: conveyor jams doubled downtime, but processing ran 72.7% on jam days versus 72.8% on other days, and every department dropped in the same week. The honest read is "a site-wide change around the week of August 3, with the conveyor a separate problem", not "fix the conveyor and efficiency recovers."

## Output: `briefings/SITE/PERIOD.interpretation.md`

Write for the customer's operations leader: plain, specific, and non-judgmental. It will be embedded under "What this means" in the site overview. The **Fact / Observation / Hypothesis** labels stay in the customer copy on purpose, because they tell the reader how sure we are.

Structure:

- **Fact.** Something the data directly shows. It must cite numbers.
- **Observation.** A pattern you see across facts, such as where a change is concentrated or what moved together.
- **Hypothesis.** A possible cause. Say what would confirm it. Never present a hypothesis as a fact.
- **Recommended next steps:** 2 to 4 bullets, each one an action someone can take.

Keep it to roughly 150 to 300 words. Lead with the most important point.

## Claim markers (required)

Every number you write must carry a claim marker, or the integrity check flags it. Copy values exactly as the briefing's tables display them: same rounding, same unit. (Every example in this file is checked against the demo account by the test suite.)

| You write | Marker |
|---|---|
| Current value | `78.2%<!--claim:efficiency-->` |
| Change vs previous period, in a table | `-4.0 pts<!--claim:delta:efficiency-->` |
| Change vs previous period, in prose | `down 4.0 pts<!--claim:absdelta:efficiency-->` (unsigned, so "down" isn't a double negative) |
| Change in one breakdown item | `down 7.1 pts<!--claim:absdelta:efficiency_by_department[processing]-->` |
| Trailing baseline | `825.4<!--claim:baseline:lost_hours-->` |
| Target | `85.0%<!--claim:target:efficiency-->` |
| Breakdown item | `29.1<!--claim:downtime_by_reason[conveyor jam]-->` |
| Driver evidence | `72.7%<!--claim:downtime_day_efficiency[conveyor jam: event days]-->` vs `72.8%<!--claim:downtime_day_efficiency[conveyor jam: other days]-->` |
| One week | `78.2%<!--claim:weekly_efficiency[2026-09-14]-->`, or from an earlier period `83.1%<!--claim:site-02@2026-08:weekly_efficiency[2026-08-03]-->` |
| Another period or site (works with any of the forms above) | `80.0%<!--claim:site-03@2026-04:efficiency-->`, `79.9%<!--claim:site-02@2026-08:efficiency_by_department[processing]-->` |

Formats: ratios use one decimal and `%`. Changes in ratios use signed `pts` (`+2.1 pts`). Hours use one decimal with thousands separators (`1,243.5`). Counts are integers.

Rules:

- **No uncited numbers.** Gate 2 warns about any bare numeral. Cite every data value, including counts like headcount. Only non-data counts ("two months in a row", "three sites") go in words. (`<!--literal-->` exists for non-data numbers such as the check count in the document header. Don't use it for data.) Don't round on your own ("about 80%"). Use the displayed value with its marker.
- **Don't invent metrics.** If the number you want isn't in the facts (for example, a percentage share), describe it qualitatively or ask for a pack change.
- **Never cite internal-only breakdowns** (the pack marks them `internal: true`; for `ops` that's lost hours by employee). Gate 2 hard-fails any document that does.
- **For problems that have not recovered**, the briefing's investigation line gives the exact claim reference for the earlier level. Copy it rather than building your own. For example, `55.9<!--claim:downtime_hours-->` versus `28.2<!--claim:site-02@2026-08:baseline:downtime_hours-->`, the May to July average. That's the baseline as of August, when the problem was first flagged. The baseline as of September would already include August's spike. Say what the reference is (an average, or a specific month). Don't call an average "July".
- **Check every qualitative statement against the facts.** Gate 2 verifies numbers, not words. "Every department slipped" or "the first time" can be false while every number is right. Before writing "all", "every", "first", "only", or "none", confirm it in `facts.json`, including items the briefing left out because they moved too little.
- **Use the customer's language.** Say departments and reasons as they appear in the data. Don't use internal rule names like `lost_hours_spike`.

## After writing

```bash
aie-integrity claims ACCOUNT --site SITE --period PERIOD   # fix anything it reports, then:
aie render ACCOUNT --site SITE --period PERIOD
aie-integrity docs ACCOUNT --site SITE --period PERIOD
aie export ACCOUNT --site SITE --period PERIOD
```

`claims` checks your file directly. A hard failure means a mis-copied number or a wrong reference, and it prints the expected value. A warning means a number with no claim marker.

## CSM prep (when asked)

From the briefing's CSM action section, give the user:

- The 3 questions most worth asking, reworded for a conversation
- One sentence they can say on the call to open the topic
- What to watch next period to confirm or rule out your hypothesis

Then offer to log what they learn with `aie note ACCOUNT INV-#### "..."`.
