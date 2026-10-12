"""Read-only view of an account folder for the integrity engine.

Knows the folder layout by convention (documented in docs/architecture.md),
not by importing the analysis engine.
"""

from __future__ import annotations

import importlib
import json
import statistics
from pathlib import Path

import yaml

from .readers import file_sha256, locate, read_typed


class Account:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        if not (self.root / "pack.yaml").is_file():
            raise FileNotFoundError(f"No account (pack.yaml) at {self.root}")
        self.spec = yaml.safe_load((self.root / "pack.yaml").read_text(encoding="utf-8"))
        self.meta = yaml.safe_load((self.root / "account.yaml").read_text(encoding="utf-8"))
        self.pack = importlib.import_module(f"aie_integrity.packs.{self.spec['name']}.recompute")
        self._loaded: dict[tuple, dict] = {}
        self._computed: dict[tuple, dict | None] = {}

    # ---- paths --------------------------------------------------------
    def inputs_dir(self, site: str, period: str) -> Path:
        return self.root / "inputs" / site / period

    def facts_path(self, site: str, period: str) -> Path:
        return self.root / "history" / site / f"{period}.facts.json"

    def validation_path(self, site: str, period: str, stage: str, ext: str = "json") -> Path:
        return self.root / "validation" / site / f"{period}.{stage}-check.{ext}"

    def outputs_dir(self, site: str, period: str) -> Path:
        return self.root / "outputs" / site / period

    def load_facts(self, site: str, period: str) -> dict | None:
        p = self.facts_path(site, period)
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None

    # ---- inputs -------------------------------------------------------
    def input_periods(self, site: str) -> list[str]:
        base = self.root / "inputs" / site
        return sorted(p.name for p in base.iterdir() if p.is_dir()) if base.is_dir() else []

    def load(self, site: str, period: str) -> dict:
        key = (site, period)
        if key in self._loaded:
            return self._loaded[key]
        folder = self.inputs_dir(site, period)
        out = {"files": {}, "tables": {}, "cells": 0, "failures": {}}
        for name, fspec in self.spec["files"].items():
            path = locate(folder, fspec["filename"])
            if path is None:
                out["files"][name] = None
                continue
            got = read_typed(path, fspec["columns"],
                             self.spec.get("total_row_pattern", r"^\s*(grand\s+)?(sub)?totals?\b"),
                             self.spec.get("date_formats", ["%Y-%m-%d"]))
            rows, cells, failures = got["rows"], got["cells"], got["failures"]
            out["files"][name] = {"path": path, "file": path.name, "sha256": file_sha256(path),
                                  "header": got["header"], "header_line": got["header_line"],
                                  "total_rows": got["total_rows"], "rows": len(rows)}
            out["tables"][name] = rows
            out["cells"] += cells
            out["failures"][name] = failures
        self._loaded[key] = out
        return out

    def compute(self, site: str, period: str) -> dict | None:
        """Independent recompute. None if inputs are missing or failed to parse."""
        key = (site, period)
        if key not in self._computed:
            data = self.load(site, period)
            required_missing = any(data["files"].get(n) is None
                                   for n, f in self.spec["files"].items() if f.get("required"))
            broken = any(data["failures"].values())
            if required_missing or broken:
                self._computed[key] = None
            else:
                tables = {n: data["tables"].get(n) for n in self.spec["files"]}
                self._computed[key] = self.pack.recompute(tables, self.spec, period)
        return self._computed[key]

    # ---- history ------------------------------------------------------
    def previous_period(self, site: str, period: str) -> str | None:
        prior = [p for p in self.input_periods(site) if p < period]
        return prior[-1] if prior else None

    def baseline_window(self, site: str, period: str) -> list[str]:
        n = int(self.spec["rules"]["baseline_periods"])
        return [p for p in self.input_periods(site) if p < period][-n:]

    def value(self, site: str, period: str, metric: str):
        r = self.compute(site, period)
        return None if r is None else r["values"].get(metric)

    def delta(self, site: str, period: str, metric: str):
        prev = self.previous_period(site, period)
        cur = self.value(site, period, metric)
        if prev is None or cur is None:
            return None
        pv = self.value(site, prev, metric)
        return None if pv is None else cur - pv

    def baseline(self, site: str, period: str, metric: str) -> tuple:
        """(mean, sample stdev, n) over the trailing window."""
        vals = [self.value(site, p, metric) for p in self.baseline_window(site, period)]
        vals = [v for v in vals if v is not None]
        if not vals:
            return None, None, 0
        mean = statistics.fmean(vals)
        sd = statistics.stdev(vals) if len(vals) >= 2 else None
        return mean, sd, len(vals)

    def streak(self, site: str, period: str, metric: str) -> tuple[int, str | None, str | None, float | None]:
        """(count, direction, start period, start value): consecutive same-direction moves ending at period."""
        periods = [p for p in self.input_periods(site) if p <= period]
        vals = [self.value(site, p, metric) for p in periods]
        count, direction, k = 0, None, len(vals) - 1
        while k >= 1:
            a, b = vals[k - 1], vals[k]
            if a is None or b is None or a == b:
                break
            step = "up" if b > a else "down"
            if direction is None:
                direction = step
            elif step != direction:
                break
            count += 1
            k -= 1
        if count == 0:
            return 0, None, None, None
        return count, direction, periods[k], vals[k]

    def breakdown_item(self, site: str, period: str, name: str, key: str):
        r = self.compute(site, period)
        if r is None:
            return None
        for k, v in r["breakdowns"].get(name, []):
            if k == key:
                return v
        return None
