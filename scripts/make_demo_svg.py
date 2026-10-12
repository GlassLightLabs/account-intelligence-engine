"""Render a real demo session to docs/images/demo.svg for the README.

Runs actual commands against a fresh demo account and records their output,
so the image never drifts from what the code does. Needs `rich` (dev only).

    pip install rich && python scripts/make_demo_svg.py
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from rich.console import Console
from rich.text import Text

ROOT = Path(__file__).resolve().parents[1]


def sh(cmd: str, cwd: Path) -> str:
    return subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True).stdout.rstrip()


def main() -> None:
    work = Path(tempfile.mkdtemp())
    acct = work / "demo"
    subprocess.run(["bash", "examples/run_demo.sh", str(acct)], cwd=ROOT, check=True, capture_output=True)
    shutil.copytree(ROOT / "examples" / "demo-data", work / "data", dirs_exist_ok=True)

    con = Console(record=True, width=134, force_terminal=True, highlight=False)

    def prompt(cmd: str) -> None:
        con.print(Text.assemble(("$ ", "bold green"), (cmd, "bold")))

    def show(out: str) -> None:
        for line in out.splitlines():
            t = Text(line)
            t.highlight_words(["VALIDATED"], "bold green")
            t.highlight_words(["BLOCKED", "HARD_FAIL"], "bold red")
            t.highlight_words(["WARNING"], "bold yellow")
            con.print(t)
        con.print()

    con.print("[dim]# September data for site-02 arrives. Analyze it, then validate it independently.[/dim]")
    prompt("aie run demo --site site-02 --period 2026-09 --input data/site-02/2026-09")
    res = json.loads(sh("aie run demo --site site-02 --period 2026-09 --input data/site-02/2026-09", work))
    show(f"facts:    {res['facts']}\n"
         f"briefing: {res['briefing']}\n"
         f"signals:  {res['signals']}  attention: {', '.join(a.split(':')[-1] for a in res['attention'])}")
    prompt("aie-integrity facts demo --site site-02 --period 2026-09")
    show(sh("aie-integrity facts demo --site site-02 --period 2026-09 | head -1", work))

    con.print("[dim]# Where does the account stand?[/dim]")
    prompt("aie status demo")
    show(sh("aie status demo", work))

    con.print("[dim]# Claude has written the interpretation. "
              "Render the customer document and check every number in it.[/dim]")
    prompt("aie render demo --site site-02 --period 2026-09")
    r = json.loads(sh("aie render demo --site site-02 --period 2026-09", work))
    show(f"wrote: {r['site_overview']}, {r['workbook']}, {r['account_summary']}")
    prompt("aie-integrity docs demo --site site-02 --period 2026-09")
    show(sh("aie-integrity docs demo --site site-02 --period 2026-09 | head -1", work))

    con.print("[dim]# Someone hand-edits one number in the customer document (29.1 -> 19.1)...[/dim]")
    doc = acct / "outputs/site-02/2026-09/site_overview.md"
    doc.write_text(doc.read_text().replace("29.1<!--claim:", "19.1<!--claim:", 1))
    prompt("aie-integrity docs demo --site site-02 --period 2026-09")
    out = sh("aie-integrity docs demo --site site-02 --period 2026-09", work)
    show("\n".join(line for line in out.splitlines() if not line.startswith("Report:")))

    target = ROOT / "docs" / "images" / "demo.svg"
    target.parent.mkdir(parents=True, exist_ok=True)
    svg = con.export_svg(title="account-intelligence-engine")
    # GitHub renders README images without loading external fonts; use a local monospace stack.
    svg = re.sub(r"@font-face\s*{[^}]*}", "", svg)
    svg = svg.replace('font-family: Fira Code, monospace',
                      'font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace')
    target.write_text(svg, encoding="utf-8")
    print(f"Wrote {target}")


if __name__ == "__main__":
    main()
