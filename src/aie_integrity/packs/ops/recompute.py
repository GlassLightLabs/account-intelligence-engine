"""Independent recompute for the `ops` pack, written from the spec in
pack.yaml. Pure Python, no pandas, and no imports from the analysis engine.

Returns a flat dictionary so the comparison layer can check facts
metric by metric.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta


def recompute(tables: dict[str, list[dict]], spec: dict, period: str) -> dict:
    rules = spec["rules"]
    excluded_classes = {c.lower() for c in rules["efficiency_excluded_classifications"]}
    max_paid = float(rules["max_paid_hours_per_row"])
    max_ratio = float(rules["max_row_efficiency"])
    top_n = int(rules["top_n"])

    roster = {e["employee_id"]: e for e in tables["employees"]}

    buckets = {"out_of_period": 0, "duplicate": 0, "unmatched": 0, "policy": 0, "outlier": 0,
               "eligible": 0, "correction": 0}
    seen_rows: set[tuple] = set()
    paid_parts, earned_parts = [], []
    dept_paid: dict[str, list[float]] = defaultdict(list)
    dept_earned: dict[str, list[float]] = defaultdict(list)
    emp_lost: dict[str, list[float]] = defaultdict(list)
    kept: list[dict] = []   # eligible rows, for driver analysis

    for row in tables["labor"]:
        if not row["date"].startswith(period + "-"):
            buckets["out_of_period"] += 1
            continue
        signature = (row["date"], row["employee_id"], row["department"], row["paid_hours"], row["earned_hours"])
        if signature in seen_rows:
            buckets["duplicate"] += 1
            continue
        seen_rows.add(signature)
        person = roster.get(row["employee_id"])
        if person is None:
            buckets["unmatched"] += 1
            continue
        if person["classification"] in excluded_classes:
            buckets["policy"] += 1
            continue
        paid, earned = row["paid_hours"], row["earned_hours"]
        if paid == 0 or paid > max_paid or (paid > 0 and earned / paid > max_ratio):
            buckets["outlier"] += 1
            continue
        buckets["eligible"] += 1
        if paid < 0:
            buckets["correction"] += 1
        paid_parts.append(paid)
        earned_parts.append(earned)
        dept_paid[row["department"]].append(paid)
        dept_earned[row["department"]].append(earned)
        emp_lost[row["employee_id"]].append(paid - earned)
        kept.append(row)

    total_paid = math.fsum(paid_parts)
    total_earned = math.fsum(earned_parts)

    values = {
        "efficiency": (total_earned / total_paid) if total_paid > 0 else None,
        "paid_hours": total_paid,
        "earned_hours": total_earned,
        "lost_hours": total_paid - total_earned,
        "active_headcount": sum(1 for e in tables["employees"] if e["status"] == "active"),
        "outlier_rows": buckets["outlier"],
        "unmatched_rows": buckets["unmatched"],
        "duplicate_rows": buckets["duplicate"],
        "out_of_period_rows": buckets["out_of_period"],
        "correction_rows": buckets["correction"],
        "excluded_rows": buckets["outlier"] + buckets["unmatched"] + buckets["duplicate"] + buckets["out_of_period"],
        "policy_excluded_rows": buckets["policy"],
        "eligible_rows": buckets["eligible"],
    }

    breakdowns: dict[str, list[tuple[str, float]]] = {}
    dept = []
    for d in sorted(dept_paid):
        p = math.fsum(dept_paid[d])
        if p > 0:
            dept.append((d, math.fsum(dept_earned[d]) / p))
    breakdowns["efficiency_by_department"] = dept
    weights = {d: math.fsum(dept_paid[d]) for d in dept_paid}

    lost = sorted(((k, math.fsum(v)) for k, v in emp_lost.items()), key=lambda kv: (-kv[1], kv[0]))
    breakdowns["top_lost_hours_employees"] = lost[:top_n]

    if tables.get("downtime") is not None:
        minutes = [r["minutes"] for r in tables["downtime"]]
        values["downtime_hours"] = math.fsum(minutes) / 60
        by_reason: dict[str, list[float]] = defaultdict(list)
        for r in tables["downtime"]:
            by_reason[r["reason"]].append(r["minutes"])
        reasons = sorted(((k, math.fsum(v) / 60) for k, v in by_reason.items()), key=lambda kv: (-kv[1], kv[0]))
        breakdowns["downtime_by_reason"] = reasons[:top_n]
        drivers = []
        for reason, _hours in reasons[:top_n]:
            depts = {r["department"] for r in tables["downtime"] if r["reason"] == reason}
            days = {r["date"] for r in tables["downtime"] if r["reason"] == reason}
            sides = {"event days": ([], []), "other days": ([], [])}
            for row in kept:
                if row["department"] in depts:
                    side = sides["event days" if row["date"] in days else "other days"]
                    side[0].append(row["paid_hours"])
                    side[1].append(row["earned_hours"])
            for label, (p_list, e_list) in sides.items():
                p_sum = math.fsum(p_list)
                if p_sum > 0:
                    drivers.append((f"{reason}: {label}", math.fsum(e_list) / p_sum))
        breakdowns["downtime_day_efficiency"] = drivers
    else:
        values["downtime_hours"] = None

    week_paid: dict[str, list[float]] = defaultdict(list)
    week_earned: dict[str, list[float]] = defaultdict(list)
    for row in kept:
        d = date.fromisoformat(row["date"])
        monday = (d - timedelta(days=d.weekday())).isoformat()
        week_paid[monday].append(row["paid_hours"])
        week_earned[monday].append(row["earned_hours"])
    breakdowns["weekly_efficiency"] = [(w, math.fsum(week_earned[w]) / math.fsum(week_paid[w]))
                                       for w in sorted(week_paid) if math.fsum(week_paid[w]) > 0]

    names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    dow_p: dict[int, list[float]] = defaultdict(list)
    dow_e: dict[int, list[float]] = defaultdict(list)
    emp_p: dict[str, list[float]] = defaultdict(list)
    emp_e: dict[str, list[float]] = defaultdict(list)
    for row in kept:
        wd = date.fromisoformat(row["date"]).weekday()
        dow_p[wd].append(row["paid_hours"])
        dow_e[wd].append(row["earned_hours"])
        emp_p[row["employee_id"]].append(row["paid_hours"])
        emp_e[row["employee_id"]].append(row["earned_hours"])
    breakdowns["weekday_efficiency"] = [(names[d], math.fsum(dow_e[d]) / math.fsum(dow_p[d]))
                                        for d in sorted(dow_p) if math.fsum(dow_p[d]) > 0]
    breakdowns["employee_efficiency"] = [(k, math.fsum(emp_e[k]) / math.fsum(emp_p[k]))
                                         for k in sorted(emp_p) if math.fsum(emp_p[k]) > 0]
    values["paid_hours_per_shift"] = (total_paid / buckets["eligible"]) if buckets["eligible"] else None

    return {"values": values, "breakdowns": breakdowns, "department_weights": weights}


# ---- optional pack hooks used by the core validator -----------------------

def notes(mine: dict) -> list[str]:
    v = mine["values"]
    return [f"eligible {v['eligible_rows']}, policy-excluded {v['policy_excluded_rows']}, "
            f"outliers {v['outlier_rows']}, unknown employee {v['unmatched_rows']}, "
            f"duplicates {v['duplicate_rows']}, out of period {v['out_of_period_rows']}, "
            f"corrections {v['correction_rows']}"]


def cross_checks(facts: dict, mine: dict, tol: float) -> list[dict]:
    checks = []
    eff = mine["values"].get("efficiency")
    dept = facts["breakdowns"].get("efficiency_by_department")
    if dept and eff is not None:
        # department efficiencies, weighted by independently computed paid hours,
        # must recombine to the overall efficiency
        w = mine["department_weights"]
        total_w = sum(w.get(i["key"], 0) for i in dept["items"])
        if total_w > 0:
            recombined = sum(i["value"] * w.get(i["key"], 0) for i in dept["items"]) / total_w
            checks.append({"check": "efficiency_by_department.recombines",
                           "ok": abs(recombined - eff) <= 1e-6,
                           "message": "department efficiencies do not recombine to the overall efficiency",
                           "detail": {"expected": eff, "actual": recombined}})
    v = mine["values"]
    labor_rows = v["eligible_rows"] + v["policy_excluded_rows"] + v["unmatched_rows"] + v["outlier_rows"]
    if labor_rows:
        share = v["unmatched_rows"] / labor_rows
        checks.append({"check": "labor.roster_match", "ok": share <= 0.10, "level": "warning",
                       "message": f"{share:.0%} of in-period labor rows match no employee on the roster. "
                                  "Check that employee IDs are formatted the same in both files."})
    for metric, what in (("duplicate_rows", "exact duplicate labor rows were dropped (re-export overlap?)"),
                         ("out_of_period_rows", "labor rows dated outside the period were excluded")):
        if v[metric]:
            checks.append({"check": f"labor.{metric}", "ok": False, "level": "warning",
                           "message": f"{v[metric]} {what}"})
    reasons = facts["breakdowns"].get("downtime_by_reason")
    total = mine["values"].get("downtime_hours")
    if reasons and total is not None:
        checks.append({"check": "downtime_by_reason.within_total",
                       "ok": sum(i["value"] for i in reasons["items"]) <= total + tol,
                       "message": "reason totals exceed total downtime"})
    return checks


def explain_source_mismatch(mine: dict) -> str:
    v = mine["values"]
    if v["excluded_rows"]:
        return (f"Likely cause: this analysis excluded {v['excluded_rows']} problem rows (outliers "
                f"{v['outlier_rows']}, unknown employee {v['unmatched_rows']}, duplicates {v['duplicate_rows']}, "
                f"out of period {v['out_of_period_rows']}) that the source system may include.")
    return ""
