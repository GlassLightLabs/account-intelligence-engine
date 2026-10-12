"""Steps 3, 6 (prep), and 8: the internal briefing for the CSM and for Claude.

The briefing is NOT customer-facing. It lays out the current state, what
changed, signals, and investigations, then hands off to Claude for
interpretation and ends with a CSM action list.
"""

from __future__ import annotations

from .formatting import fmt_delta, fmt_value
from .investigations import site_items
from .store import AccountStore, write_json

ICON = {"risk": "RISK", "anomaly": "ANOMALY", "improvement": "WIN", "opportunity": "OPPORTUNITY"}


def _is_small(fmt: str, delta: float) -> bool:
    """Stability band for display: half a point for percentages, otherwise 2% of nothing (any change)."""
    return abs(delta) < 0.005 if fmt == "pct1" else delta == 0


def _evidence_line(sig: dict, spec: dict) -> str:
    ev = sig["evidence"]
    if "breakdown" in ev:
        fmt = spec["breakdowns"][ev["breakdown"]]["format"]
        prev = f" (previous top: {ev['previous_top']})" if ev.get("previous_top") else ""
        return f"'{ev['item']}' at {fmt_value(ev['value'], fmt)}{prev}"
    fmt = spec["metrics"][sig["metric"]]["format"]
    parts = [f"current {fmt_value(ev['current'], fmt)}"]
    if "streak" in ev:
        parts.append(f"{ev['direction']} {ev['streak']} periods in a row since {ev['start_period']} "
                     f"({fmt_value(ev['start_value'], fmt)}), total {fmt_delta(ev['total_change'], fmt)}")
    if "previous" in ev:
        parts.append(f"previous {fmt_value(ev['previous'], fmt)} ({ev['previous_period']})")
        parts.append(f"change {fmt_delta(ev['delta'], fmt)}")
    if "target" in ev:
        parts.append(f"target {fmt_value(ev['target'], fmt)}")
    if "zscore" in ev:
        parts.append(f"baseline {fmt_value(ev['baseline'], fmt)} over {', '.join(ev['baseline_periods'])}")
        parts.append(f"z = {ev['zscore']:.2f}")
    return "; ".join(parts)


