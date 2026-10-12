import csv
import importlib.util
from pathlib import Path

import pytest
from openpyxl import Workbook

from aie.detect import detect
from aie.formatting import fmt_delta, fmt_value
from aie.pipeline import run
from aie.store import AccountStore
from aie_integrity.context import Account
from aie_integrity.docs_check import CLAIM, _displayed
from aie_integrity.facts_check import check_facts
from aie_integrity.readers import parse_cell, parse_date

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "src" / "aie" / "packs" / "ops" / "pack.yaml"


def _csv_to_xlsx(src: Path, dst: Path) -> None:
    wb = Workbook()
    ws = wb.active
    with src.open(newline="") as fh:
        for i, row in enumerate(csv.reader(fh)):
            if i == 0:
                ws.append(row)
                continue
            # store numbers as numbers, like a real Excel export
            ws.append([float(c) if c.replace(".", "", 1).isdigit() else c for c in row])
    wb.save(dst)


def test_xlsx_inputs_work_in_both_engines(tmp_path):
    spec = importlib.util.spec_from_file_location("gen", ROOT / "examples" / "generate_demo_data.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    data = tmp_path / "data"
    gen.generate(data)
    src = data / "site-01" / "2026-07"
    xin = tmp_path / "xlsx"
    xin.mkdir()
    for f in src.glob("*.csv"):
        _csv_to_xlsx(f, xin / f"{f.stem}.xlsx")

    store = AccountStore(tmp_path / "acct")
    store.init("X", SPEC)
    run(store, "site-01", "2026-07", xin)
    v = check_facts(Account(store.root), "site-01", "2026-07")
    assert v["status"] == "VALIDATED", v["findings"]
    assert store.load_facts("site-01", "2026-07")["metrics"]["outlier_rows"]["value"] > 0


@pytest.mark.parametrize("value,fmt,expected", [
    (0.78234, "pct1", "78.2%"),
    (1243.456, "num1", "1,243.5"),
    (38, "int", "38"),
    (None, "pct1", "n/a"),
])
def test_fmt_value(value, fmt, expected):
    assert fmt_value(value, fmt) == expected


def test_fmt_delta_signs():
    assert fmt_delta(-0.0401, "pct1") == "-4.0 pts"
    assert fmt_delta(0.021, "pct1") == "+2.1 pts"
    assert fmt_delta(281.64, "num1") == "+281.6"


def test_displayed_tolerance_matches_rounding():
    val, tol = _displayed("78.2", "%")
    assert val == pytest.approx(0.782)
    assert abs(0.78249 - val) <= tol            # rounds to 78.2%
    assert abs(0.78260 - val) > tol             # would round to 78.3%
    val, tol = _displayed("1,243.5", None)
    assert val == 1243.5 and tol == pytest.approx(0.05, abs=1e-8)


def test_claim_regex_reads_units_and_refs():
    m = CLAIM.search("down -4.0 pts<!--claim:site-02@2026-09:delta:efficiency--> from")
    assert m["val"] == "-4.0" and m["unit"] == " pts" and m["ref"] == "site-02@2026-09:delta:efficiency"


@pytest.mark.parametrize("raw,typ,expected,ok", [
    (" Trainee ", "cat", "trainee", True),
    ("CONVEYOR-JAM ", "cat", "conveyor jam", True),
    ("", "cat?", "(blank)", True),
    (" b1005", "id", "B1005", True),
    ("", "str", None, False),
    ("8.25", "float", 8.25, True),
    ("nan", "float", None, False),
])
def test_integrity_cell_parsing(raw, typ, expected, ok):
    assert parse_cell(raw, typ) == (expected, ok)


@pytest.mark.parametrize("raw,fmt,expected,ok", [
    ("2026-09-03", "%Y-%m-%d", "2026-09-03", True),
    ("09/03/2026", "%Y-%m-%d", None, False),
    ("09/03/2026", "%m/%d/%Y", "2026-09-03", True),
])
def test_integrity_date_parsing(raw, fmt, expected, ok):
    assert parse_date(raw, fmt) == (expected, ok)


def _spec_with(rule: dict) -> dict:
    return {"signals": {"r": rule}, "targets": {"m": 0.85}}


def _comp(**m):
    base = {"current": 0.80, "previous": 0.84, "delta": -0.04, "baseline": 0.84, "stdev": 0.01,
            "zscore": -4.0, "history_count": 3}
    base.update(m)
    return {"previous_period": "2026-08", "baseline_periods": [], "metrics": {"m": base}, "breakdowns": {}}


def test_delta_rule_respects_threshold_direction():
    rule = {"type": "delta", "metric": "m", "threshold": -0.03}
    assert detect("s", "2026-09", {"breakdowns": {}}, _comp(), _spec_with(rule))
    assert not detect("s", "2026-09", {"breakdowns": {}}, _comp(delta=-0.02), _spec_with(rule))


def test_zscore_rule_needs_history_and_min_change():
    rule = {"type": "zscore", "metric": "m", "threshold": 2.0, "min_history": 3, "min_change_rel": 0.25}
    big = _comp(current=1.2, baseline=0.9, zscore=3.0)
    assert detect("s", "2026-09", {"breakdowns": {}}, big, _spec_with(rule))
    small = _comp(current=0.95, baseline=0.9, zscore=3.0)          # z is high but change is only 5.6%
    assert not detect("s", "2026-09", {"breakdowns": {}}, small, _spec_with(rule))
    short = _comp(current=1.2, baseline=0.9, zscore=3.0, history_count=2)
    assert not detect("s", "2026-09", {"breakdowns": {}}, short, _spec_with(rule))


def test_target_rule():
    rule = {"type": "target", "metric": "m", "direction": "below"}
    assert detect("s", "2026-09", {"breakdowns": {}}, _comp(current=0.80), _spec_with(rule))
    assert not detect("s", "2026-09", {"breakdowns": {}}, _comp(current=0.90), _spec_with(rule))


def test_absdelta_and_breakdown_delta_claims(tmp_path):
    spec = importlib.util.spec_from_file_location("gen", ROOT / "examples" / "generate_demo_data.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    gen.generate(tmp_path / "d")
    store = AccountStore(tmp_path / "a")
    store.init("X", SPEC)
    for p in ("2026-08", "2026-09"):
        run(store, "site-02", p, tmp_path / "d" / "site-02" / p)
    from aie_integrity.docs_check import resolve
    acct = Account(store.root)
    d, err = resolve(acct, "delta:efficiency", "site-02", "2026-09")
    ad, _ = resolve(acct, "absdelta:efficiency", "site-02", "2026-09")
    assert err is None and d < 0 and ad == pytest.approx(-d)
    dd, err = resolve(acct, "delta:efficiency_by_department[processing]", "site-02", "2026-09")
    f8, f9 = store.load_facts("site-02", "2026-08"), store.load_facts("site-02", "2026-09")
    p8 = next(i["value"] for i in f8["breakdowns"]["efficiency_by_department"]["items"] if i["key"] == "processing")
    p9 = next(i["value"] for i in f9["breakdowns"]["efficiency_by_department"]["items"] if i["key"] == "processing")
    assert err is None and dd == pytest.approx(p9 - p8)


def test_month_day_dates_are_not_flagged_as_unsupported_numbers():
    from aie_integrity.docs_check import MONTH_DATE
    text = "the week of August 3 and Sep 28, 2026, but not 30 percent"
    left = MONTH_DATE.sub(" ", text)
    assert "3" not in left.replace("30", "") and "30" in left


def test_claims_precheck_catches_a_wrong_number_before_render(tmp_path):
    spec = importlib.util.spec_from_file_location("gen", ROOT / "examples" / "generate_demo_data.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    gen.generate(tmp_path / "d")
    store = AccountStore(tmp_path / "a")
    store.init("X", SPEC)
    for p in ("2026-08", "2026-09"):
        run(store, "site-02", p, tmp_path / "d" / "site-02" / p)
    from aie_integrity.docs_check import check_interpretation
    f = store.interpretation_file("site-02", "2026-09")
    f.write_text("**Fact.** Efficiency was 78.2%<!--claim:efficiency-->, down 4.0 pts<!--claim:absdelta:efficiency-->.")
    assert check_interpretation(Account(store.root), "site-02", "2026-09")["status"] == "VALIDATED"
    f.write_text("**Fact.** Efficiency was 79.2%<!--claim:efficiency--> and 5 people left.")
    bad = check_interpretation(Account(store.root), "site-02", "2026-09")
    assert bad["status"] == "BLOCKED"
    assert any(x["level"] == "warning" and "unsupported" in x["check"] for x in bad["findings"])
