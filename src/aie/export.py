"""Clean customer copies of a RELEASED document.

The rendered `site_overview.md` keeps hidden claim tags so gate 2 can verify
it. Customers should get a copy without them. Export only works when the
document is RELEASED and unchanged since release (matched by SHA-256).
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from .render import GateError
from .store import AccountStore, sha256_file

COMMENT = re.compile(r"<!--.*?-->", re.S)


def _inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<em>\1</em>", text)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", text)


def to_html(md: str, title: str) -> str:
    """Minimal Markdown to HTML for the subset render.py produces."""
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            out.append(f"<h{level}>{_inline(line[level:].strip())}</h{level}>")
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip("|").split("|")]
                if not all(set(c) <= set("-: ") for c in cells):
                    rows.append(cells)
                i += 1
            head, *body = rows
            out.append("<table><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in body)
                       + "</tbody></table>")
            continue
        elif line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(f"<li>{_inline(lines[i][2:])}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif line.strip():
            out.append(f"<p>{_inline(line)}</p>")
        i += 1
    css = ("body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:820px;margin:40px auto;"
           "padding:0 16px;color:#1f2328;line-height:1.5}table{border-collapse:collapse;margin:12px 0}"
           "th,td{border:1px solid #d0d7de;padding:6px 12px;text-align:left}th{background:#f6f8fa}"
           "td:not(:first-child){text-align:right}h1{font-size:1.6em}h2{font-size:1.25em;margin-top:28px}")
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
            f"<style>{css}</style></head><body>{''.join(out)}</body></html>\n")


def export_site(store: AccountStore, site: str, period: str) -> dict:
    out = store.outputs_dir(site, period)
    doc, marker = out / "site_overview.md", out / "RELEASED"
    if not marker.exists():
        raise GateError(f"{site} {period} is not RELEASED. Run `aie-integrity docs` first.")
    stamp = json.loads(marker.read_text(encoding="utf-8"))
    if stamp.get("site_overview_sha256") != sha256_file(doc):
        raise GateError("site_overview.md changed after release. Re-render and re-run `aie-integrity docs`.")
    clean = COMMENT.sub("", doc.read_text(encoding="utf-8")).rstrip() + "\n"
    md_path: Path = out / "site_overview.customer.md"
    html_path: Path = out / "site_overview.customer.html"
    md_path.write_text(clean, encoding="utf-8")
    html_path.write_text(to_html(clean, f"Site overview {site} {period}"), encoding="utf-8")
    store.log_event("exported", site=site, period=period)
    return {"markdown": str(md_path), "html": str(html_path)}
