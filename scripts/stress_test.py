"""Messy-data stress test.

Takes one clean period of demo data, applies one realistic export problem at a
time, runs the full pipeline plus gate 1, and compares the result with the
clean answer. Each scenario is designed so the *correct* result is known.

Outcomes
  handled    ran, and the numbers match the clean answer (or the documented expectation)
  rejected   refused with a clear error that names the problem (safe, but needs a human)
  flagged    ran, numbers differ, but gate 1 raised a warning or hard failure about it
  SILENT     ran, numbers are wrong, and nothing said so  <- the dangerous one
  crash      unhandled exception

    python scripts/stress_test.py [--markdown docs/stress-test-results.md]

Exits 1 if any scenario is SILENT or crashes, so CI fails on the dangerous outcomes.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import random
import shutil
import tempfile
import traceback
from pathlib import Path

from openpyxl import Workbook

from aie.ingest import IngestError
from aie.pipeline import run
from aie.store import AccountStore
from aie_integrity.context import Account
from aie_integrity.facts_check import check_facts

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "src" / "aie" / "packs" / "ops" / "pack.yaml"
SITE, PREV, CUR = "site-02", "2026-08", "2026-09"
CHECK = ["efficiency", "paid_hours", "earned_hours", "downtime_hours", "active_headcount"]


# ---- csv helpers -------------------------------------------------------------
def read(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    return rows[0], rows[1:]


def write(path: Path, header: list[str], rows: list[list], prefix: str = "", bom: bool = False) -> None:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows([header, *rows])
    path.write_text(("﻿" if bom else "") + prefix + buf.getvalue(), encoding="utf-8")


def mutate(name: str):
    def deco(fn):
        SCENARIOS.append((name, fn.__doc__.strip(), fn))
        return fn
    return deco


SCENARIOS: list = []
rng = random.Random(11)


@mutate("utf8_bom")
def _bom(d: Path):
    """Excel 'CSV UTF-8' export adds a byte-order mark to labor.csv."""
    h, r = read(d / "labor.csv")
    write(d / "labor.csv", h, r, bom=True)


@mutate("header_variants")
def _headers(d: Path):
    """Headers come out as 'Employee ID', 'Paid Hours', 'Earned Hours '."""
    h, r = read(d / "labor.csv")
    write(d / "labor.csv", ["Date", "Employee ID", "Department", "Paid Hours", "Earned Hours "], r)


@mutate("title_rows")
def _title(d: Path):
    """Report export puts two title lines above the header row."""
    h, r = read(d / "labor.csv")
    write(d / "labor.csv", h, r, prefix="Labor Detail Report\nRun date: 10/01/2026\n")


@mutate("extra_and_reordered_columns")
def _cols(d: Path):
    """Columns reordered and two extra columns added (shift, supervisor)."""
    h, r = read(d / "labor.csv")
    order = [4, 3, 2, 1, 0]
    write(d / "labor.csv", ["shift"] + [h[i] for i in order] + ["supervisor"],
          [["A"] + [x[i] for i in order] + ["S1"] for x in r])


@mutate("padded_numbers")
def _pad(d: Path):
    """Numbers padded with spaces: ' 8.25 '."""
    h, r = read(d / "labor.csv")
    write(d / "labor.csv", h, [[a, b, c, f" {p} ", f" {e} "] for a, b, c, p, e in r])


@mutate("us_dates")
def _us(d: Path):
    """Dates exported as MM/DD/YYYY instead of YYYY-MM-DD."""
    h, r = read(d / "labor.csv")
    write(d / "labor.csv", h, [[f"{x[0][5:7]}/{x[0][8:10]}/{x[0][:4]}", *x[1:]] for x in r])


@mutate("totals_row")
def _tot(d: Path):
    """A grand-total row at the bottom of labor.csv."""
    h, r = read(d / "labor.csv")
    tp = sum(float(x[3]) for x in r)
    te = sum(float(x[4]) for x in r)
    write(d / "labor.csv", h, [*r, ["TOTAL", "", "", f"{tp:.2f}", f"{te:.2f}"]])


@mutate("trailing_blank_rows")
def _blank(d: Path):
    """Trailing empty rows and empty trailing columns (',,,,')."""
    h, r = read(d / "labor.csv")
    write(d / "labor.csv", h, [*r, ["", "", "", "", ""], ["", "", "", "", ""]])


@mutate("duplicate_rows")
def _dup(d: Path):
    """An overlapping re-export duplicates 40 labor rows exactly."""
    h, r = read(d / "labor.csv")
    write(d / "labor.csv", h, r + rng.sample(r, 40))


@mutate("id_case_mismatch")
def _idcase(d: Path):
    """Labor file has lowercase employee IDs ('b1005'); roster has 'B1005'."""
    h, r = read(d / "labor.csv")
    write(d / "labor.csv", h, [[a, b.lower(), c, p, e] for a, b, c, p, e in r])


@mutate("reason_variants")
def _reasons(d: Path):
    """Same downtime reason typed three ways: 'Conveyor Jam', 'conveyor-jam', 'CONVEYOR JAM '."""
    h, r = read(d / "downtime.csv")
    variants = ["Conveyor Jam", "conveyor-jam", "CONVEYOR JAM "]
    out = [[a, b, (variants[i % 3] if c == "conveyor jam" else c), m] for i, (a, b, c, m) in enumerate(r)]
    write(d / "downtime.csv", h, out)


@mutate("reversal_pairs")
def _rev(d: Path):
    """Payroll corrections: 12 entries posted and then reversed with negative hours."""
    h, r = read(d / "labor.csv")
    extra = []
    for x in rng.sample(r, 12):
        extra += [[x[0], x[1], x[2], "8.00", "7.00"], [x[0], x[1], x[2], "-8.00", "-7.00"]]
    write(d / "labor.csv", h, r + extra)


@mutate("late_prior_month_rows")
def _late(d: Path):
    """15 rows dated in the prior month show up in this month's export."""
    h, r = read(d / "labor.csv")
    late = [["2026-08-28", *x[1:]] for x in rng.sample(r, 15)]
    write(d / "labor.csv", h, r + late)


