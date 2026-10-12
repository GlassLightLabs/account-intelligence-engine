"""Step 1 and the front half of step 2: take raw files in, keep an immutable
copy, then load, validate, and normalize them against the pack spec."""

from __future__ import annotations

import re
import shutil
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from .store import AccountStore, sha256_file

SUPPORTED = (".csv", ".xlsx")


class IngestError(Exception):
    pass


def _find(src_dir: Path, stem: str) -> Path | None:
    hits = [src_dir / f"{stem}{ext}" for ext in SUPPORTED if (src_dir / f"{stem}{ext}").exists()]
    if len(hits) > 1:
        raise IngestError(f"Both .csv and .xlsx found for '{stem}' in {src_dir}; keep one.")
    return hits[0] if hits else None


def stage_inputs(store: AccountStore, site: str, period: str, src_dir: Path,
                 force: bool = False) -> dict[str, Path]:
    """Copy raw files into the account. Existing inputs are immutable unless --force."""
    spec = store.spec()
    dest = store.inputs_dir(site, period)
    staged: dict[str, Path] = {}
    for key, fspec in spec["files"].items():
        src = _find(src_dir, fspec["filename"])
        if src is None:
            if fspec.get("required"):
                raise IngestError(f"Required file '{fspec['filename']}' (.csv or .xlsx) not found in {src_dir}")
            continue
        target = dest / src.name
        if target.exists() and src.resolve() != target.resolve():
            if sha256_file(target) != sha256_file(src) and not force:
                raise IngestError(
                    f"{target} already exists with different content. Inputs are immutable; "
                    "pass --force to replace them (the change is logged).")
        if src.resolve() != target.resolve():
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
        staged[key] = target
    store.log_event("inputs_staged", site=site, period=period,
                    files={k: {"name": p.name, "sha256": sha256_file(p)} for k, p in staged.items()})
    return staged


HEADER_SCAN_ROWS = 20
DEFAULT_TOTAL_PATTERN = r"^\s*(grand\s+)?(sub)?totals?\b"
DEFAULT_DATE_FORMATS = ["%Y-%m-%d"]


def _norm_header(name) -> str:
    return re.sub(r"[\s\-]+", "_", str(name).strip().lower())


def _blank(v) -> bool:
    return v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == ""


def _read_raw(path: Path, required: list[str]) -> tuple[pd.DataFrame, int]:
    """Read a file, find the header row, return (data with normalized headers, header line no)."""
    if path.suffix == ".csv":
        for sep in (",", ";", "\t"):
            header_at = None
            for i in range(HEADER_SCAN_ROWS):
                try:
                    row = pd.read_csv(path, header=None, skiprows=i, nrows=1, dtype=str, sep=sep,
                                      keep_default_na=False, encoding="utf-8-sig")
                except (pd.errors.EmptyDataError, pd.errors.ParserError):
                    continue
                if row.empty:
                    break
                names = {_norm_header(v) for v in row.iloc[0].tolist()}
                if all(c in names for c in required):
                    header_at = i
                    break
            if header_at is not None:
                break
        if header_at is None:
            raise IngestError(f"{path.name}: no header row with all required columns {required} "
                              f"in the first {HEADER_SCAN_ROWS} lines (tried ',', ';' and tab delimiters)")
        try:
            df = pd.read_csv(path, skiprows=header_at, dtype=str, keep_default_na=False,
                             encoding="utf-8-sig", sep=sep)
        except pd.errors.ParserError as e:
            raise IngestError(f"{path.name}: could not parse the file ({e})") from e
    else:
        sheets = pd.read_excel(path, header=None, dtype=object, sheet_name=None)
        header_at, raw = None, None
        for _name, sheet in sheets.items():
            for i in range(min(HEADER_SCAN_ROWS, len(sheet))):
                names = {_norm_header(v) for v in sheet.iloc[i].tolist() if not _blank(v)}
                if all(c in names for c in required):
                    header_at, raw = i, sheet
                    break
            if raw is not None:
                break
        if raw is None:
            raise IngestError(f"{path.name}: no sheet has a header row with all required columns {required} "
                              f"in its first {HEADER_SCAN_ROWS} rows")
        df = raw.iloc[header_at + 1:].copy()
        df.columns = raw.iloc[header_at].tolist()
    df.columns = [_norm_header(c) for c in df.columns]
    repeats = df.apply(lambda r: all(_norm_header(r[c]) == c for c in required), axis=1)
    return df[~repeats].reset_index(drop=True), header_at + 1


THOUSANDS = re.compile(r"^[+-]?\d{1,3}(,\d{3})+(\.\d+)?$")


def _number_text(v):
    if not isinstance(v, str):
        return v
    v = v.strip()
    return v.replace(",", "") if THOUSANDS.match(v) else v


