# Sample output

Real output from `bash examples/run_demo.sh`, committed so you can see what the engine produces without installing anything. All data is synthetic. Regenerate with `bash examples/refresh_samples.sh`.

| File | What it is | Who reads it |
|---|---|---|
| [00-status.txt](00-status.txt) | `aie status`: one line per site | CSM |
| [01-briefing-site-02-2026-09.md](01-briefing-site-02-2026-09.md) | Internal briefing: current state, what changed, signals, investigations, questions to ask | CSM and Claude |
| [02-site-overview-site-02-2026-09.md](02-site-overview-site-02-2026-09.md) | Customer-ready site overview, including Claude's interpretation | Customer |
| [02-analysis-site-02-2026-09.xlsx](02-analysis-site-02-2026-09.xlsx) | Analysis workbook: metrics, breakdowns, signals, provenance | Customer or analyst |
| [03-account-summary.md](03-account-summary.md) | Rolling cross-site account view | CSM and leadership |
| [04-integrity-facts-site-01-2026-07.md](04-integrity-facts-site-01-2026-07.md) | Gate 1 report for a month with a timekeeping glitch. Validated, with warnings that explain why the customer's own system shows different totals. | CSM |
| [05-integrity-docs-site-02-2026-09.md](05-integrity-docs-site-02-2026-09.md) | Gate 2 report: every number in the customer document checked | CSM |
| [06-integrity-BLOCKED-example.md](06-integrity-BLOCKED-example.md) | What happens when one number in a finished document is hand-edited | CSM |

**Tip:** the customer document looks like plain Markdown on GitHub. Open it in raw view to see the hidden claim markers (`<!--claim:...-->`) behind every number, which gate 2 uses to verify it.
