---
name: account-intelligence
description: Orchestrates the Account Intelligence Engine for a customer account. Use when new site data arrives, when asked what changed or what needs attention on an account, when preparing for a customer call or QBR, or when customer-facing site documents are needed. Routes to site-analysis (for documents) and integrity-check (only when a gate fails).
---

# Account Intelligence: orchestration

The Python engine does the math. You do the routing, interpretation and judgment. Never do the math in your head. Two engines share no code: `aie` (analysis) and `aie-integrity` (an independent validator that gates release).

## Read with one command

`aie context ACCOUNT [--site SITE]` prints everything you need in one block: the status table, gate 1 results, and each site's briefing. The briefing includes six-period trends, breakdown history, what changed, cause evidence (Drivers), signals, investigations with CSM notes, questions and wins.

**Start every task with it, after any `aie run` and gate 1.** Read `history/SITE/PERIOD.facts.json` only for a value the context doesn't show. Don't list folders or read other files to orient yourself. `ACCOUNT` is the path to the account folder (the one with `pack.yaml`).

## Tasks

| The user wants... | Do this |
|---|---|
| New data processed | For each site: `aie run`, then gate 1. Then `aie context`. If they also want documents, follow the document steps. |
| What needs attention, call prep, or a QBR | `aie context`, then answer (format below). For a QBR, structure it as *what's working / what isn't / what to push on*, across sites. |
| Customer documents | Load `site-analysis`, then for each site: write the interpretation, `aie-integrity claims`, `aie render`, gate 2, `aie export`. |
| To record what they learned | `aie note ACCOUNT INV-#### "text"`. Note it on the most specific investigation and mention related IDs. |
| A gate is BLOCKED or shows warnings you can't explain | Load `integrity-check`. |
| To change a released document after the call | `aie note` first, revise the interpretation, then claims, render, gate 2 and export again. |

```bash
aie run           ACCOUNT --site SITE --input DIR [--period YYYY-MM]   # period inferred from dates if omitted
aie-integrity facts  ACCOUNT --site SITE --period YYYY-MM           # gate 1
aie context       ACCOUNT [--site SITE]
aie-integrity claims ACCOUNT --site SITE --period YYYY-MM           # pre-check your interpretation
aie render        ACCOUNT --site SITE --period YYYY-MM
aie-integrity docs   ACCOUNT --site SITE --period YYYY-MM           # gate 2, writes RELEASED
aie export        ACCOUNT --site SITE --period YYYY-MM              # clean .customer.html/.md to send
```

## Rules

1. **Process periods in order** for each site. If `aie run` warns that later periods exist, re-run them in order.
2. **Stop at a blocked gate.** Don't interpret or render on a BLOCKED gate 1.
3. **Customer-ready means RELEASED.** Send only `site_overview.customer.html` (or `.customer.md`) from `aie export`, never the tagged `site_overview.md`. Any re-render removes RELEASED.
4. **Inputs are immutable.** Corrected data needs `--force`. Tell the user.
5. **Never edit facts, validation files or RELEASED markers by hand.**
6. **Raw files:** don't read them into context. The only exception is testing a cause the Drivers evidence can't settle (see `site-analysis`).

## How to answer the CSM

Lead with the answer, in this order:

1. **Needs attention:** risks and anomalies, most severe first, one line each, with the number and period. Include investigations marked **NOT RECOVERED** (the alert went quiet only because the baseline caught up).
2. **What drives it:** departments and causes. Use the Drivers evidence, and never blame a cause that the evidence rules out.
3. **What changed since last time:** only what the briefing lists.
4. **Questions to ask:** the three most useful, plus an opening line.
5. **Wins to share.**

- **Internal breakdowns** (such as lost hours by employee): you may mention them to the CSM, labeled internal. Never put them in customer documents.
- **Exploratory results:** label them "exploratory, not validated".
- **Site names:** offer `aie name ACCOUNT site-01 "Riverside plant"` if the customer uses names for sites.
- **The account summary:** `outputs/account_summary.md` is internal.
