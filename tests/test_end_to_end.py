import ast
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from aie.ingest import IngestError
from aie.pipeline import run
from aie.render import GateError, render_site
from aie.store import AccountStore, read_json
from aie_integrity.context import Account
from aie_integrity.docs_check import check_docs
from aie_integrity.facts_check import check_facts

ROOT = Path(__file__).resolve().parents[1]
PERIODS = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
SITES = ["site-01", "site-02", "site-03"]
SPEC = ROOT / "src" / "aie" / "packs" / "ops" / "pack.yaml"


def _generator():
    spec = importlib.util.spec_from_file_location("gen", ROOT / "examples" / "generate_demo_data.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def demo_data(tmp_path_factory):
    out = tmp_path_factory.mktemp("data")
    _generator().generate(out)
    return out


@pytest.fixture(scope="session")
def built(tmp_path_factory, demo_data):
    """A fully analyzed and gate-1 validated account. Treat as read-only."""
    root = tmp_path_factory.mktemp("acct") / "demo"
    store = AccountStore(root)
    store.init("Demo Co", SPEC)
    for site in SITES:
        for p in PERIODS:
            run(store, site, p, demo_data / site / p)
            check_facts(Account(root), site, p)
    return root


@pytest.fixture
def account(built, tmp_path):
    """A private copy that a test may modify."""
    dst = tmp_path / "acct"
    shutil.copytree(built, dst)
    return dst


def test_gate1_validates_every_period(built):
    for site in SITES:
        for p in PERIODS:
            v = read_json(built / "validation" / site / f"{p}.facts-check.json")
            assert v["status"] == "VALIDATED", (site, p, v["findings"])
            assert v["summary"]["checks"] > 1000


def test_source_system_disagreement_is_a_warning_not_a_failure(built):
    v = read_json(built / "validation" / "site-01" / "2026-07.facts-check.json")
    assert v["status"] == "VALIDATED"
    warns = [f for f in v["findings"] if f["level"] == "warning" and f["category"] == "source_system"]
    assert {w["check"] for w in warns} == {"paid_hours", "earned_hours", "efficiency"}
    assert all("outlier" in w["message"] for w in warns)


def test_source_system_cross_check_runs_every_month(built):
    """Regression: a normalization change once made this check silently skip two metrics."""
    for p in PERIODS:
        v = read_json(built / "validation" / "site-02" / f"{p}.facts-check.json")
        checked = {c["check"] for c in v["checks"] if c["category"] == "source_system"}
        assert {"paid_hours", "earned_hours", "efficiency"} <= checked, p


def test_planted_stories_are_detected(built):
    store = AccountStore(built)
    aug = {s["rule"]: s for s in store.load_facts("site-02", "2026-08")["signals"]}
    assert "efficiency_drop" in aug
    assert aug["new_downtime_driver"]["evidence"]["item"] == "conveyor jam"
    jul = {s["rule"] for s in store.load_facts("site-01", "2026-07")["signals"]}
    assert "data_quality" in jul
    assert store.load_facts("site-01", "2026-07")["metrics"]["outlier_rows"]["value"] > 0
    jun = store.load_facts("site-03", "2026-06")["metrics"]
    assert jun["unmatched_rows"]["value"] == 12
    sep3 = {s["rule"] for s in store.load_facts("site-03", "2026-09")["signals"]}
    assert "below_target" not in sep3


def test_investigation_lifecycle(built):
    items = read_json(built / "state" / "investigations.json")["items"]
    target3 = next(i for i in items if i["key"] == "site-03:below_target")
    assert target3["opened"] == "2026-04"
    assert target3["status"] == "resolved"          # quiet in 07 and 08
    assert [h["change"] for h in target3["history"]] == ["opened", "watching", "resolved"]
    drop2 = next(i for i in items if i["key"] == "site-02:efficiency_drop")
    assert drop2["status"] == "open" and len(drop2["observations"]) == 2


def test_rerun_is_idempotent(account, demo_data):
    store = AccountStore(account)
    before = read_json(store.investigations_file)
    run(store, "site-02", "2026-09", demo_data / "site-02" / "2026-09")
    assert read_json(store.investigations_file) == before
    assert check_facts(Account(account), "site-02", "2026-09")["status"] == "VALIDATED"


def test_render_is_gated(account):
    store = AccountStore(account)
    (account / "validation" / "site-02" / "2026-09.facts-check.json").unlink()
    with pytest.raises(GateError):
        render_site(store, "site-02", "2026-09")


def test_tampered_fact_is_blocked(account):
    store = AccountStore(account)
    path = store.facts_file("site-02", "2026-09")
    facts = json.loads(path.read_text())
    facts["metrics"]["efficiency"]["value"] += 0.01
    path.write_text(json.dumps(facts))
    with pytest.raises(GateError):                    # facts changed after validation
        render_site(store, "site-02", "2026-09")
    v = check_facts(Account(account), "site-02", "2026-09")
    assert v["status"] == "BLOCKED"
    assert any(f["check"] == "efficiency" for f in v["findings"])


def test_tampered_input_breaks_provenance(account):
    labor = account / "inputs" / "site-02" / "2026-09" / "labor.csv"
    labor.write_text(labor.read_text().replace(",8.", ",9.", 1))
    v = check_facts(Account(account), "site-02", "2026-09")
    assert v["status"] == "BLOCKED"
    assert any(f["check"] == "labor.sha256" for f in v["findings"])


def test_documents_pass_then_catch_a_wrong_number(account):
    store = AccountStore(account)
    shutil.copy(ROOT / "examples" / "interpretations" / "site-02_2026-09.md",
                store.interpretation_file("site-02", "2026-09"))
    render_site(store, "site-02", "2026-09")
    ok = check_docs(Account(account), "site-02", "2026-09")
    assert ok["status"] == "VALIDATED", ok["findings"]
    released = account / "outputs" / "site-02" / "2026-09" / "RELEASED"
    assert released.exists()

    doc = account / "outputs" / "site-02" / "2026-09" / "site_overview.md"
    text = doc.read_text()
    doc.write_text(text.replace("78.2%<!--claim:site-02@2026-09:efficiency-->",
                                "81.2%<!--claim:site-02@2026-09:efficiency-->", 1))
    bad = check_docs(Account(account), "site-02", "2026-09")
    assert bad["status"] == "BLOCKED"
    assert not released.exists()


def test_unmarked_number_is_a_warning(account):
    store = AccountStore(account)
    store.interpretation_file("site-02", "2026-09").write_text(
        "**Observation.** About 30 percent of downtime came from one cause.\n")
    render_site(store, "site-02", "2026-09")
    v = check_docs(Account(account), "site-02", "2026-09")
    assert v["status"] == "VALIDATED"
    assert any(f["check"] == "site_overview.unsupported_numbers" and f["level"] == "warning"
               for f in v["findings"])


def test_ingest_rejects_bad_source(tmp_path, demo_data):
    src = tmp_path / "in"
    shutil.copytree(demo_data / "site-01" / "2026-09", src)
    labor = src / "labor.csv"
    lines = labor.read_text().splitlines()
    lines[3] = lines[3].rsplit(",", 1)[0] + ",abc"
    labor.write_text("\n".join(lines) + "\n")
    store = AccountStore(tmp_path / "acct")
    store.init("T", SPEC)
    with pytest.raises(IngestError, match="earned_hours"):
        run(store, "site-01", "2026-09", src)


def test_inputs_are_immutable(account, demo_data):
    store = AccountStore(account)
    with pytest.raises(IngestError, match="immutable"):
        run(store, "site-02", "2026-09", demo_data / "site-02" / "2026-08")


def test_integrity_engine_shares_no_code():
    """The validator must not import the analysis engine or pandas."""
    for py in (ROOT / "src" / "aie_integrity").rglob("*.py"):
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            for n in names:
                root = n.split(".")[0]
                assert root not in ("aie", "pandas", "numpy"), f"{py.name} imports {n}"


def test_skill_examples_are_true_on_the_demo(account):
    """Every claim example in the skills must resolve and match on the demo account.
    (A wrong example once taught a cold-start Claude session to cite the wrong baseline.)"""
    from aie_integrity.docs_check import CLAIM, _displayed, resolve
    acct = Account(account)
    checked = 0
    for skill in (ROOT / "skills").rglob("SKILL.md"):
        for mt in CLAIM.finditer(skill.read_text()):
            ref = mt.group("ref")
            expected, err = resolve(acct, ref, "site-02", "2026-09")
            assert err is None, (skill.parent.name, ref, err)
            val, tol = _displayed(mt.group("val"), mt.group("unit"))
            assert abs(val - expected) <= tol, (skill.parent.name, mt.group(0), expected)
            checked += 1
    assert checked >= 8


def test_driver_analysis_is_validated_and_shows_conveyor_is_not_the_cause(built):
    """The planted decline is site-wide; conveyor jams coincide with it but don't cause it.
    The engine must surface that, and gate 1 must have verified the numbers."""
    f = AccountStore(built).load_facts("site-02", "2026-09")
    items = {i["key"]: i["value"] for i in f["breakdowns"]["downtime_day_efficiency"]["items"]}
    assert abs(items["conveyor jam: event days"] - items["conveyor jam: other days"]) < 0.01
    weeks = [i["key"] for i in f["breakdowns"]["weekly_efficiency"]["items"]]
    assert weeks == sorted(weeks) and all(w[4] == "-" for w in weeks)
    v = read_json(built / "validation" / "site-02" / "2026-09.facts-check.json")
    checked = {c["check"] for c in v["checks"]}
    assert "downtime_day_efficiency[conveyor jam: event days]" in checked
    assert any(c.startswith("weekly_efficiency[") for c in checked)
    brief = (built / "briefings" / "site-02" / "2026-09.briefing.md").read_text()
    assert "Largest week-to-week move: week of 2026-07-27 -> week of 2026-08-03" in brief
