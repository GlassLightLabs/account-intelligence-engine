"""Generate a fully synthetic demo dataset for the `ops` domain pack.

Nothing here comes from a real company. The fictional account is "Demo Co",
with three sites and six monthly periods. A few stories are planted so the
engine has something to find:

* site-01  steady performer. In 2026-07 a timekeeping glitch double-clocks a
           batch of shifts (outlier rows the engine must exclude, and a source
           system total that disagrees with ours).
* site-02  healthy, then slides in 2026-08 and 2026-09 as a new downtime
           reason ("conveyor jam") takes over.
* site-03  starts below target and improves every month. In 2026-06 a handful
           of labor rows point at employee IDs that do not exist.

Usage:
    python examples/generate_demo_data.py --out examples/demo-data
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

PERIODS = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
DEPARTMENTS = ["receiving", "processing", "packing", "shipping"]
DEPT_OFFSET = {"receiving": 0.02, "processing": -0.03, "packing": 0.01, "shipping": 0.0}
BASE_REASONS = ["changeover", "material shortage", "planned maintenance", "quality hold"]
REASON_WEIGHTS = [0.55, 0.2, 0.15, 0.1]

# Site-level efficiency for standard employees, by period.
SITE_EFF = {
    "site-01": [0.88, 0.885, 0.88, 0.875, 0.88, 0.882],
    "site-02": [0.87, 0.872, 0.868, 0.87, 0.825, 0.785],
    "site-03": [0.79, 0.81, 0.83, 0.85, 0.875, 0.895],
}


def workdays(period: str) -> list[date]:
    year, month = map(int, period.split("-"))
    d = date(year, month, 1)
    days = []
    while d.month == month:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def make_roster(rng: random.Random, site: str) -> list[dict]:
    roster = []
    prefix = {"site-01": "A", "site-02": "B", "site-03": "C"}[site]
    classes = ["standard"] * 32 + ["trainee"] * 3 + ["contractor"] * 3 + ["supervisor"] * 2
    for i, cls in enumerate(classes, start=1):
        roster.append({
            "employee_id": f"{prefix}{1000 + i}",
            "department": DEPARTMENTS[i % len(DEPARTMENTS)],
            "classification": cls,
            "status": "inactive" if i in (7, 23) else "active",
        })
    return roster


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def generate(out: Path, seed: int = 7) -> None:
    for site in SITE_EFF:
        rng = random.Random(f"{seed}-{site}")
        roster = make_roster(rng, site)
        for p_idx, period in enumerate(PERIODS):
            site_eff = SITE_EFF[site][p_idx]
            days = workdays(period)
            labor: list[dict] = []
            for emp in roster:
                if emp["status"] != "active":
                    continue
                skill = rng.gauss(0, 0.03)
                for d in days:
                    if rng.random() < 0.06:          # day off
                        continue
                    paid = round(rng.uniform(7.5, 9.0), 2)
                    eff = site_eff + DEPT_OFFSET[emp["department"]] + skill + rng.gauss(0, 0.05)
                    if emp["classification"] == "trainee":
                        eff -= 0.25
                    earned = round(max(paid * eff, 0.0), 2)
                    labor.append({
                        "date": d.isoformat(), "employee_id": emp["employee_id"],
                        "department": emp["department"], "paid_hours": paid,
                        "earned_hours": earned,
                    })

            # Planted: double-clocked shifts at site-01 in 2026-07.
            glitch_rows = []
            if site == "site-01" and period == "2026-07":
                for row in rng.sample(labor, 14):
                    row["paid_hours"] = round(row["paid_hours"] + rng.uniform(12, 15), 2)
                    glitch_rows.append(row)

            # Planted: rows for employees that are not on the roster at site-03 in 2026-06.
            if site == "site-03" and period == "2026-06":
                for k in range(12):
                    labor.append({
                        "date": days[k].isoformat(), "employee_id": f"C9{k:03d}",
                        "department": "packing", "paid_hours": 8.0, "earned_hours": 6.9,
                    })

            downtime: list[dict] = []
            for d in days:
                for dept in DEPARTMENTS:
                    if rng.random() < 0.6:
                        downtime.append({
                            "date": d.isoformat(), "department": dept,
                            "reason": rng.choices(BASE_REASONS, REASON_WEIGHTS)[0],
                            "minutes": round(rng.uniform(20, 40), 1),
                        })
                # Planted: conveyor jams take over at site-02.
                if site == "site-02" and period in ("2026-08", "2026-09"):
                    rate = 0.55 if period == "2026-08" else 0.85
                    if rng.random() < rate:
                        downtime.append({
                            "date": d.isoformat(), "department": "processing",
                            "reason": "conveyor jam",
                            "minutes": round(rng.uniform(60, 150), 1),
                        })

            # The "source system" reports its own totals. It applies the
            # classification exclusions but NOT the outlier rule, so it agrees
            # with us everywhere except where outliers exist.
            eligible_ids = {
                e["employee_id"] for e in roster
                if e["classification"] not in ("trainee", "supervisor")
            }
            src_rows = [r for r in labor if r["employee_id"] in eligible_ids]
            src_paid = sum(r["paid_hours"] for r in src_rows)
            src_earned = sum(r["earned_hours"] for r in src_rows)
            summary = [
                {"metric": "paid_hours", "value": round(src_paid, 2)},
                {"metric": "earned_hours", "value": round(src_earned, 2)},
                {"metric": "efficiency", "value": round(src_earned / src_paid, 4)},
            ]

            rng.shuffle(labor)
            labor.sort(key=lambda r: r["date"])
            base = out / site / period
            write_csv(base / "employees.csv",
                      ["employee_id", "department", "classification", "status"], roster)
            write_csv(base / "labor.csv",
                      ["date", "employee_id", "department", "paid_hours", "earned_hours"], labor)
            write_csv(base / "downtime.csv", ["date", "department", "reason", "minutes"], downtime)
            write_csv(base / "source_summary.csv", ["metric", "value"], summary)
    print(f"Demo data written to {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="examples/demo-data", type=Path)
    ap.add_argument("--seed", default=7, type=int)
    args = ap.parse_args()
    generate(args.out, args.seed)


if __name__ == "__main__":
    main()
