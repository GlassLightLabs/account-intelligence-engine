"""Runs steps 1 through 5 and the briefing for one site and period."""

from __future__ import annotations

import importlib
from pathlib import Path

from . import __version__
from .brief import build_briefing
from .compare import compare
from .detect import detect
from .ingest import load_frames, stage_inputs
from .investigations import update_investigations
from .store import AccountStore, now_iso, read_json, validate_ids, write_json


def load_analyzer(pack_name: str):
    return importlib.import_module(f"aie.packs.{pack_name}.analyzer")


def run(store: AccountStore, site: str, period: str, input_dir: Path | None = None,
        force: bool = False) -> dict:
    validate_ids(site, period)
    meta = store.meta()
    spec = store.spec()

    # 1. New data in (or reuse inputs already staged for this site/period)
    src = Path(input_dir) if input_dir else store.inputs_dir(site, period)
    if not src.exists():
        raise FileNotFoundError(f"No inputs for {site} {period}: pass --input DIR")
    staged = stage_inputs(store, site, period, src, force=force)

    # 2. Ingest and analyze
    frames, input_meta = load_frames(store, staged)
    body = load_analyzer(spec["name"]).analyze(frames, spec, input_meta, period)
    facts = {
        "schema": 1,
        "account": meta["name"],
        "site": site,
        "period": period,
        "pack": spec["name"],
        "pack_version": spec.get("version"),
        "engine": f"aie {__version__}",
        "generated_at": now_iso(),
        "inputs": input_meta,
        **body,
    }

    # 3/4. Current state vs history
    prior = store.prior_facts(site, period)
    facts["comparison"] = compare(facts, prior, spec)

    # 5a. Detect
    facts["signals"] = detect(site, period, facts, facts["comparison"], spec)
    write_json(store.facts_file(site, period), facts)

    later = [p for p in store.periods(site) if p > period]
    # 5b. Maintain investigations (skipped when back-filling an older period)
    touched = [] if later else update_investigations(store, site, period, facts["signals"], spec, facts)

    # 7. Update account state
    current = read_json(store.current_file, {"account": meta["name"], "sites": {}})
    latest = current["sites"].get(site, {}).get("latest_period", "")
    if period >= latest:
        current["sites"][site] = {
            "latest_period": period,
            "metrics": {k: v["value"] for k, v in facts["metrics"].items()},
            "signals": [s["id"] for s in facts["signals"]],
            "updated": facts["generated_at"],
        }
        current["updated"] = facts["generated_at"]
        write_json(store.current_file, current)

    briefing = build_briefing(store, facts)
    store.log_event("analysis_run", site=site, period=period,
                    signals=[s["id"] for s in facts["signals"]],
                    investigations_touched=[i["id"] for i in touched])
    return {"facts": str(store.facts_file(site, period)),
            "briefing": str(store.briefing_file(site, period, "md")),
            "signals": len(facts["signals"]),
            "attention": briefing["attention"],
            "stale_later_periods": later}
