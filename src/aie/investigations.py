"""Step 5b: maintain investigations, known issues, and open questions across
periods.

Lifecycle per site + rule:
  open      the rule fired this period (new item, or an existing one fired again),
            OR the rule went quiet but the metric has not recovered (see below)
  watching  the rule stopped firing AND the metric is back near where it was
            before the problem started; waiting to see if it stays there
  resolved  recovered for `resolve_after_clean_periods` periods in a row

Why "recovered" and not just "the rule stopped firing": rules compare against
recent history, and history absorbs a problem. A downtime spike that persists
becomes the new baseline, so the z-score rule goes quiet even though nothing
improved. Each item therefore stores a `reference` value from before the problem,
and only a return toward that reference counts as recovery.
A resolved item that fires again is reopened, keeping its history.
Re-running a period that was already evaluated changes nothing.
"""

from __future__ import annotations

from .store import AccountStore, now_iso, read_json, write_json


def _reference(sig: dict, rule: dict):
    ev = sig["evidence"]
    return {"delta": ev.get("previous"), "zscore": ev.get("baseline"), "target": ev.get("target"),
            "new_top_item": ev.get("item"), "trend": ev.get("start_value")}.get(rule["type"])


def _reference_source(sig: dict, rule: dict) -> dict | None:
    """Where the reference value comes from, as a label and a claim reference that gate 2 can verify."""
    ev, site, period, m = sig["evidence"], sig["site"], sig["period"], rule.get("metric")
    if rule["type"] == "delta" and ev.get("previous_period"):
        return {"label": f"{ev['previous_period']} value", "claim": f"{site}@{ev['previous_period']}:{m}"}
    if rule["type"] == "trend" and ev.get("start_period"):
        return {"label": f"{ev['start_period']} value, before the slide began",
                "claim": f"{site}@{ev['start_period']}:{m}"}
    if rule["type"] == "zscore":
        span = ev.get("baseline_periods") or []
        label = f"average of {span[0]} to {span[-1]}" if span else "trailing average"
        return {"label": label, "claim": f"{site}@{period}:baseline:{m}"}
    return None


def _show(value, fmt: str) -> str:
    if fmt == "pct1":
        return f"{value * 100:.1f}%"
    return f"{value:,.0f}" if fmt == "int" else f"{value:,.1f}"


def _recovered(item: dict, rule: dict, facts: dict, fmt: str = "num1") -> tuple[bool, str]:
    """Has the metric returned toward its pre-problem reference? Returns (recovered, why)."""
    typ, ref = rule["type"], item.get("reference")
    if typ == "target" or ref is None:
        return True, "rule no longer fires"
    if typ == "new_top_item":
        k = int(rule.get("top_k", 1))
        top = [i["key"] for i in facts["breakdowns"].get(rule["breakdown"], {}).get("items", [])[:k]]
        return (ref not in top), (f"'{ref}' is still a top item" if ref in top else f"'{ref}' left the top")
    cur = facts["metrics"].get(rule["metric"], {}).get("value")
    if cur is None:
        return False, "no current value to confirm recovery"
    if typ == "trend":
        tol = float(rule.get("min_total", 0)) / 2
        ok = cur >= ref - tol if rule["direction"] == "down" else cur <= ref + tol
        src = (item.get("reference_source") or {}).get("label", "before the problem")
        return ok, f"now {_show(cur, fmt)} vs {_show(ref, fmt)} ({src})"
    thr = float(rule["threshold"])
    if typ == "delta":
        tol = abs(thr) / 2
        ok = cur >= ref - tol if thr < 0 else cur <= ref + tol
    else:  # zscore
        rel = float(rule.get("min_change_rel", 0.1))   # back inside the band that counts as normal
        change = (cur - ref) / abs(ref) if ref else 0.0
        ok = change < rel if thr >= 0 else change > -rel
    src = (item.get("reference_source") or {}).get("label", "before the problem")
    return ok, f"now {_show(cur, fmt)} vs {_show(ref, fmt)} ({src})"


