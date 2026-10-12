"""Step 4: compare the current snapshot to history. What changed, what is new,
what is stable."""

from __future__ import annotations

import statistics


def _val(facts: dict, metric: str):
    m = facts["metrics"].get(metric)
    return None if m is None else m["value"]


def _is_stable(fmt: str, prev: float, delta: float) -> bool:
    if fmt == "pct1":
        return abs(delta) < 0.005
    return abs(delta) <= 0.02 * abs(prev) if prev else delta == 0


def _streak(prior: list[dict], current: dict, metric: str) -> dict:
    """Consecutive period-over-period moves in the same direction, ending now.
    A move is a strict increase or decrease. Missing values break the streak."""
    series = [(f["period"], _val(f, metric)) for f in prior] + [(current["period"], _val(current, metric))]
    out = {"streak": 0, "streak_direction": None, "streak_start_period": None, "streak_start": None}
    if len(series) < 2 or series[-1][1] is None or series[-2][1] is None or series[-1][1] == series[-2][1]:
        return out
    up = series[-1][1] > series[-2][1]
    n, i = 0, len(series) - 1
    while i > 0 and series[i][1] is not None and series[i - 1][1] is not None \
            and series[i][1] != series[i - 1][1] and (series[i][1] > series[i - 1][1]) == up:
        n += 1
        i -= 1
    return {"streak": n, "streak_direction": "up" if up else "down",
            "streak_start_period": series[i][0], "streak_start": series[i][1]}


def compare(current: dict, prior: list[dict], spec: dict) -> dict:
    """`prior` is every stored period before the current one, oldest first."""
    n_base = int(spec["rules"]["baseline_periods"])
    previous = prior[-1] if prior else None
    base_window = prior[-n_base:]
    out = {
        "previous_period": previous["period"] if previous else None,
        "baseline_periods": [f["period"] for f in base_window],
        "metrics": {},
        "breakdowns": {},
    }
    for metric, mspec in spec["metrics"].items():
        cur = _val(current, metric)
        entry: dict = {"current": cur, "previous": None, "delta": None, "baseline": None,
                       "stdev": None, "zscore": None, "assessment": "n/a"}
        if previous is not None:
            entry["previous"] = _val(previous, metric)
        if cur is not None and previous is not None and _val(previous, metric) is not None:
            prev = _val(previous, metric)
            delta = cur - prev
            entry.update(previous=prev, delta=round(delta, 10))
            hib = mspec.get("higher_is_better")
            if _is_stable(mspec["format"], prev, delta):
                entry["assessment"] = "stable"
            elif hib is None:
                entry["assessment"] = "up" if delta > 0 else "down"
            else:
                entry["assessment"] = "better" if (delta > 0) == hib else "worse"
        hist = [_val(f, metric) for f in base_window]
        hist = [h for h in hist if h is not None]
        if cur is not None and hist:
            base = statistics.fmean(hist)
            entry["baseline"] = round(base, 10)
            if len(hist) >= 2:
                sd = statistics.stdev(hist)
                entry["stdev"] = round(sd, 10)
                if sd > 0:
                    entry["zscore"] = round((cur - base) / sd, 6)
        entry["history_count"] = len(hist)
        entry.update(_streak(prior, current, metric))
        out["metrics"][metric] = entry

    for name, bspec in spec.get("breakdowns", {}).items():
        if bspec.get("compare") is False:
            continue
        cur_items = current["breakdowns"].get(name, {}).get("items", [])
        prev_items = previous["breakdowns"].get(name, {}).get("items", []) if previous else []
        cur_keys = [i["key"] for i in cur_items]
        prev_keys = [i["key"] for i in prev_items]
        entry = {
            "current_top": cur_keys[0] if cur_keys else None,
            "previous_top": prev_keys[0] if prev_keys else None,
            "previous_keys": prev_keys,
            "new": [k for k in cur_keys if previous and k not in prev_keys],
            "dropped": [k for k in prev_keys if k not in cur_keys],
        }
        if not bspec.get("ranked"):
            prev_map = {i["key"]: i["value"] for i in prev_items}
            entry["deltas"] = {i["key"]: round(i["value"] - prev_map[i["key"]], 10)
                               for i in cur_items if i["key"] in prev_map}
        out["breakdowns"][name] = entry
    return out
