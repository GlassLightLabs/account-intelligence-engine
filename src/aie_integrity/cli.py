"""Command line for the independent integrity engine.

    aie-integrity facts ACCOUNT --site site-01 --period 2026-09   (gate 1)
    aie-integrity claims ACCOUNT --site site-01 --period 2026-09  (pre-check the interpretation file)
    aie-integrity docs  ACCOUNT --site site-01 --period 2026-09   (gate 2)

Exit codes: 0 validated, 1 blocked (hard failures), 2 usage or setup error.
Pass --strict to also block on warnings.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .context import Account
from .docs_check import check_docs, check_interpretation
from .facts_check import check_facts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="aie-integrity", description="Independent validation engine")
    ap.add_argument("stage", choices=["facts", "claims", "docs"],
                    help="facts = gate 1; claims = pre-check the interpretation before render; docs = gate 2")
    ap.add_argument("account", type=Path)
    ap.add_argument("--site", required=True)
    ap.add_argument("--period", required=True)
    ap.add_argument("--strict", action="store_true", help="treat warnings as blocking")
    a = ap.parse_args(argv)
    try:
        acct = Account(a.account)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    data = {"facts": check_facts, "claims": check_interpretation, "docs": check_docs}[a.stage](acct, a.site, a.period)
    s = data["summary"]
    print(f"{data['status']}: {a.site} {a.period} ({a.stage}) | {s['checks']:,} checks, "
          f"{s['passed']:,} passed, {s['hard_fail']} failed, {s['warning']} warnings, {s['info']} info")
    for f in data["findings"]:
        if f["level"] in ("hard_fail", "warning"):
            extra = f" (expected {f['expected']:.6g})" if isinstance(f.get("expected"), float) else ""
            print(f"  {f['level'].upper():9} [{f['category']}] {f['check']}: {f['message']}{extra}")
    print(f"Report: {acct.validation_path(a.site, a.period, a.stage, 'md')}")
    if data["status"] != "VALIDATED" or (a.strict and s["warning"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
