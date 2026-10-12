# Benchmark: engine + skills vs. plain Claude

**Question:** for the same CSM request, does the engine and skills setup use fewer tokens than Claude working directly from the raw exports with Python?

**Short answer: modestly, and only after tuning.** The current version (v3) uses about the same tokens as plain Claude for one site (+3%) and 10% fewer for a three-site QBR, while finishing 32 to 43% faster with every customer-facing number independently verified. The real advantages are speed, verified numbers, consistency, and month-to-month memory. Token savings are a small bonus, not the headline.

## Method

Each trial is a fresh Claude session with no prior context, given the same CSM request and the same list of what the CSM expects. That list covers changes vs. last month and the trend, anomalies, drivers by department and downtime cause, data quality, the status of earlier problems, questions for the call, and customer-ready documents where every number is correct.

- **Plain Claude:** raw CSV exports for April to September, a shell, and Python with pandas.
- **Engine + skills:** the three skills, the `aie` and `aie-integrity` CLIs, and an account with April to August already processed (the normal steady state). September's exports are dropped in.

Two tasks, two trials each:

- **Call prep:** one site.
- **QBR:** three sites, an account-level story, and three customer documents.

Tokens are the per-session totals the agent harness reports. A session that only replies "OK" costs about **50.6k tokens**: the fixed cost of the system prompt and tool definitions, which every session pays. All data is synthetic, and the engine runs were repeated after the version 2 changes described below.

## Results

| Task | Arm | Trial tokens | Avg tokens | Avg time |
|---|---|---|---|---|
| Call prep (1 site) | Plain Claude | 79.3k, 89.5k | 84.4k | 162 s |
| | Engine v1 | 83.2k, 79.1k | 81.1k | 94 s |
| | Engine v2 | 88.1k, 92.8k | 90.4k (+7%) | 121 s (-25%) |
| | **Engine v3** | 87.1k, 86.3k | **86.7k** (+3%) | **111 s** (-32%) |
| QBR (3 sites) | Plain Claude | 109.8k, 106.7k | 108.3k | 257 s |
| | Engine v1 | 100.3k, 98.9k | 99.6k | 154 s |
| | Engine v2 | 105.6k, 106.6k | 106.1k (-2%) | 171 s (-33%) |
| | **Engine v3** | 99.4k, 95.9k | **97.7k** (-10%) | **147 s** (-43%) |

Without the ~50.6k fixed cost, the task work alone came to about 34k (plain) vs. 36k (engine v3) for call prep, and 58k vs. 47k (19% less) for the QBR. The engine's advantage grows with the size of the job.

## What the numbers mean

- **Why the token savings are small.** Plain Claude with Python already never loads raw data into its context. It writes scripts and reads only their summaries. The engine saves Claude the analysis work, but it adds the cost of reading roughly 3,000 words of skills every session.
- **v1 vs. v2.** In v1, the engine was slightly cheaper but missed the root cause (see below). Fixing that cost about 9k tokens per run, because the sessions now read the driver evidence and run their own read-only checks.
- **What wasn't measured.** The plain approach reprocesses every month of history on every run, so its cost should grow with more months and more sites, while the engine's should stay roughly flat. That's a reasonable expectation, but these trials don't measure it, so it isn't claimed here.

## What changed in v3 (and the quality check)

v3 kept a change only if quality held:

- **`aie context`:** one command prints the status, gate results, and every site's briefing, including six-period breakdown history and investigation notes. Sessions no longer need to list folders or read raw state files to get oriented.
- **More evidence computed by the engine (verified):** efficiency by day of week, per-employee efficiency (internal, used for a "how broad is the change" summary), and average paid hours per shift. Earlier sessions kept writing their own scripts for these, and now they're verified numbers.
- **`aie-integrity claims`:** checks Claude's interpretation file directly before rendering, so a mis-cited number is caught in one cheap step instead of a full render and gate 2 cycle.
- **Shorter orchestration skill:** the troubleshooting skill now loads only when a gate fails. Every quality rule (cause testing, claim rules, qualitative checks) was kept.

Quality held: all four v3 runs found the true cause, cited the breadth and day-of-week evidence, released valid documents, and kept exploratory numbers out of customer documents. One QBR reply to the CSM misstated which classifications are excluded (it added contractors). That was a wording slip in the internal message, not in a customer document.

Sessions still ran small exploratory scripts (mostly earned hours per shift and hours by department). Making those engine metrics is the obvious next step.

## Quality: what each arm found

| | Plain Claude | Engine v1 | Engine v2 |
|---|---|---|---|
| Headline numbers correct (spot-checked against validated facts) | yes | yes | yes |
| Every number in customer docs independently verified | no | yes | yes |
| Problems that went quiet but never recovered | rebuilt from raw history each run | flagged automatically | flagged automatically |
| **Root cause:** site-wide change in the week of August 3, conveyor not the cause | **found (2/2)** | missed (0/2; leaned on the conveyor) | **found (4/4)** |
| Exploratory findings labeled as unverified | n/a | n/a | yes |

The planted story is a site-wide efficiency drop starting the week of August 3. Conveyor jams began that same week but don't cause it: processing ran 72.7% on jam days and 72.8% on other days.

The plain sessions found this by drilling into raw rows. Engine v1 didn't: its pre-summarized briefing showed big conveyor numbers, and its skills told Claude not to read raw files. **Plain Claude was the better analyst in that round, and that's how the gap was found.**

v2 closed the gap two ways:

1. **Driver evidence in the engine.** For each downtime reason, the engine now computes efficiency on event days vs. other days, plus a weekly trend that flags the largest week-to-week step. Both are implemented separately in each engine and checked by gate 1.
2. **Hypothesis testing in the skills.** Claude must check the driver evidence before naming a cause. It may run read-only scripts on the staged inputs, but anything those find is labeled *exploratory* and kept out of customer documents.

In all four v2 runs, the session named the site-wide change and the week it started, and told the CSM not to promise that fixing the conveyor would restore efficiency.

## Bottom line

Use this system for **trustworthy, consistent, faster** account analysis with memory. On tokens it's about even for small jobs and modestly cheaper for larger ones. Don't sell it on token savings.
