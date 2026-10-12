"""Validation gate 1: check a facts file against an independent recompute.

Categories
  source          files present, columns, row counts, every cell parses, date ranges
  provenance      input hashes match, every metric names a real source file and columns
  classification  row exclusion buckets match
  calculation     every headline metric matches
  aggregation     every breakdown item, ranking, and cross-totals match
  history         previous period, deltas, baselines, z-scores match
  signals         every signal's evidence matches and its rule condition actually holds
  source_system   totals the source system reports about itself (warning only)
"""

from __future__ import annotations

from .context import Account
from .readers import file_sha256
from .report import Report


def _close(a, b, tol: float) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= tol


def check_facts(acct: Account, site: str, period: str) -> dict:
    spec = acct.spec
    tol = float(spec.get("integrity", {}).get("tolerance_abs", 1e-6))
    rep = Report("facts", site, period)
    facts_path = acct.facts_path(site, period)
    facts = acct.load_facts(site, period)
    if facts is None:
        rep.add("source", "hard_fail", "facts_present", f"No facts file at {facts_path}")
        return _finish(acct, rep, site, period, None)

    rep.expect("source", "facts_identity", facts.get("site") == site and facts.get("period") == period,
               "facts file site/period does not match its location",
               expected=[site, period], actual=[facts.get("site"), facts.get("period")])

    # ---- source ingestion + provenance ----------------------------------
    data = acct.load(site, period)
    for name, fspec in spec["files"].items():
        info = data["files"].get(name)
        claimed = facts["inputs"].get(name)
        if info is None:
            if fspec.get("required"):
                rep.add("source", "hard_fail", f"{name}.present", "required input file is missing")
            rep.expect("provenance", f"{name}.not_claimed", claimed is None,
                       "facts cite an input file that is not in the account", claimed=claimed)
            continue
        rep.ok("source", f"{name}.present", file=info["file"])
        if not rep.expect("provenance", f"{name}.cited", claimed is not None,
                          "input file exists but facts do not cite it", file=info["file"]):
            continue
        rep.expect("provenance", f"{name}.sha256", claimed["sha256"] == info["sha256"],
                   "input file changed after analysis (hash mismatch)",
                   expected=info["sha256"], actual=claimed["sha256"])
        missing = [c for c in fspec["columns"] if c not in info["header"]]
        rep.expect("source", f"{name}.columns", not missing, "required columns missing", missing=missing)
        rep.expect("source", f"{name}.row_count", claimed["rows"] == info["rows"],
                   "row count differs from what the analysis read",
                   expected=info["rows"], actual=claimed["rows"])
        rep.expect("source", f"{name}.total_rows", claimed.get("total_rows", 0) == info["total_rows"],
                   "number of report-total rows skipped differs", expected=info["total_rows"],
                   actual=claimed.get("total_rows"))
        if info["total_rows"]:
            rep.add("source", "info", f"{name}.total_rows_skipped",
                    f"{info['total_rows']} report-total row(s) skipped")
        rep.expect("source", f"{name}.header_line", claimed.get("header_line") == info["header_line"],
                   "header row found on a different line", level="warning",
                   expected=info["header_line"], actual=claimed.get("header_line"))
        fails = data["failures"].get(name, [])
        if fails:
            rep.add("source", "hard_fail", f"{name}.cells_parse",
                    f"{len(fails)} cells are empty or unparseable", first=fails[:5])
        date_cols = [c for c, t in fspec["columns"].items() if t == "date"]
        if date_cols and info["rows"]:
            dates = [r[date_cols[0]] for r in data["tables"][name] if r.get(date_cols[0])]
            if dates:
                rep.expect("source", f"{name}.date_range",
                           claimed.get("date_min") == min(dates) and claimed.get("date_max") == max(dates),
                           "date range differs from what the analysis read",
                           expected=[min(dates), max(dates)],
                           actual=[claimed.get("date_min"), claimed.get("date_max")])
                outside = sum(1 for d in dates if d[:7] != period)
                rep.expect("source", f"{name}.dates_in_period", outside == 0,
                           f"{outside} rows are dated outside {period}", level="warning")
        key = fspec.get("key")
        if key:
            keys = [r[key] for r in data["tables"][name]]
            rep.expect("source", f"{name}.unique_{key}", len(keys) == len(set(keys)),
                       f"duplicate {key} values")
    rep.count_bulk("source", data["cells"] - sum(len(f) for f in data["failures"].values()))

    for name in facts["inputs"]:
        if name not in spec["files"]:
            rep.add("provenance", "hard_fail", f"{name}.unknown_input", "facts cite an input the pack does not define")

    cited_files = {m["file"]: k for k, m in facts["inputs"].items()}

    def check_source(label: str, src: dict | None, value) -> None:
        if src is None:
            rep.expect("provenance", f"{label}.source", value is None, "value has no source trail")
            return
        fkey = cited_files.get(src.get("file"))
        if not rep.expect("provenance", f"{label}.source_file", fkey is not None,
                          "source file is not one of the cited inputs", file=src.get("file")):
            return
        bad_cols = [c for c in src.get("columns", []) if c not in spec["files"][fkey]["columns"]]
        rep.expect("provenance", f"{label}.source_columns", not bad_cols,
                   "source names columns that are not in the file spec", columns=bad_cols)

    mine = acct.compute(site, period)
    if mine is None:
        rep.add("calculation", "hard_fail", "recompute", "could not recompute: inputs missing or unparseable")
        return _finish(acct, rep, site, period, facts_path)

    # ---- classification + calculations ----------------------------------
    for metric in spec["metrics"]:
        entry = facts["metrics"].get(metric)
        if not rep.expect("provenance", f"{metric}.present", entry is not None, "metric missing from facts"):
            continue
        check_source(metric, entry.get("source"), entry.get("value"))
        cat = "classification" if metric.endswith("_rows") else "calculation"
        rep.expect(cat, metric, _close(entry["value"], mine["values"].get(metric), tol),
                   "value does not match independent recompute",
                   expected=mine["values"].get(metric), actual=entry["value"])
    for note in getattr(acct.pack, "notes", lambda _m: [])(mine):
        rep.add("classification", "info", "pack_note", note)

    # ---- aggregations -----------------------------------------------------
    for name, bspec in spec.get("breakdowns", {}).items():
        claimed = facts["breakdowns"].get(name)
        expected = mine["breakdowns"].get(name)
        if expected is None:
            rep.expect("aggregation", f"{name}.present", claimed is None, "breakdown has no source data")
            continue
        if not rep.expect("aggregation", f"{name}.present", claimed is not None, "breakdown missing"):
            continue
        check_source(name, claimed.get("source"), True)
        exp_map = dict(expected)
        items = claimed["items"]
        for it in items:
            rep.expect("aggregation", f"{name}[{it['key']}]", _close(it["value"], exp_map.get(it["key"]), tol),
                       "item value does not match recompute (or item should not be listed)",
                       expected=exp_map.get(it["key"]), actual=it["value"])
        claimed_keys, exp_keys = [i["key"] for i in items], [k for k, _ in expected]
        if set(claimed_keys) == set(exp_keys):
            rep.ok("aggregation", f"{name}.membership")
        else:
            # allow a different member only when it ties with the boundary item
            boundary = expected[-1][1] if expected else None
            extra = [k for k in claimed_keys if k not in exp_keys]
            tied = boundary is not None and all(_close(next(i["value"] for i in items if i["key"] == k), boundary, tol)
                                                for k in extra)
            rep.expect("aggregation", f"{name}.membership", tied, "listed items differ from recompute",
                       expected=exp_keys, actual=claimed_keys)
        if bspec.get("ranked"):
            vals = [i["value"] for i in items]
            rep.expect("aggregation", f"{name}.ranking",
                       all(vals[i] >= vals[i + 1] - tol for i in range(len(vals) - 1)),
                       "items are not in descending order", actual=claimed_keys)
    # pack-specific consistency checks (cross-totals and the like)
    for chk in getattr(acct.pack, "cross_checks", lambda *_a: [])(facts, mine, tol):
        rep.expect("aggregation", chk["check"], chk["ok"], chk["message"], level=chk.get("level", "hard_fail"),
                   **chk.get("detail", {}))

    # ---- history ------------------------------------------------------------
    comp = facts.get("comparison", {})
    prev = acct.previous_period(site, period)
    rep.expect("history", "previous_period", comp.get("previous_period") == prev,
               "previous period differs", expected=prev, actual=comp.get("previous_period"))
    rep.expect("history", "baseline_periods", comp.get("baseline_periods") == acct.baseline_window(site, period),
               "baseline window differs", expected=acct.baseline_window(site, period),
               actual=comp.get("baseline_periods"))
    for metric, c in comp.get("metrics", {}).items():
        if prev is not None:
            rep.expect("history", f"{metric}.previous", _close(c.get("previous"), acct.value(site, prev, metric), tol),
                       "previous value differs", expected=acct.value(site, prev, metric), actual=c.get("previous"))
            rep.expect("history", f"{metric}.delta", _close(c.get("delta"), acct.delta(site, period, metric), tol),
                       "delta differs", expected=acct.delta(site, period, metric), actual=c.get("delta"))
        cnt, direc, start_p, start_v = acct.streak(site, period, metric)
        rep.expect("history", f"{metric}.streak",
                   c.get("streak", 0) == cnt and c.get("streak_direction") == direc
                   and c.get("streak_start_period") == start_p and _close(c.get("streak_start"), start_v, tol),
                   "streak differs", expected=[cnt, direc, start_p, start_v],
                   actual=[c.get("streak"), c.get("streak_direction"), c.get("streak_start_period"),
                           c.get("streak_start")])
        mean, sd, n = acct.baseline(site, period, metric)
        if mean is not None and c.get("current") is not None:
            rep.expect("history", f"{metric}.baseline", _close(c.get("baseline"), mean, tol),
                       "baseline differs", expected=mean, actual=c.get("baseline"))
            if sd:
                z = (c["current"] - mean) / sd
                rep.expect("history", f"{metric}.zscore", _close(c.get("zscore"), z, 1e-4),
                           "z-score differs", expected=z, actual=c.get("zscore"))

    # ---- signals --------------------------------------------------------------
    rules = spec.get("signals", {})
    for sig in facts.get("signals", []):
        sid, ev = sig["id"], sig["evidence"]
        rule = rules.get(sig["rule"])
        if not rep.expect("signals", f"{sid}.rule_exists", rule is not None, "signal cites an unknown rule"):
            continue
        m = rule.get("metric")
        if "current" in ev:
            rep.expect("signals", f"{sid}.current", _close(ev["current"], acct.value(site, period, m), tol),
                       "evidence value differs", expected=acct.value(site, period, m), actual=ev["current"])
        if "delta" in ev:
            d = acct.delta(site, period, m)
            rep.expect("signals", f"{sid}.delta", _close(ev["delta"], d, tol), "evidence delta differs",
                       expected=d, actual=ev["delta"])
            thr = float(rule["threshold"])
            rep.expect("signals", f"{sid}.condition",
                       d is not None and ((thr < 0 and d <= thr) or (thr >= 0 and d >= thr)),
                       "rule condition does not hold on recomputed data", delta=d, threshold=thr)
        if "target" in ev:
            target = spec.get("targets", {}).get(m)
            cur = acct.value(site, period, m)
            below = rule.get("direction", "below") == "below"
            rep.expect("signals", f"{sid}.condition",
                       ev["target"] == target and cur is not None and ((cur < target) if below else (cur > target)),
                       "target condition does not hold", current=cur, target=target)
        if "zscore" in ev:
            mean, sd, n = acct.baseline(site, period, m)
            cur = acct.value(site, period, m)
            z = (cur - mean) / sd if sd else None
            rep.expect("signals", f"{sid}.zscore", _close(ev["zscore"], z, 1e-4), "evidence z-score differs",
                       expected=z, actual=ev["zscore"])
            rep.expect("signals", f"{sid}.baseline", _close(ev["baseline"], mean, tol), "evidence baseline differs",
                       expected=mean, actual=ev["baseline"])
            thr = float(rule["threshold"])
            rep.expect("signals", f"{sid}.condition",
                       z is not None and n >= int(rule.get("min_history", 3))
                       and ((thr >= 0 and z >= thr) or (thr < 0 and z <= thr)),
                       "z-score rule condition does not hold", zscore=z, threshold=thr)
        if rule.get("type") == "trend":
            cnt, direc, start_p, start_v = acct.streak(site, period, m)
            cur = acct.value(site, period, m)
            total = None if cur is None or start_v is None else cur - start_v
            rep.expect("signals", f"{sid}.streak",
                       ev.get("streak") == cnt and ev.get("start_period") == start_p
                       and _close(ev.get("start_value"), start_v, tol) and _close(ev.get("total_change"), total, tol),
                       "trend evidence differs", expected=[cnt, start_p, start_v, total],
                       actual=[ev.get("streak"), ev.get("start_period"), ev.get("start_value"), ev.get("total_change")])
            rep.expect("signals", f"{sid}.condition",
                       direc == rule["direction"] and cnt >= int(rule["periods"]) and total is not None
                       and abs(total) >= float(rule.get("min_total", 0)),
                       "trend condition does not hold on recomputed data", streak=cnt, direction=direc, total=total)
        if "breakdown" in ev:
            val = acct.breakdown_item(site, period, ev["breakdown"], ev["item"])
            rep.expect("signals", f"{sid}.value", _close(ev["value"], val, tol), "evidence value differs",
                       expected=val, actual=ev["value"])
            k = int(rule.get("top_k", 1))
            mine_top = [key for key, _ in acct.compute(site, period)["breakdowns"].get(ev["breakdown"], [])[:k]]
            prev_comp = acct.compute(site, prev) if prev else None
            prev_top = [key for key, _ in (prev_comp or {"breakdowns": {}})["breakdowns"].get(ev["breakdown"], [])[:k]]
            rep.expect("signals", f"{sid}.condition", ev["item"] in mine_top and ev["item"] not in prev_top,
                       "item is not newly in the top ranks", current_top=mine_top, previous_top=prev_top)

    # ---- source system's own computed fields ---------------------------------
    reported = facts.get("source_reported") or {}
    rel_tol = float(spec.get("integrity", {}).get("source_summary_tolerance_rel", 0.005))
    if data["files"].get("source_summary"):
        own = {r["metric"]: r["value"] for r in data["tables"]["source_summary"]}
        rep.expect("source_system", "reported_values_read", own == reported,
                   "facts misreport what the source system said", expected=own, actual=reported)
        for metric, val in own.items():
            mv = mine["values"].get(metric)
            if mv is None:
                rep.add("source_system", "warning", f"{metric}.unknown",
                        "source reports a metric this pack does not compute")
                continue
            ok = abs(val - mv) <= rel_tol * max(abs(mv), 1e-9)
            explain = getattr(acct.pack, "explain_source_mismatch", None)
            hint = f" {explain(mine)}" if (not ok and explain) else ""
            rep.expect("source_system", metric, ok,
                       f"source system reports {val:,.4f}, independent recompute is {mv:,.4f}.{hint}",
                       level="warning", reported=val, recomputed=mv)

    return _finish(acct, rep, site, period, facts_path)


def _finish(acct: Account, rep: Report, site: str, period: str, facts_path) -> dict:
    sha = file_sha256(facts_path) if facts_path is not None and facts_path.is_file() else None
    return rep.write(acct.validation_path(site, period, "facts"),
                     acct.validation_path(site, period, "facts", "md"), facts_sha256=sha)
