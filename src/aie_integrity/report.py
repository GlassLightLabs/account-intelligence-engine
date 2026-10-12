"""Validation report: every check is recorded with a level.

  hard_fail  data is wrong or inconsistent. Blocks output.
  warning    unusual or needs review. Output may proceed.
  info       not a problem; recorded for transparency.
  pass       check succeeded.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

LEVELS = ("hard_fail", "warning", "info", "pass")


def _n(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


class Report:
    def __init__(self, stage: str, site: str, period: str):
        self.stage, self.site, self.period = stage, site, period
        self.records: list[dict] = []
        self.bulk_passes: Counter = Counter()      # row-level passes, counted not listed

    def add(self, category: str, level: str, check: str, message: str = "", **detail) -> None:
        assert level in LEVELS
        self.records.append({"category": category, "level": level, "check": check,
                             "message": message, **detail})

    def ok(self, category: str, check: str, **detail) -> None:
        self.add(category, "pass", check, **detail)

    def expect(self, category: str, check: str, cond: bool, message: str, level: str = "hard_fail",
               **detail) -> bool:
        self.add(category, "pass" if cond else level, check, "" if cond else message, **detail)
        return cond

    def count_bulk(self, category: str, n: int) -> None:
        self.bulk_passes[category] += n

    def summary(self) -> dict:
        c = Counter(r["level"] for r in self.records)
        bulk = sum(self.bulk_passes.values())
        return {"checks": len(self.records) + bulk, "passed": c["pass"] + bulk,
                "hard_fail": c["hard_fail"], "warning": c["warning"], "info": c["info"]}

    @property
    def status(self) -> str:
        return "VALIDATED" if self.summary()["hard_fail"] == 0 else "BLOCKED"

    def to_dict(self, **extra) -> dict:
        by_cat: dict[str, Counter] = {}
        for r in self.records:
            by_cat.setdefault(r["category"], Counter())[r["level"]] += 1
        for cat, n in self.bulk_passes.items():
            by_cat.setdefault(cat, Counter())["pass"] += n
        return {
            "stage": self.stage, "site": self.site, "period": self.period,
            "status": self.status,
            "validated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "engine": "aie-integrity",
            "summary": self.summary(),
            "by_category": {k: dict(v) for k, v in sorted(by_cat.items())},
            **extra,
            "findings": [r for r in self.records if r["level"] != "pass"],
            "checks": [r for r in self.records if r["level"] == "pass"],
        }

    def write(self, json_path: Path, md_path: Path, **extra) -> dict:
        data = self.to_dict(**extra)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
        s = data["summary"]
        lines = [f"# Integrity report: {self.site} {self.period} ({self.stage})", "",
                 f"**Result: {data['status']}**. {s['checks']:,} checks, {s['passed']:,} passed, "
                 f"{_n(s['hard_fail'], 'hard failure')}, {_n(s['warning'], 'warning')}, {s['info']} info.", "",
                 "| Category | Pass | Hard fail | Warning | Info |", "|---|---|---|---|---|"]
        for cat, cnt in data["by_category"].items():
            lines.append(f"| {cat} | {cnt.get('pass', 0):,} | {cnt.get('hard_fail', 0)} | "
                         f"{cnt.get('warning', 0)} | {cnt.get('info', 0)} |")
        for level, title in (("hard_fail", "Hard failures"), ("warning", "Warnings"), ("info", "Info")):
            items = [r for r in data["findings"] if r["level"] == level]
            if items:
                lines += ["", f"## {title}", ""]
                for r in items:
                    extra_bits = {k: v for k, v in r.items()
                                  if k not in ("category", "level", "check", "message")}
                    tail = f" `{json.dumps(extra_bits, default=str)}`" if extra_bits else ""
                    lines.append(f"- **[{r['category']}] {r['check']}**: {r['message']}{tail}")
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return data
