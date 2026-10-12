"""Analysis for the `ops` pack (pandas implementation).

The integrity engine has its own, separately written implementation of the
same spec in `aie_integrity/packs/ops/recompute.py`. Do not import across.
"""

from __future__ import annotations

import pandas as pd

LABOR = "labor.csv"


def _r(x: float) -> float:
    return round(float(x), 10)


def analyze(frames: dict[str, pd.DataFrame], spec: dict, input_meta: dict, period: str) -> dict:
    rules = spec["rules"]
    top_n = int(rules["top_n"])
    labor = frames["labor"].copy()
    emp = frames["employees"]
    labor_file = input_meta["labor"]["file"]
    emp_file = input_meta["employees"]["file"]

    out_of_period = labor["date"].str[:7] != period
    # duplicates are judged among in-period rows only
    duplicate = pd.Series(False, index=labor.index)
    in_period = labor[~out_of_period]
    duplicate.loc[in_period.index] = in_period.duplicated(keep="first")
    seen = ~out_of_period & ~duplicate
    cls = labor["employee_id"].map(dict(zip(emp["employee_id"], emp["classification"], strict=True)))
    unmatched = seen & cls.isna()
    excluded_cls = [c.lower() for c in rules["efficiency_excluded_classifications"]]
    policy = seen & ~unmatched & cls.isin(excluded_cls)
    paid_h = labor["paid_hours"]
    ratio = labor["earned_hours"] / paid_h.where(paid_h > 0)
    outlier = seen & ~unmatched & ~policy & (
        (paid_h == 0)
        | (paid_h > float(rules["max_paid_hours_per_row"]))
        | (ratio > float(rules["max_row_efficiency"]))
    )
    usable = seen & ~unmatched & ~policy & ~outlier
    eligible = labor[usable].copy()

    paid = eligible["paid_hours"].sum()
    earned = eligible["earned_hours"].sum()
    efficiency = earned / paid if paid > 0 else None

    def src(file: str, columns: list[str], rule: str) -> dict:
        return {"file": file, "columns": columns, "rule": rule}

    metrics = {
        "efficiency": {"value": None if efficiency is None else _r(efficiency),
                       "source": src(labor_file, ["earned_hours", "paid_hours"],
                                     "sum(earned_hours) / sum(paid_hours), eligible rows")},
        "paid_hours": {"value": _r(paid), "source": src(labor_file, ["paid_hours"], "sum, eligible rows")},
        "earned_hours": {"value": _r(earned), "source": src(labor_file, ["earned_hours"], "sum, eligible rows")},
        "paid_hours_per_shift": {"value": _r(paid / len(eligible)) if len(eligible) else None,
                                 "source": src(labor_file, ["paid_hours"], "sum(paid_hours) / eligible rows")},
        "lost_hours": {"value": _r(paid - earned),
                       "source": src(labor_file, ["paid_hours", "earned_hours"], "paid - earned, eligible rows")},
        "active_headcount": {"value": int((emp["status"] == "active").sum()),
                             "source": src(emp_file, ["status"], "count where status = active")},
        "outlier_rows": {"value": int(outlier.sum()),
                         "source": src(labor_file, ["paid_hours", "earned_hours"], "rows breaking outlier limits")},
        "unmatched_rows": {"value": int(unmatched.sum()),
                           "source": src(labor_file, ["employee_id"], "employee_id not in employees")},
        "duplicate_rows": {"value": int(duplicate.sum()),
                           "source": src(labor_file, ["date", "employee_id", "department", "paid_hours",
                                                      "earned_hours"], "identical to an earlier row")},
        "out_of_period_rows": {"value": int(out_of_period.sum()),
                               "source": src(labor_file, ["date"], "date not in the analyzed period")},
        "correction_rows": {"value": int((usable & (paid_h < 0)).sum()),
                            "source": src(labor_file, ["paid_hours"], "eligible rows with negative paid_hours")},
        "excluded_rows": {"value": int(outlier.sum() + unmatched.sum() + duplicate.sum() + out_of_period.sum()),
                          "source": src(labor_file, ["date", "employee_id", "paid_hours", "earned_hours"],
                                        "out_of_period + duplicate + unmatched + outlier rows")},
        "policy_excluded_rows": {"value": int(policy.sum()),
                                 "source": src(labor_file, ["employee_id"],
                                               "classification in efficiency_excluded_classifications")},
    }

    breakdowns: dict[str, dict] = {}
    by_dept = eligible.groupby("department")[["earned_hours", "paid_hours"]].sum().sort_index()
    breakdowns["efficiency_by_department"] = {
        "items": [{"key": d, "value": _r(r.earned_hours / r.paid_hours)}
                  for d, r in by_dept.iterrows() if r.paid_hours > 0],
        "source": src(labor_file, ["department", "earned_hours", "paid_hours"],
                      "efficiency per department, eligible rows"),
    }

    eligible["lost"] = eligible["paid_hours"] - eligible["earned_hours"]
    lost = eligible.groupby("employee_id")["lost"].sum().reset_index()
    lost = lost.sort_values(["lost", "employee_id"], ascending=[False, True]).head(top_n)
    breakdowns["top_lost_hours_employees"] = {
        "items": [{"key": r.employee_id, "value": _r(r.lost)} for r in lost.itertuples()],
        "source": src(labor_file, ["employee_id", "paid_hours", "earned_hours"],
                      f"top {top_n} employees by paid - earned, eligible rows"),
    }

    if "downtime" in frames:
        dt = frames["downtime"]
        dt_file = input_meta["downtime"]["file"]
        metrics["downtime_hours"] = {"value": _r(dt["minutes"].sum() / 60),
                                     "source": src(dt_file, ["minutes"], "sum(minutes) / 60")}
        by_reason = (dt.groupby("reason")["minutes"].sum() / 60).reset_index()
        by_reason = by_reason.sort_values(["minutes", "reason"], ascending=[False, True]).head(top_n)
        breakdowns["downtime_by_reason"] = {
            "items": [{"key": r.reason, "value": _r(r.minutes)} for r in by_reason.itertuples()],
            "source": src(dt_file, ["reason", "minutes"], f"top {top_n} reasons by hours"),
        }
        drivers = []
        for reason in [i["key"] for i in breakdowns["downtime_by_reason"]["items"]]:
            events = dt[dt["reason"] == reason]
            scope = eligible[eligible["department"].isin(set(events["department"]))]
            on_day = scope["date"].isin(set(events["date"]))
            for label, part in (("event days", scope[on_day]), ("other days", scope[~on_day])):
                if part["paid_hours"].sum() > 0:
                    drivers.append({"key": f"{reason}: {label}",
                                    "value": _r(part["earned_hours"].sum() / part["paid_hours"].sum()),
                                    "departments": sorted(set(events["department"]))})
        breakdowns["downtime_day_efficiency"] = {
            "items": drivers,
            "source": src(dt_file, ["date", "department", "reason"],
                          "efficiency of eligible labor in affected departments, event days vs other days"),
        }
    else:
        metrics["downtime_hours"] = {"value": None, "source": None}

    weeks = pd.to_datetime(eligible["date"])
    eligible["week"] = (weeks - pd.to_timedelta(weeks.dt.weekday, unit="D")).dt.strftime("%Y-%m-%d")
    by_week = eligible.groupby("week")[["earned_hours", "paid_hours"]].sum().sort_index()
    breakdowns["weekly_efficiency"] = {
        "items": [{"key": w, "value": _r(r.earned_hours / r.paid_hours)} for w, r in by_week.iterrows()
                  if r.paid_hours > 0],
        "source": src(labor_file, ["date", "earned_hours", "paid_hours"], "efficiency by week (Monday start)"),
    }

    days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    eligible["dow"] = weeks.dt.weekday
    by_dow = eligible.groupby("dow")[["earned_hours", "paid_hours"]].sum().sort_index()
    breakdowns["weekday_efficiency"] = {
        "items": [{"key": days[d], "value": _r(r.earned_hours / r.paid_hours)} for d, r in by_dow.iterrows()
                  if r.paid_hours > 0],
        "source": src(labor_file, ["date", "earned_hours", "paid_hours"], "efficiency by day of week"),
    }
    by_emp = eligible.groupby("employee_id")[["earned_hours", "paid_hours"]].sum().sort_index()
    breakdowns["employee_efficiency"] = {
        "items": [{"key": e, "value": _r(r.earned_hours / r.paid_hours)} for e, r in by_emp.iterrows()
                  if r.paid_hours > 0],
        "source": src(labor_file, ["employee_id", "earned_hours", "paid_hours"], "efficiency per employee"),
    }

    source_reported = {}
    if "source_summary" in frames:
        ss = frames["source_summary"]
        source_reported = {r.metric: float(r.value) for r in ss.itertuples()}

    return {"metrics": metrics, "breakdowns": breakdowns, "source_reported": source_reported}