def build_briefing(store: AccountStore, facts: dict) -> dict:
    spec = store.spec()
    site, period = facts["site"], facts["period"]
    comp, signals = facts["comparison"], facts["signals"]
    items = site_items(store, site)
    L: list[str] = []
    L += [f"# Briefing: {site}, {period}", "",
          f"Account: **{facts['account']}** | Pack: `{facts['pack']}` | Generated {facts['generated_at']}",
          "", "> Internal working document for the CSM and Claude. Not customer-facing.", ""]

    # 3. Current state
    prev = comp["previous_period"] or "none"
    L += ["## 1. Current state", "", f"Compared with previous period: **{prev}**", "",
          "| Metric | Current | Previous | Change | Assessment |", "|---|---|---|---|---|"]
    for m, ms in spec["metrics"].items():
        c = comp["metrics"][m]
        L.append(f"| {ms['label']} | {fmt_value(c['current'], ms['format'])} | "
                 f"{fmt_value(c['previous'], ms['format'])} | {fmt_delta(c['delta'], ms['format'])} | "
                 f"{c['assessment']} |")
    L.append("")

    # 4. What changed
    # Trend: the last six periods for the headline and report key metrics
    history = store.prior_facts(site, period, 5) + [facts]
    if len(history) > 1:
        key_metrics = spec.get("report", {}).get("key_metrics", list(spec["metrics"]))
        L += ["**Trend** (oldest to newest)", "", "| Metric | " + " | ".join(f["period"] for f in history) + " |",
              "|---|" + "---|" * len(history)]
        for m in key_metrics:
            ms = spec["metrics"][m]
            L.append(f"| {ms['label']} | " + " | ".join(fmt_value(f["metrics"][m]["value"], ms["format"])
                                                      for f in history) + " |")
        L.append("")
        for b, bspec in spec.get("breakdowns", {}).items():
            if bspec.get("compare") is False or bspec.get("internal"):
                continue
            keys = []
            for f in history:
                keys += [i["key"] for i in f["breakdowns"].get(b, {}).get("items", []) if i["key"] not in keys]
            if not keys:
                continue
            L += [f"**{bspec['label']}** (oldest to newest; blank = not in that period's list)", "",
                  "| | " + " | ".join(f["period"] for f in history) + " |", "|---|" + "---|" * len(history)]
            for k in keys:
                vals = []
                for f in history:
                    m = {i["key"]: i["value"] for i in f["breakdowns"].get(b, {}).get("items", [])}
                    vals.append(fmt_value(m[k], bspec["format"]) if k in m else "")
                L.append(f"| {k} | " + " | ".join(vals) + " |")
            L.append("")
    L += ["## 2. What changed", ""]
    moved = [(m, c) for m, c in comp["metrics"].items() if c["assessment"] not in ("stable", "n/a")]
    stable = [spec["metrics"][m]["label"] for m, c in comp["metrics"].items() if c["assessment"] == "stable"]
    for m, c in moved:
        ms = spec["metrics"][m]
        L.append(f"- **{ms['label']}** {c['assessment']}: {fmt_value(c['previous'], ms['format'])} -> "
                 f"{fmt_value(c['current'], ms['format'])} ({fmt_delta(c['delta'], ms['format'])})")
    for b, e in comp["breakdowns"].items():
        bspec = spec["breakdowns"][b]
        label = bspec["label"] + (" (internal only, never customer-facing)" if bspec.get("internal") else "")
        cur_map = {i["key"]: i["value"] for i in facts["breakdowns"].get(b, {}).get("items", [])}
        moves = []
        for key, d in e.get("deltas", {}).items():
            if not _is_small(bspec["format"], d):
                moves.append(f"{key} {fmt_value(cur_map[key] - d, bspec['format'])} -> "
                             f"{fmt_value(cur_map[key], bspec['format'])} ({fmt_delta(d, bspec['format'])})")
        if moves:
            L.append(f"- **{label}**: " + "; ".join(moves))
            still = [k for k, d in e.get("deltas", {}).items() if _is_small(bspec["format"], d)]
            if still:
                L.append(f"  - unchanged: {', '.join(still)}")
        if e["new"]:
            L.append(f"- **{label}**: new entries {', '.join(e['new'])}")
        if e["previous_top"] and e["current_top"] != e["previous_top"]:
            L.append(f"- **{label}**: top item changed from {e['previous_top']} to {e['current_top']}")
    if not moved and comp["previous_period"]:
        L.append("- No metric moved beyond its stability band.")
    if not comp["previous_period"]:
        L.append("- First period on record for this site. No comparison yet.")
    if stable:
        L.append(f"- Stable: {', '.join(stable)}")
    L.append("")

    # Drivers: evidence for or against candidate causes
    drv = facts["breakdowns"].get("downtime_day_efficiency", {}).get("items", [])
    weekly = []
    for f in store.prior_facts(site, period, 2) + [facts]:
        weekly += [(f["period"], i) for i in f["breakdowns"].get("weekly_efficiency", {}).get("items", [])]
    if drv or weekly:
        L += ["## 2b. Drivers (root-cause evidence)", "",
              "Use this before writing any hypothesis about cause. If efficiency is about the same on event "
              "days and other days, that downtime reason does **not** explain the efficiency level, even if "
              "it is large.", ""]
        pairs: dict[str, dict] = {}
        for i in drv:
            reason, side = i["key"].rsplit(": ", 1)
            pairs.setdefault(reason, {"departments": i.get("departments", [])})[side] = i["value"]
        for reason, p in pairs.items():
            on, off = p.get("event days"), p.get("other days")
            where = ", ".join(p["departments"])
            if on is None or off is None:
                L.append(f"- **{reason}** ({where}): only one side has data, no comparison possible.")
                continue
            gap = on - off
            verdict = ("no meaningful difference: not an explanation for the efficiency level"
                       if abs(gap) < 0.01 else
                       f"efficiency is {fmt_delta(abs(gap), 'pct1').lstrip('+')} "
                       f"{'lower' if gap < 0 else 'higher'} on event days")
            L.append(f"- **{reason}** ({where}): event days {fmt_value(on, 'pct1')} vs other days "
                     f"{fmt_value(off, 'pct1')} -> {verdict}. "
                     f"Cite as `<!--claim:downtime_day_efficiency[{reason}: event days]-->`.")
        emp_now = {i["key"]: i["value"] for i in facts["breakdowns"].get("employee_efficiency", {}).get("items", [])}
        prev_f = store.prior_facts(site, period, 1)
        prev_items = prev_f[0]["breakdowns"].get("employee_efficiency", {}).get("items", []) if prev_f else []
        emp_prev = {i["key"]: i["value"] for i in prev_items}
        both = sorted(set(emp_now) & set(emp_prev))
        if both:
            changes = sorted(emp_now[k] - emp_prev[k] for k in both)
            down = sum(1 for c in changes if c <= -0.01)
            up = sum(1 for c in changes if c >= 0.01)
            median = changes[len(changes) // 2] if len(changes) % 2 else (changes[len(changes) // 2 - 1]
                                                                          + changes[len(changes) // 2]) / 2
            L += ["", f"**Breadth (internal, individual-level):** of {len(both)} employees with data in both "
                      f"{prev_f[0]['period']} and {period}, {down} fell by at least 1 pt and {up} rose by at least "
                      f"1 pt; median change {fmt_delta(median, 'pct1')}. Most people moving the same way points to "
                      "a site-wide cause; a few people moving a lot points to individuals."]
        dow = facts["breakdowns"].get("weekday_efficiency", {}).get("items", [])
        if dow:
            L += ["", "**By day of week:** " + ", ".join(f"{i['key']} {fmt_value(i['value'], 'pct1')}" for i in dow)
                  + ". A flat pattern rules out day-specific causes (a shift, a delivery day)."]
        if weekly:
            L += ["", "**Weekly efficiency** (week starting; a week that spans two months appears once per month, "
                  "each with that month's days only)", "",
                  "| Period | Week of | Efficiency |", "|---|---|---|"]
            L += [f"| {per} | {i['key']} | {fmt_value(i['value'], 'pct1')} |" for per, i in weekly]
            steps = [(weekly[k - 1][1], weekly[k][1]) for k in range(1, len(weekly))
                     if weekly[k][1]["key"] != weekly[k - 1][1]["key"]]
            if steps:
                a, b = max(steps, key=lambda ab: abs(ab[1]["value"] - ab[0]["value"]))
                L += ["", f"Largest week-to-week move: week of {a['key']} -> week of {b['key']} "
                          f"({fmt_delta(b['value'] - a['value'], 'pct1')}). A sharp step suggests a specific "
                          "event or change around that date; a gradual slope suggests drift."]
        L.append("")

    # 5a. Signals
    L += ["## 3. Signals", ""]
    if signals:
        for s in signals:
            L.append(f"- [{ICON.get(s['kind'], s['kind'].upper())} / {s['severity']}] **{s['title']}**: "
                     f"{_evidence_line(s, spec)}")
    else:
        L.append("- No rules fired this period.")
    L.append("")

    # 5b. Investigations
    L += ["## 4. Investigations", ""]
    if items:
        for i in items:
            state = i["status"]
            if i.get("persisting"):
                state += ", NOT RECOVERED: rule went quiet but " + i["recovery_check"]["detail"]
                if i.get("reference_source"):
                    state += f"; cite the earlier level as `<!--claim:{i['reference_source']['claim']}-->`"
            L.append(f"- **{i['id']}** ({state}; opened {i['opened']}, last fired {i['last_seen']}): "
                     f"{i['title']}")
            for n in i["notes"][-3:]:
                L.append(f"  - note ({n['author']}, {n['ts'][:10]}): {n['text']}")
    else:
        L.append("- None open.")
    L.append("")

    # 6. Interpret (hand-off)
    L += ["## 5. For interpretation (Claude)", "",
          f"Write `briefings/{site}/{period}.interpretation.md`. Label every point as **Fact**, "
          "**Observation**, or **Hypothesis**. Every number must carry a claim marker, for example "
          "`81.2%<!--claim:efficiency-->`, `down 4.0 pts<!--claim:absdelta:efficiency-->`, or "
          "`72.7%<!--claim:efficiency_by_department[processing]-->`. "
          "Numbers without markers will be flagged by the integrity check.", ""]

    # 8. CSM action
    L += ["## 6. CSM action", "", "**Needs attention**", ""]
    attention = [s for s in signals if s["kind"] in ("risk", "anomaly")]
    persisting = [i for i in items if i.get("persisting")]
    L += ([f"- {s['title']}" for s in attention]
          + [f"- Still not recovered: {i['title']} ({i['recovery_check']['detail']})" for i in persisting]
          ) or ["- Nothing urgent."]
    L += ["", "**Questions to ask**", ""]
    qs: list[str] = []
    for s in signals:
        qs += [q for q in s["questions"] if q not in qs]
    L += [f"- {q}" for q in qs] or ["- None generated."]
    wins = [s for s in signals if s["kind"] in ("improvement", "opportunity")]
    L += ["", "**Wins to share**", ""] + ([f"- {s['title']}" for s in wins]
                                         or ["- None at this site this period. Run `aie status` for other sites."])
    L.append("")

    md = "\n".join(L)
    payload = {"site": site, "period": period, "previous_period": comp["previous_period"],
               "signals": signals, "investigations": [i["id"] for i in items],
               "attention": [s["id"] for s in attention], "questions": qs}
    store.briefing_file(site, period, "md").parent.mkdir(parents=True, exist_ok=True)
    store.briefing_file(site, period, "md").write_text(md, encoding="utf-8")
    write_json(store.briefing_file(site, period, "json"), payload)
    return payload