@mutate("blank_department")
def _blankdept(d: Path):
    """Department left blank on 20 labor rows."""
    h, r = read(d / "labor.csv")
    idx = set(rng.sample(range(len(r)), 20))
    write(d / "labor.csv", h, [[a, b, ("" if i in idx else c), p, e] for i, (a, b, c, p, e) in enumerate(r)])


@mutate("missing_downtime_file")
def _nodt(d: Path):
    """No downtime export this month."""
    (d / "downtime.csv").unlink()


@mutate("rehire_duplicate_id")
def _rehire(d: Path):
    """Roster lists a rehired employee twice (inactive old record, active new one)."""
    h, r = read(d / "employees.csv")
    first = r[0]
    write(d / "employees.csv", h, [[first[0], first[1], first[2], "inactive"], *r])


@mutate("xlsx_real_dates")
def _xlsx(d: Path):
    """Labor delivered as .xlsx with real Excel date cells and numeric cells."""
    from datetime import date
    h, r = read(d / "labor.csv")
    wb = Workbook()
    ws = wb.active
    ws.append(h)
    for a, b, c, p, e in r:
        ws.append([date.fromisoformat(a), b, c, float(p), float(e)])
    wb.save(d / "labor.xlsx")
    (d / "labor.csv").unlink()


@mutate("source_summary_labels")
def _ss(d: Path):
    """Source system labels metrics 'Efficiency', 'Paid Hours' instead of snake_case."""
    h, r = read(d / "source_summary.csv")
    write(d / "source_summary.csv", h, [[m.replace("_", " ").title(), v] for m, v in r])


@mutate("repeated_header_rows")
def _rephdr(d: Path):
    """Paged report repeats the header row every 200 lines."""
    h, r = read(d / "labor.csv")
    out = []
    for i, x in enumerate(r):
        if i and i % 200 == 0:
            out.append(list(h))
        out.append(x)
    write(d / "labor.csv", h, out)


@mutate("thousands_separators")
def _thou(d: Path):
    """Source-system totals exported with thousands separators: "6,089.43"."""
    h, r = read(d / "source_summary.csv")
    write(d / "source_summary.csv", h, [[m, f"{float(v):,.4f}" if float(v) > 999 else v] for m, v in r])


@mutate("semicolon_delimited")
def _semi(d: Path):
    """European-locale export uses ';' as the delimiter."""
    h, r = read(d / "labor.csv")
    (d / "labor.csv").write_text("\n".join(";".join(x) for x in [h, *r]) + "\n", encoding="utf-8")


@mutate("data_on_second_sheet")
def _sheet2(d: Path):
    """Labor .xlsx has a 'Summary' sheet first and the data on sheet 2."""
    h, r = read(d / "labor.csv")
    wb = Workbook()
    wb.active.title = "Summary"
    wb.active.append(["Labor report", "September"])
    ws = wb.create_sheet("Detail")
    ws.append(h)
    for a, b, c, p, e in r:
        ws.append([a, b, c, float(p), float(e)])
    wb.save(d / "labor.xlsx")
    (d / "labor.csv").unlink()