def _parse_dates(raw: pd.Series, formats: list[str]) -> pd.Series:
    if all(isinstance(v, (datetime, date)) for v in raw):
        return pd.to_datetime(pd.Series([pd.Timestamp(v) for v in raw], index=raw.index))
    text = raw.astype("string").str.strip()
    best = None
    for fmt in formats:
        parsed = pd.to_datetime(text, format=fmt, errors="coerce")
        if not parsed.isna().any():
            return parsed
        if best is None or parsed.notna().sum() > best.notna().sum():
            best = parsed
    return best


def _coerce(df: pd.DataFrame, columns: dict[str, str], fname: str, date_formats: list[str],
            first_line: int) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    problems: list[str] = []
    for col, typ in columns.items():
        raw = df[col]
        if typ in ("str", "id", "cat", "cat?", "key"):
            s = raw.map(lambda v: "" if _blank(v) else str(v)).astype("string").str.strip()
            if typ == "key":
                s = s.map(lambda v: _norm_header(v) if isinstance(v, str) else v).astype("string")
            if typ == "id":
                s = s.str.upper()
            if typ in ("cat", "cat?"):
                s = s.str.lower().str.replace(r"[\s_\-]+", " ", regex=True).str.strip()
            if typ == "cat?":
                s = s.mask(s == "", "(blank)")
            bad = s.isna() | (s == "")
            out[col] = s.astype(object)
        elif typ == "float":
            s = pd.to_numeric(raw.map(_number_text), errors="coerce")
            bad = s.isna()
            out[col] = s.astype(float)
        elif typ == "date":
            s = _parse_dates(raw, date_formats)
            bad = s.isna()
            out[col] = s.dt.strftime("%Y-%m-%d").astype(object)
        else:
            raise IngestError(f"Unknown column type {typ!r} for {fname}.{col}")
        if bad.any():
            lines = (df.index[bad][:5] + first_line + 1).tolist()
            hint = f" Expected one of the date formats {date_formats}." if typ == "date" else ""
            problems.append(f"{fname}.{col}: {int(bad.sum())} empty or unparseable values "
                            f"(first lines: {lines}).{hint}")
    if problems:
        raise IngestError("Source data failed type checks:\n  " + "\n  ".join(problems))
    return out


def load_frames(store: AccountStore, staged: dict[str, Path]) -> tuple[dict[str, pd.DataFrame], dict]:
    """Load staged files into normalized DataFrames plus input metadata for provenance."""
    spec = store.spec()
    total_re = re.compile(spec.get("total_row_pattern", DEFAULT_TOTAL_PATTERN), re.I)
    date_formats = spec.get("date_formats", DEFAULT_DATE_FORMATS)
    frames: dict[str, pd.DataFrame] = {}
    meta: dict[str, dict] = {}
    for key, path in staged.items():
        fspec = spec["files"][key]
        required = list(fspec["columns"])
        df, header_line = _read_raw(path, required)
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise IngestError(f"{path.name} is missing required columns: {missing}")
        blank_rows = df.apply(lambda r: all(_blank(v) for v in r), axis=1)
        df = df[~blank_rows]
        first = df.iloc[:, 0].map(lambda v: "" if _blank(v) else str(v))
        total_rows = first.str.match(total_re)
        df = df[~total_rows]
        clean = _coerce(df, fspec["columns"], path.name, date_formats, header_line).reset_index(drop=True)
        if fspec.get("key"):
            dups = clean[fspec["key"]][clean[fspec["key"]].duplicated()].unique().tolist()
            if dups:
                raise IngestError(f"{path.name}: duplicate {fspec['key']} values {dups[:5]}. "
                                  "Each key must appear once (for a rehire, keep only the current record).")
        frames[key] = clean
        m = {"file": path.name, "sha256": sha256_file(path), "rows": int(len(clean)),
             "total_rows": int(total_rows.sum()), "header_line": header_line,
             "columns": list(fspec["columns"].keys())}
        date_cols = [c for c, t in fspec["columns"].items() if t == "date"]
        if date_cols and len(clean):
            m["date_min"] = str(clean[date_cols[0]].min())
            m["date_max"] = str(clean[date_cols[0]].max())
        meta[key] = m
    return frames, meta


def detect_period(spec: dict, src_dir: Path) -> str:
    """Infer YYYY-MM from the first dated required file. Needs 90% of rows in one month."""
    date_formats = spec.get("date_formats", DEFAULT_DATE_FORMATS)
    for _key, fspec in spec["files"].items():
        date_cols = [c for c, t in fspec["columns"].items() if t == "date"]
        path = _find(src_dir, fspec["filename"])
        if not date_cols or path is None or not fspec.get("required"):
            continue
        df, _ = _read_raw(path, list(fspec["columns"]))
        values = df[date_cols[0]][~df[date_cols[0]].map(_blank)]
        months = _parse_dates(values, date_formats).dt.strftime("%Y-%m").value_counts()
        if months.empty:
            break
        top, share = months.index[0], months.iloc[0] / months.sum()
        if share < 0.9:
            raise IngestError(f"{path.name}: dates span several months {dict(months.head(3))}; pass --period")
        return str(top)
    raise IngestError(f"Could not infer the period from {src_dir}; pass --period YYYY-MM")
