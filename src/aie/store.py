"""Persistent account state on disk.

Everything the engine knows about an account lives in one folder:

    <account>/
      account.yaml                 name, pack, created
      pack.yaml                    frozen copy of the domain pack spec
      inputs/<site>/<period>/      immutable copies of the raw files
      history/<site>/<period>.facts.json
      state/current.json           latest snapshot per site
      state/investigations.json    open, watching, and resolved items
      state/events.jsonl           append-only log of everything that happened
      briefings/<site>/<period>.briefing.{md,json}
      briefings/<site>/<period>.interpretation.md   (written by Claude)
      validation/<site>/<period>.{facts,docs}-check.{json,md}
      outputs/<site>/<period>/     customer-ready documents
      outputs/account_summary.md   rolling account view (archived on change)

Plain files on purpose: easy to diff, back up, version with git, and read by
Claude without any special tooling.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
SITE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=False, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def validate_ids(site: str, period: str) -> None:
    if not SITE_RE.match(site):
        raise ValueError(f"Invalid site id {site!r}: use lowercase letters, digits, - or _")
    if not PERIOD_RE.match(period):
        raise ValueError(f"Invalid period {period!r}: use YYYY-MM")


class AccountStore:
    def __init__(self, root: Path | str):
        self.root = Path(root)

    # ---- layout -------------------------------------------------------
    @property
    def account_file(self) -> Path:
        return self.root / "account.yaml"

    @property
    def pack_file(self) -> Path:
        return self.root / "pack.yaml"

    def inputs_dir(self, site: str, period: str) -> Path:
        return self.root / "inputs" / site / period

    def facts_file(self, site: str, period: str) -> Path:
        return self.root / "history" / site / f"{period}.facts.json"

    def briefing_file(self, site: str, period: str, ext: str) -> Path:
        return self.root / "briefings" / site / f"{period}.briefing.{ext}"

    def interpretation_file(self, site: str, period: str) -> Path:
        return self.root / "briefings" / site / f"{period}.interpretation.md"

    def validation_file(self, site: str, period: str, stage: str, ext: str = "json") -> Path:
        return self.root / "validation" / site / f"{period}.{stage}-check.{ext}"

    def outputs_dir(self, site: str, period: str) -> Path:
        return self.root / "outputs" / site / period

    @property
    def current_file(self) -> Path:
        return self.root / "state" / "current.json"

    @property
    def investigations_file(self) -> Path:
        return self.root / "state" / "investigations.json"

    @property
    def events_file(self) -> Path:
        return self.root / "state" / "events.jsonl"

    # ---- account ------------------------------------------------------
    def exists(self) -> bool:
        return self.account_file.exists() and self.pack_file.exists()

    def init(self, name: str, pack_spec_path: Path) -> None:
        if self.exists():
            raise FileExistsError(f"Account already initialized at {self.root}")
        self.root.mkdir(parents=True, exist_ok=True)
        spec = yaml.safe_load(pack_spec_path.read_text(encoding="utf-8"))
        self.pack_file.write_text(pack_spec_path.read_text(encoding="utf-8"), encoding="utf-8")
        meta = {"name": name, "pack": spec["name"], "pack_version": spec.get("version"),
                "created": now_iso()}
        self.account_file.write_text(yaml.safe_dump(meta, sort_keys=False), encoding="utf-8")
        self.log_event("account_initialized", **meta)

    def meta(self) -> dict:
        if not self.exists():
            raise FileNotFoundError(f"No account at {self.root}. Run `aie init` first.")
        return yaml.safe_load(self.account_file.read_text(encoding="utf-8"))

    def site_name(self, site: str) -> str:
        """Customer-facing display name, e.g. 'Elk Grove plant (site-01)'. Falls back to the id."""
        name = (self.meta().get("site_names") or {}).get(site)
        return f"{name} ({site})" if name else site

    def set_site_name(self, site: str, name: str) -> None:
        meta = self.meta()
        meta.setdefault("site_names", {})[site] = name
        self.account_file.write_text(yaml.safe_dump(meta, sort_keys=False), encoding="utf-8")

    def spec(self) -> dict:
        return yaml.safe_load(self.pack_file.read_text(encoding="utf-8"))

    # ---- history ------------------------------------------------------
    def sites(self) -> list[str]:
        base = self.root / "history"
        return sorted(p.name for p in base.iterdir() if p.is_dir()) if base.exists() else []

    def periods(self, site: str) -> list[str]:
        base = self.root / "history" / site
        if not base.exists():
            return []
        return sorted(p.name.split(".")[0] for p in base.glob("*.facts.json"))

    def load_facts(self, site: str, period: str) -> dict | None:
        return read_json(self.facts_file(site, period))

    def prior_facts(self, site: str, period: str, n: int | None = None) -> list[dict]:
        """Facts for periods strictly before `period`, oldest first."""
        prior = [p for p in self.periods(site) if p < period]
        if n is not None:
            prior = prior[-n:]
        return [self.load_facts(site, p) for p in prior]

    # ---- events -------------------------------------------------------
    def log_event(self, event: str, **data: Any) -> None:
        self.events_file.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": now_iso(), "event": event, **data}
        with self.events_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