@mutate("mixed_date_formats")
def _mixdates(d: Path):
    """Half the rows use YYYY-MM-DD and half use MM/DD/YYYY."""
    h, r = read(d / "labor.csv")
    write(d / "labor.csv", h, [[(f"{x[0][5:7]}/{x[0][8:10]}/{x[0][:4]}" if i % 2 else x[0]), *x[1:]]
                               for i, x in enumerate(r)])


# ---- runner -----------------------------------------------------------------
def build(base: Path, data: Path, sep_dir: Path) -> tuple[AccountStore, dict | None, str]:
    store = AccountStore(base / "acct")
    store.init("Stress", SPEC)
    run(store, SITE, PREV, data / SITE / PREV)
    try:
        run(store, SITE, CUR, sep_dir)
    except IngestError as e:
        return store, None, f"IngestError: {str(e).splitlines()[0]}"[:160]
    return store, store.load_facts(SITE, CUR), ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--markdown", type=Path)
    args = ap.parse_args()

    spec = importlib.util.spec_from_file_location("gen", ROOT / "examples" / "generate_demo_data.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    tmp = Path(tempfile.mkdtemp())
    data = tmp / "data"
    gen.generate(data)

    _, truth, _ = build(tmp / "clean", data, data / SITE / CUR)
    tv = {k: truth["metrics"][k]["value"] for k in CHECK}

    results = []
    for name, desc, fn in SCENARIOS:
        work = tmp / name
        sep = work / "in"
        shutil.copytree(data / SITE / CUR, sep)
        fn(sep)
        try:
            store, facts, err = build(work, data, sep)
        except Exception as e:  # noqa: BLE001
            results.append((name, desc, "crash", "", f"{type(e).__name__}: {e}"[:160]))
            traceback.print_exc()
            continue
        if facts is None:
            results.append((name, desc, "rejected", "", err))
            continue
        v = check_facts(Account(store.root), SITE, CUR)
        gate = f"{v['status']} ({v['summary']['hard_fail']}F/{v['summary']['warning']}W)"
        diffs = []
        for k in CHECK:
            got = facts["metrics"][k]["value"]
            exp = tv[k]
            if name == "missing_downtime_file" and k == "downtime_hours":
                exp = None
            if (got is None) != (exp is None) or (got is not None and abs(got - exp) > 1e-6):
                diffs.append(f"{k} {exp if exp is None else round(exp, 4)} -> {got if got is None else round(got, 4)}")
        if name == "reason_variants":
            got = [(i["key"], round(i["value"], 6)) for i in facts["breakdowns"]["downtime_by_reason"]["items"]]
            exp = [(i["key"], round(i["value"], 6)) for i in truth["breakdowns"]["downtime_by_reason"]["items"]]
            if got != exp:
                diffs.append(f"downtime by reason {exp[:2]} -> {got[:2]}")
        unchecked = [f["check"] for f in v["findings"] if f["check"].endswith(".unknown")]
        if unchecked:
            diffs.append(f"source-system cross-check skipped for {unchecked}")
        if not diffs:
            outcome = "handled"
        elif v["summary"]["hard_fail"] or v["summary"]["warning"]:
            outcome = "flagged"
        else:
            outcome = "SILENT"
        flagged = "; ".join(f"{f['level']}: {f['check']}" for f in v["findings"]
                            if f["level"] in ("hard_fail", "warning"))[:160]
        results.append((name, desc, outcome, gate, "; ".join(diffs)[:200] + (f" | {flagged}" if flagged else "")))

    order = {"SILENT": 0, "crash": 1, "flagged": 2, "rejected": 3, "handled": 4}
    lines = ["| Scenario | What the export did | Outcome | Gate 1 | Detail |", "|---|---|---|---|---|"]
    for r in sorted(results, key=lambda r: order[r[2]]):
        lines.append(f"| `{r[0]}` | {r[1]} | **{r[2]}** | {r[3]} | {r[4].replace('|', '/')} |")
    summary = {k: sum(1 for r in results if r[2] == k) for k in order}
    text = (f"{len(results)} scenarios: " + ", ".join(f"{v} {k}" for k, v in summary.items() if v)
            + "\n\n" + "\n".join(lines) + "\n")
    print(text)
    if args.markdown:
        args.markdown.write_text(text, encoding="utf-8")
    if summary["SILENT"] or summary["crash"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
