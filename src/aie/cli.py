"""Command line for the analysis engine.

    aie init     ACCOUNT --name "Demo Co" [--pack ops | --pack-spec path/to/pack.yaml]
    aie run      ACCOUNT --site site-01 --period 2026-09 [--input DIR] [--force]
    aie render   ACCOUNT --site site-01 --period 2026-09
    aie export   ACCOUNT --site site-01 --period 2026-09   (after gate 2)
    aie note     ACCOUNT INV-0001 "text" [--author csm]
    aie name     ACCOUNT site-01 "Elk Grove plant"   (display name used in documents)
    aie context  ACCOUNT [--site SITE ...]   (one compact block for a Claude session)
    aie status   ACCOUNT
"""

from __future__ import annotations

import argparse
import json
import sys
from importlib import resources
from pathlib import Path

from .export import export_site
from .formatting import fmt_delta, fmt_value
from .ingest import IngestError, detect_period
from .investigations import add_note, site_items
from .pipeline import run
from .render import GateError, render_site
from .store import AccountStore, read_json


def _bundled_spec(pack: str) -> Path:
    return Path(str(resources.files("aie.packs") / pack / "pack.yaml"))


def status_table(store: AccountStore) -> str:
    """One line per site: latest period, headline metric, change, and what needs attention."""
    spec = store.spec()
    headline = spec.get("report", {}).get("headline_metric", next(iter(spec["metrics"])))
    fmt = spec["metrics"][headline]["format"]
    rows = [("SITE", "PERIOD", spec["metrics"][headline]["label"].upper(), "CHANGE", "GATE 1", "OPEN", "ATTENTION")]
    for site in store.sites():
        period = store.periods(site)[-1]
        f = store.load_facts(site, period)
        c = f["comparison"]["metrics"][headline]
        v = read_json(store.validation_file(site, period, "facts"))
        gate = "not run" if v is None else v["status"]
        n_open = sum(1 for i in site_items(store, site, ("open",)))
        attention = ", ".join(s["rule"] for s in f["signals"] if s["kind"] in ("risk", "anomaly")) or "-"
        rows.append((site, period, fmt_value(c["current"], fmt),
                     fmt_delta(c["delta"], fmt) if c["delta"] is not None else "-", gate, str(n_open), attention))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]) - 1)]
    lines = [f"Account: {store.meta()['name']}", ""]
    for r in rows:
        lines.append("  ".join(cell.ljust(w) for cell, w in zip(r[:-1], widths, strict=True)) + "  " + r[-1])
    return "\n".join(lines)


def context_block(store: AccountStore, sites: list[str] | None = None) -> str:
    """Status, then for each site's latest period: gate results and the full briefing (which already holds
    trends, breakdown history, drivers, signals, investigations with notes, and claim references)."""
    out = [status_table(store), ""]
    for site in sites or store.sites():
        period = store.periods(site)[-1]
        v = read_json(store.validation_file(site, period, "facts"))
        gate = "gate 1 not run" if v is None else (
            f"gate 1 {v['status']}: {v['summary']['checks']:,} checks, {v['summary']['hard_fail']} failed, "
            f"{v['summary']['warning']} warnings")
        out.append(f"=== {site} {period} | {gate} ===")
        if v:
            out += [f"  {f['level'].upper()} [{f['category']}] {f['check']}: {f['message']}"
                    for f in v["findings"] if f["level"] in ("hard_fail", "warning")]
        brief = store.briefing_file(site, period, "md")
        out += [brief.read_text(encoding="utf-8") if brief.exists() else "(no briefing)", ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="aie", description="Account Intelligence Engine")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="create an account folder")
    p.add_argument("account", type=Path)
    p.add_argument("--name", required=True)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--pack", default="ops", help="bundled domain pack name")
    g.add_argument("--pack-spec", type=Path, help="path to a custom pack.yaml")

    for name, help_ in (("run", "ingest, analyze, compare, detect, brief"),
                        ("render", "build customer documents (requires validation)"),
                        ("export", "write clean customer copies (.md, .html) of a RELEASED document")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("account", type=Path)
        p.add_argument("--site", required=True)
        p.add_argument("--period", required=(name != "run"),
                       help="YYYY-MM" + (" (inferred from the input dates if omitted)" if name == "run" else ""))
        if name == "run":
            p.add_argument("--input", type=Path, help="folder with this period's raw files")
            p.add_argument("--force", action="store_true", help="replace existing inputs")

    p = sub.add_parser("context", help="everything a Claude session needs, in one compact block")
    p.add_argument("account", type=Path)
    p.add_argument("--site", action="append", help="limit to these sites (repeatable); default all")

    p = sub.add_parser("note", help="add a note to an investigation")
    p.add_argument("account", type=Path)
    p.add_argument("investigation")
    p.add_argument("text")
    p.add_argument("--author", default="csm")

    p = sub.add_parser("name", help="set a site's customer-facing display name")
    p.add_argument("account", type=Path)
    p.add_argument("site")
    p.add_argument("display_name")

    p = sub.add_parser("status", help="print the current account state")
    p.add_argument("account", type=Path)
    p.add_argument("--json", action="store_true", help="raw state/current.json")

    a = ap.parse_args(argv)
    store = AccountStore(a.account)
    try:
        if a.cmd == "init":
            spec = a.pack_spec or _bundled_spec(a.pack)
            store.init(a.name, spec)
            print(f"Initialized account '{a.name}' at {a.account}")
        elif a.cmd == "run":
            period = a.period
            if period is None:
                if a.input is None:
                    raise ValueError("pass --period, or --input so the period can be inferred")
                period = detect_period(store.spec(), a.input)
                print(f"Inferred period {period} from the input dates", file=sys.stderr)
            res = run(store, a.site, period, a.input, a.force)
            res["period"] = period
            print(json.dumps(res, indent=2))
            if res["stale_later_periods"]:
                print(f"WARNING: later periods {res['stale_later_periods']} were computed before this one. "
                      "Re-run them in order to refresh their comparisons.", file=sys.stderr)
        elif a.cmd == "render":
            print(json.dumps(render_site(store, a.site, a.period), indent=2))
        elif a.cmd == "name":
            store.set_site_name(a.site, a.display_name)
            print(f"{a.site} will appear in documents as: {store.site_name(a.site)}")
        elif a.cmd == "export":
            print(json.dumps(export_site(store, a.site, a.period), indent=2))
        elif a.cmd == "context":
            print(context_block(store, a.site))
        elif a.cmd == "note":
            item = add_note(store, a.investigation, a.text, a.author)
            print(f"Added note to {item['id']}: {item['title']}")
        elif a.cmd == "status":
            if a.json:
                print(json.dumps(read_json(store.current_file, {}), indent=2))
            else:
                print(status_table(store))
    except (IngestError, GateError, FileNotFoundError, FileExistsError, ValueError, KeyError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