def update_investigations(store: AccountStore, site: str, period: str,
                          signals: list[dict], spec: dict, facts: dict) -> list[dict]:
    data = read_json(store.investigations_file, {"next_id": 1, "items": []})
    resolve_after = int(spec.get("investigations", {}).get("resolve_after_clean_periods", 2))
    firing = {f"{site}:{s['rule']}": s for s in signals if s["investigate"]}
    touched: list[dict] = []

    for item in data["items"]:
        if item["site"] != site or item.get("last_evaluated", "") >= period:
            continue
        sig = firing.pop(item["key"], None)
        item["last_evaluated"] = period
        if sig:
            if item["status"] == "resolved":
                item["history"].append({"period": period, "change": "reopened"})
            item["status"] = "open"
            item["clean_periods"] = 0
            item["last_seen"] = period
            item["observations"].append({"period": period, "signal_id": sig["id"],
                                         "title": sig["title"], "evidence": sig["evidence"]})
            item["questions"] = list(sig["questions"])       # latest wording, no per-period duplicates
            item["persisting"] = False
            touched.append(item)
        elif item["status"] in ("open", "watching"):
            rule = spec.get("signals", {}).get(item["rule"], {"type": "target"})
            fmt = spec["metrics"].get(rule.get("metric"), {}).get("format", "num1")
            ok, why = _recovered(item, rule, facts, fmt)
            item["recovery_check"] = {"period": period, "recovered": ok, "detail": why}
            if not ok:
                if not item.get("persisting"):
                    item["history"].append({"period": period, "change": "persisting", "detail": why})
                item["persisting"] = True
                item["status"] = "open"
                item["clean_periods"] = 0
                touched.append(item)
                continue
            item["persisting"] = False
            item["clean_periods"] = item.get("clean_periods", 0) + 1
            new_status = "resolved" if item["clean_periods"] >= resolve_after else "watching"
            if new_status != item["status"]:
                item["history"].append({"period": period, "change": new_status})
                item["status"] = new_status
            touched.append(item)

    for key, sig in firing.items():
        if any(i["key"] == key and i.get("last_evaluated", "") >= period for i in data["items"]):
            continue
        item = {
            "id": f"INV-{data['next_id']:04d}",
            "key": key,
            "site": site,
            "rule": sig["rule"],
            "title": sig["title"],
            "severity": sig["severity"],
            "status": "open",
            "opened": period,
            "last_seen": period,
            "last_evaluated": period,
            "clean_periods": 0,
            "reference": _reference(sig, spec["signals"][sig["rule"]]),
            "reference_source": _reference_source(sig, spec["signals"][sig["rule"]]),
            "persisting": False,
            "observations": [{"period": period, "signal_id": sig["id"], "title": sig["title"],
                              "evidence": sig["evidence"]}],
            "questions": list(sig["questions"]),
            "notes": [],                       # CSM / Claude notes: {"ts", "author", "text"}
            "history": [{"period": period, "change": "opened"}],
            "created": now_iso(),
        }
        data["next_id"] += 1
        data["items"].append(item)
        touched.append(item)

    write_json(store.investigations_file, data)
    return touched


def add_note(store: AccountStore, inv_id: str, text: str, author: str = "csm") -> dict:
    data = read_json(store.investigations_file, {"next_id": 1, "items": []})
    for item in data["items"]:
        if item["id"] == inv_id:
            item["notes"].append({"ts": now_iso(), "author": author, "text": text})
            write_json(store.investigations_file, data)
            store.log_event("investigation_note", id=inv_id, author=author)
            return item
    raise KeyError(f"No investigation {inv_id}")


def site_items(store: AccountStore, site: str, statuses=("open", "watching")) -> list[dict]:
    data = read_json(store.investigations_file, {"items": []})
    return [i for i in data["items"] if i["site"] == site and i["status"] in statuses]
