# Field testing

Passing its own tests on its own demo data proves the machinery works. It doesn't prove the system holds up when a different operator drives it, or when the data is messy. So two more tests were run, and everything they found was fixed and turned into a regression test.

## Test 1: a cold-start Claude session runs the skills

**Setup.** A fresh Claude session got only the three `SKILL.md` files, the installed CLIs, and an account folder with April to August already loaded. It got no repo access, no examples, and no hints. It was then given a realistic CSM request and asked to report every command it ran plus any friction in the skills.

**Request (rounds 1 and 2):** *"September data for site-02 just came in. Process it, tell me what needs my attention before my call with their ops director Thursday, and get me the customer-ready site overview I can send after the call."*

**Request (round 3, harder):** *"September exports for all three sites are in. I've got the QBR with their VP of Operations next week. Give me the account-level story (what's working, what isn't, what I should push on) and customer-ready overviews for every site."*

In all three rounds the session followed the gates in order, never computed a number itself, tagged every number in the customer documents, and got every document RELEASED. What changed from round to round was the quality of what it found, and the friction it reported.

| Round | What the session caught or hit | Fix |
|---|---|---|
| 1 | **A real design flaw.** A downtime investigation had quietly moved to *watching* even though downtime was still about double its normal level. The z-score rule stopped firing because the spike had become part of the baseline. | Investigations now store a pre-problem **reference** value. Only a return toward that reference counts as recovery. A quiet rule with an unrecovered metric shows as **NOT RECOVERED**, both in the briefing and in the customer document. |
| 1 | It had to read raw files to work out which period the data was for. | `aie run` infers the period from the input dates (and refuses if they span several months). |
| 1 | "down -4.0 pts" reads as a double negative, and there was no way to cite a department's change. | New claim forms `absdelta:` and `delta:breakdown[key]`. Gate 2 verifies both. |
| 1 | The customer document still contained the hidden validation tags. | `aie export` writes clean `.customer.md` and `.customer.html` copies, and only for RELEASED, unchanged documents. |
| 1 | Employee-level data appeared in the briefing with no guidance. | Packs can mark breakdowns `internal: true`. Gate 2 **hard-fails** any customer document that cites one. |
| 2 | **A regression I introduced in round 1's fixes.** Tightening how category text is cleaned turned `paid_hours` into `paid hours`, so the source-system cross-check silently skipped two of its three metrics. The session spotted an INFO line that kept repeating. | New `key` column type for identifiers. An unknown metric is now a **warning**, not info. A regression test asserts the cross-check runs every month. |
| 2 | **A skill example taught a wrong number.** It labeled a baseline average as "July". The session copied the pattern, and gate 2 correctly blocked it. | The example was fixed, and every claim example in the skills is now **resolved against the demo account by the test suite**. (Round 3 then caught a second wrong example. That test is why it can't happen again.) |
| 2 | Gate 2 verifies numbers, not words. The session nearly wrote "every department slipped" when one was flat. | The skill now requires checking words like *all, every, first, only, none* against the facts. The briefing lists items that stayed unchanged. |
| 3 | **A detection gap.** Site-03 had improved five months in a row for a total of +9.5 points, but no single month crossed the +3 point threshold, so the engine never flagged the account's best QBR story. | New `trend` rule type (`sustained_gain`, `sustained_decline`), verified independently by the integrity engine, plus a six-period **Trend** table in every briefing. |
| 3 | There was no path for an account-level story. The account summary omitted problems that had not recovered. | A QBR row in the orchestration skill. Unrecovered items now appear in the account summary flags. |
| 3 | Documents showed internal site codes. | `aie name ACCOUNT site-01 "Riverside plant"` sets the display name used in documents. |

## Test 2: messy data

`scripts/stress_test.py` takes one clean month, applies one realistic export problem at a time, runs the full pipeline and gate 1, and compares the result with the known-correct answer. It runs in CI and **fails the build if any scenario produces wrong numbers silently, or crashes**.

**Before fixes:** of 18 scenarios, 1 crashed, 6 were rejected, 4 were wrong but flagged, and 7 were handled. Two findings stood out:

- **Engine disagreement on trailing empty rows.** The pandas engine read `,,,,` lines as data and rejected the file, while the stdlib validator skipped them. Two independent readers disagreeing is exactly the class of bug the two-engine design exists to surface.
- **Duplicate rows were caught by luck.** They showed up only because the customer's own system totals disagreed. Without that file, they would have been silent.

**After fixes:** 23 scenarios. 21 are handled with correct numbers, and 2 are rejected on purpose with a clear message:

- A rehired employee listed twice: there's no safe way to guess which record is current.
- A date column mixing two formats: guessing could swap months and days.

Every rule added along the way (header detection, delimiter detection, total and repeated-header rows, duplicates, reversals, out-of-period rows, ID and category normalization, thousands separators) went into `pack.yaml` as plain-language spec first, then was implemented separately in each engine.

Full results: [stress-test-results.md](stress-test-results.md)

## Honest limits of these tests

- **Same author for both engines.** The validator shares no code with the analysis engine and uses different libraries and a different math path, but the same person wrote both. A truly independent reimplementation by someone else would be a stronger test.
- **Synthetic messiness.** The scenarios are the export problems I've seen most often. Real systems will find others, and the stress harness is built so each new one becomes a single function.
- **Thresholds aren't tuned to real accounts.** Detection thresholds (3 points, z of 2, a 25% change) are reasonable defaults, not values fitted to real operations data.
