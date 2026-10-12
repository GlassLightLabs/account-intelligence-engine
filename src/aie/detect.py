"""Step 5a: turn comparisons into signals using the rules in the pack spec.

Rule types
  delta         current - previous crosses `threshold` (negative = drop, positive = rise)
  target        current is below/above `targets[metric]`
  zscore        current vs trailing baseline exceeds `threshold` standard deviations
                (and, if set, differs from the baseline by at least `min_change_rel`)
  new_top_item  a key enters the top `top_k` of a ranked breakdown
  trend         the metric moved the same `direction` for at least `periods` periods in a row,
                with a total change of at least `min_total` (catches slow, steady shifts)
"""

from __future__ import annotations

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _fmt(text: str, **kw) -> str:
    try:
        return text.format(**kw)
    except (KeyError, IndexError):
        return text


def detect(site: str, period: str, current: dict, comparison: dict, spec: dict) -> list[dict]:
    signals: list[dict] = []
    for rule_name, rule in spec.get("signals", {}).items():
        typ = rule["type"]
        evidence: dict | None = None
        item = None
        if typ == "delta":
            c = comparison["metrics"].get(rule["metric"], {})
            d, thr = c.get("delta"), float(rule["threshold"])
            if d is not None and ((thr < 0 and d <= thr) or (thr >= 0 and d >= thr)):
                evidence = {"current": c["current"], "previous": c["previous"], "delta": d,
                            "previous_period": comparison["previous_period"], "threshold": thr}
        elif typ == "target":
            c = comparison["metrics"].get(rule["metric"], {})
            target = spec.get("targets", {}).get(rule["metric"])
            cur = c.get("current")
            if cur is not None and target is not None:
                below = rule.get("direction", "below") == "below"
                if (below and cur < target) or (not below and cur > target):
                    evidence = {"current": cur, "target": target}
        elif typ == "zscore":
            c = comparison["metrics"].get(rule["metric"], {})
            z, thr = c.get("zscore"), float(rule["threshold"])
            base = c.get("baseline")
            rel = (c["current"] - base) / abs(base) if base else None
            min_rel = rule.get("min_change_rel")
            big_enough = min_rel is None or (rel is not None and abs(rel) >= float(min_rel))
            if (z is not None and big_enough and c.get("history_count", 0) >= int(rule.get("min_history", 3))
                    and ((thr >= 0 and z >= thr) or (thr < 0 and z <= thr))):
                evidence = {"current": c["current"], "baseline": c["baseline"], "stdev": c["stdev"],
                            "zscore": z, "baseline_periods": comparison["baseline_periods"],
                            "threshold": thr}
        elif typ == "trend":
            c = comparison["metrics"].get(rule["metric"], {})
            n, direction = c.get("streak", 0), c.get("streak_direction")
            if direction == rule["direction"] and n >= int(rule["periods"]):
                total = c["current"] - c["streak_start"]
                if abs(total) >= float(rule.get("min_total", 0)):
                    evidence = {"current": c["current"], "streak": n, "direction": direction,
                                "start_period": c["streak_start_period"], "start_value": c["streak_start"],
                                "total_change": round(total, 10)}
        elif typ == "new_top_item":
            if comparison["previous_period"] is None:
                continue
            k = int(rule.get("top_k", 1))
            cur_items = current["breakdowns"].get(rule["breakdown"], {}).get("items", [])[:k]
            entry = comparison["breakdowns"].get(rule["breakdown"], {})
            prev_top = entry.get("previous_top")
            prev_keys = set(entry.get("previous_keys", [])[:k])
            if not prev_keys:
                continue
            fresh = [i for i in cur_items if i["key"] not in prev_keys]
            if fresh:
                item = fresh[0]["key"]
                evidence = {"breakdown": rule["breakdown"], "item": item, "value": fresh[0]["value"],
                            "previous_top": prev_top, "previous_period": comparison["previous_period"]}
        else:
            raise ValueError(f"Unknown signal rule type {typ!r} in rule {rule_name}")

        if evidence is None:
            continue
        ctx = {"site": site, "period": period, "item": item or ""}
        signals.append({
            "id": f"{site}:{period}:{rule_name}",
            "rule": rule_name,
            "kind": rule.get("kind", "risk"),
            "severity": rule.get("severity", "medium"),
            "investigate": bool(rule.get("investigate", False)),
            "site": site,
            "period": period,
            "metric": rule.get("metric"),
            "title": _fmt(rule.get("title", rule_name), **ctx),
            "evidence": evidence,
            "questions": [_fmt(q, **ctx) for q in rule.get("questions", [])],
        })
    signals.sort(key=lambda s: (SEVERITY_ORDER.get(s["severity"], 9), s["rule"]))
    return signals
