"""
data_utils.py — Data cleaning, column auto-detection, and preview logic.

Kept separate from display/dashboard logic so that Part 2 (AI agent) can import
cleaning utilities without pulling in Streamlit.
"""

import csv
import io
import re
from typing import Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Column-name patterns (bilingual — English & Bahasa Melayu)
# ---------------------------------------------------------------------------

# NOTE: each keyword is wrapped in custom boundaries (?<![A-Za-z0-9])...
# (?![A-Za-z0-9]) so that short tokens like "name", "net", "date" or "type"
# only match as whole words. We deliberately avoid \b because it treats the
# underscore as a word character — snake_case columns such as
# "transaction_date", "total_sales" or "product_name" are extremely common in
# POS/DB exports and must keep matching. The custom lookarounds still stop junk
# columns such as "Unnamed: 2" (contains "name") or "Internet" (contains "net")
# from false-positive and stealing an auto-detected mapping.

_DATE_PATTERNS = re.compile(
    r"(?<![A-Za-z0-9])(tarikh|date|tgl|masa|time|transaction\s*date|hari|created|timestamp)(?![A-Za-z0-9])",
    re.IGNORECASE,
)

_AMOUNT_PATTERNS = re.compile(
    r"(?<![A-Za-z0-9])(amount|jumlah|total|sales|harga|price|revenue|nilai|bayaran|jualan|"
    r"gross|net|subtotal|grand\s*total)(?![A-Za-z0-9])",
    re.IGNORECASE,
)

_PRODUCT_PATTERNS = re.compile(
    r"(?<![A-Za-z0-9])(product|item|barang|produk|description|perkhidmatan|nama|name|"
    r"service|menu)(?![A-Za-z0-9])",
    re.IGNORECASE,
)

_CATEGORY_PATTERNS = re.compile(
    r"(?<![A-Za-z0-9])(category|kategori|segment|jenis|type|kumpulan|jenis|group|"
    r"department|section)(?![A-Za-z0-9])",
    re.IGNORECASE,
)

# Common Malaysian date formats (incl. dot-separated variants)
_DATE_FORMATS = [
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d/%m/%y",
    "%d-%m-%y",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%d.%m.%Y",
    "%d.%m.%y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%Y%m%d",
]

# Year-first formats (ISO order). Parsed *before* the dayfirst loose pass so
# dates like "2026.03.05" or "2026/03/09" are never re-interpreted day-first
# (which would silently swap day and month).
_YEAR_FIRST_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _strip_currency(series: pd.Series) -> pd.Series:
    """Remove currency symbols (RM, $, etc.), commas, and whitespace from
    string values, then attempt numeric conversion.

    The minus sign is deliberately preserved so negative amounts (e.g. a
    ``-4.50`` refund) keep their sign instead of being silently flipped to
    positive.  Currency prefixes are matched case-insensitively so
    ``RM4.50``, ``rm2.00`` and ``RM 3.50`` all parse.
    """
    if not pd.api.types.is_numeric_dtype(series):
        cleaned = (
            series.astype(str)
            .str.replace(r"[RM$,€£¥\s()]+", "", regex=True, flags=re.IGNORECASE)
            .str.strip()
        )
        cleaned = pd.to_numeric(cleaned, errors="coerce")
        return cleaned
    return series


def _try_parse_date(series: pd.Series) -> pd.Series:
    """Tolerantly parse a Series as dates, trying common formats.

    Strategy — row-level fallback instead of all-or-nothing:
    1. Integer ``YYYYMMDD`` columns (a real POS export format, e.g.
       ``20260305``) are parsed with an explicit ``%Y%m%d`` format.
    2. Otherwise pandas' fast mixed-format parser is tried (``dayfirst=True``,
       ``errors='coerce'``) — this avoids the slow per-element dateutil
       fallback that plain ``dayfirst`` triggers on mixed formats.
    3. For any rows still unparsed, try each explicit format in
       ``_DATE_FORMATS`` and fill in what parses.
    4. If at least half of the non-empty values parsed, return a datetime
       Series (NaT marks the genuinely unparseable rows). Otherwise return
       the original Series unchanged so the caller can decide.

    This means a column with mixed date formats keeps every row it can
    parse instead of abandoning the whole column.
    """
    # Integer YYYYMMDD dates (e.g. 20260305) are a common POS export format.
    if pd.api.types.is_numeric_dtype(series):
        sample = series.dropna()
        if sample.empty:
            return series
        nums = pd.to_numeric(sample, errors="coerce")
        ints = nums.astype("int64")
        looks_like_yyyymmdd = ((ints >= 19000101) & (ints <= 21001231)).mean() >= 0.8
        if not looks_like_yyyymmdd:
            return series  # ordinary numbers (amounts/quantities) — not dates
        parsed = pd.to_datetime(ints.astype(str), format="%Y%m%d", errors="coerce")
        if parsed.notna().mean() >= 0.5:
            return pd.to_datetime(
                series.astype("Int64").astype(str),
                format="%Y%m%d",
                errors="coerce",
            )
        return series

    if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
        return series

    # Normalise to string; treat empty / whitespace-only cells as missing
    s = series.astype("string").str.strip()
    s = s.mask(s.isna() | (s == ""), None)

    # Result container (object dtype; normalised to datetime64 at the end).
    parsed = pd.Series(pd.NaT, index=s.index)

    # Pass A — cells that clearly start with a 4-digit year are parsed in ISO
    # order first (YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD). Doing this before the
    # dayfirst pass stops "2026.03.05" / "2026/03/09" from being silently
    # re-read as YYYY-DD-MM (day/month swapped).
    year_first = s.str.match(r"^\d{4}[/.-]", na=False)
    if year_first.any():
        still = year_first.copy()
        for fmt in _YEAR_FIRST_FORMATS:
            if not still.any():
                break
            try:
                vals = pd.to_datetime(
                    s.loc[still], format=fmt, errors="coerce"
                )
                parsed.loc[still] = vals.to_numpy()
            except Exception:
                continue
            still = parsed.isna() & year_first

    # Pass B — everything else: fast "mixed" / dayfirst loose parse.
    rest = (~year_first) & s.notna()
    if rest.any():
        try:
            vals = pd.to_datetime(
                s.loc[rest], format="mixed", dayfirst=True, errors="coerce"
            )
        except Exception:
            vals = pd.to_datetime(s.loc[rest], dayfirst=True, errors="coerce")
        parsed.loc[rest] = vals.to_numpy()

    # Pass C — explicit-format fallback for any still-unparsed rows.
    still_missing = np.flatnonzero(parsed.isna().to_numpy())
    for fmt in _DATE_FORMATS:
        if len(still_missing) == 0:
            break
        try:
            fmt_parsed = pd.to_datetime(
                s.iloc[still_missing], format=fmt, errors="coerce"
            )
            parsed.iloc[still_missing] = fmt_parsed.to_numpy()
        except Exception:
            continue
        still_missing = np.flatnonzero(parsed.isna().to_numpy())

    # Normalise back to a proper datetime64 series (was object dtype above).
    parsed = pd.to_datetime(parsed, errors="coerce")

    total = int(s.notna().sum())
    ok = int(parsed.notna().sum())
    if total > 0 and ok / total >= 0.5:
        return parsed
    return series


_JUNK_COLUMN_RE = re.compile(
    r"^(unnamed\s*:?\s*\d*|col\d+|column\d+|nan|none|null|\s*)$",
    re.IGNORECASE,
)


def _score_column_by_name(col: str, pattern: re.Pattern) -> int:
    """Return a match score (0–100) for a column name against a pattern."""
    score = 0
    if pattern.search(col):
        score += 60  # base match
        # Bonus for exact/close matches
        col_lower = col.strip().lower()
        if col_lower in ("tarikh", "date", "amount", "jumlah", "total", "product", "item", "category", "kategori"):
            score += 30
        # Penalty for obvious non-matches mixed in
        if re.search(r"(id\b|_id\b|code\b|kad\b)", col_lower):
            score -= 20
    # Heavily penalise junk/auto-generated headers so they never win a mapping.
    if _JUNK_COLUMN_RE.search(col.strip()):
        score -= 200
    return score


def _score_date_by_values(series: pd.Series) -> float:
    """Try parsing column as dates and return the fraction of successful
    parses (0.0 – 1.0)."""
    if series.dropna().empty:
        return 0.0
    # _try_parse_date already refuses ordinary numbers (epoch timestamps),
    # while still scoring integer YYYYMMDD columns that genuinely are dates.
    parsed = _try_parse_date(series.dropna().head(100))
    if not pd.api.types.is_datetime64_any_dtype(parsed):
        return 0.0
    return parsed.notna().sum() / len(parsed)


def _score_amount_by_values(series: pd.Series) -> float:
    """Return fraction of values that look numeric after stripping currency."""
    sample = series.dropna().head(100)
    if sample.empty:
        return 0.0
    # Date-like columns (e.g. "2026-03-02") can look numeric after stripping
    # dashes — make sure the column doesn't mostly parse as dates instead.
    if pd.api.types.is_object_dtype(sample) or pd.api.types.is_string_dtype(sample):
        as_dates = _try_parse_date(sample)
        if (
            pd.api.types.is_datetime64_any_dtype(as_dates)
            and as_dates.notna().sum() / len(sample) >= 0.5
        ):
            return 0.0
    # _strip_currency already returns a numeric Series with NaN for invalid
    numeric_count = _strip_currency(sample).notna().sum()
    return numeric_count / len(sample)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


# Header-row detection — known column keywords (English + Bahasa Melayu)
# used to locate the real header when a file begins with title/banner rows
# (e.g. a report title printed above the column names, as in
# ``test_messy_4_worst_case.csv``).
_HEADER_KEYWORD_RE = re.compile(
    r"(tarikh|date|tgl|masa|time|transaction\s*date|hari|created|timestamp|"
    r"amount|jumlah|total|sales|harga|price|revenue|nilai|bayaran|jualan|gross|"
    r"net|subtotal|product|item|barang|produk|description|perkhidmatan|nama|name|"
    r"service|menu|category|kategori|segment|jenis|type|kumpulan|group|"
    r"department|section)",
    re.IGNORECASE,
)

_NUMERIC_CELL_RE = re.compile(r"^[-+]?[\d,]+(?:\.\d+)?$")


def _find_header_row(lines: list, max_scan: int = 15) -> int:
    """Locate the index of the real column-header row in a list of CSV lines.

    Each candidate line is scored by the number of non-empty cells plus a
    bonus for cells that look like column labels (match a known header
    keyword), minus a penalty for purely numeric cells (data rows usually
    contain numbers).  Returns 0 (use the first line as header) when no
    better candidate is found — i.e. normal CSVs are unaffected.
    """
    # Guard: if the first line already looks like a plausible header (has at
    # least two non-empty cells), trust it and return 0 immediately.  This
    # guarantees the search can never silently skip real data rows on files
    # whose header just happens to be keyword-poor — the search is only
    # reached for files that start with title/banner rows (one cell, e.g.
    # ``Laporan Jualan Kedai Makan Pak Su,,,,,``).
    first_cells = [c.strip() for c in next(csv.reader([lines[0]]))] if lines else []
    if sum(1 for c in first_cells if c) >= 2:
        return 0

    best_idx = 0
    best_score = -1
    for i, line in enumerate(lines[:max_scan]):
        # Use the csv module so quoted commas (e.g. "Teh O,Ais") don't
        # inflate the cell count of data rows.
        try:
            cells = [c.strip() for c in next(csv.reader([line]))]
        except Exception:
            cells = [c.strip() for c in line.split(",")]
        non_empty = [c for c in cells if c]
        if not non_empty:
            continue
        score = len(non_empty) * 10
        score += sum(15 for c in non_empty if _HEADER_KEYWORD_RE.search(c))
        score -= sum(3 for c in non_empty if _NUMERIC_CELL_RE.match(c))
        if score > best_score:
            best_score = score
            best_idx = i
    return best_idx


def _read_csv_text(text: str) -> Optional[pd.DataFrame]:
    """Parse CSV text, skipping any leading title/banner rows so the real
    header line becomes the column names.

    Blank lines are kept (``skip_blank_lines=False``) so fully-empty rows
    survive into the DataFrame where ``clean_data_with_report`` can count
    them in the data-quality report instead of silently discarding them.
    """
    lines = text.splitlines()
    header_idx = _find_header_row(lines)
    return pd.read_csv(
        io.StringIO(text),
        skiprows=header_idx,
        skip_blank_lines=False,
        on_bad_lines="skip",
    )


def load_file(uploaded_file) -> Optional[pd.DataFrame]:
    """Read a CSV or Excel file into a DataFrame.  Returns None on failure.

    CSV handling:
    - Tries several encodings (UTF-8 first, then common fallbacks).
    - Locates the real header row, so files that start with title/banner
      lines (e.g. ``test_messy_4_worst_case.csv``) still parse correctly.
    """
    try:
        if uploaded_file.name.endswith(".csv"):
            raw = uploaded_file.read()
            if isinstance(raw, str):
                raw = raw.encode("utf-8")
            encodings = ["utf-8", "latin-1", "ISO-8859-1", "cp1252"]
            for enc in encodings:
                try:
                    text = raw.decode(enc)
                except (UnicodeDecodeError, UnicodeError):
                    continue
                df = _read_csv_text(text)
                if df is not None and not df.empty:
                    return df
            # Last resort: replace undecodable bytes
            text = raw.decode("utf-8", errors="replace")
            return _read_csv_text(text)

        if uploaded_file.name.endswith(".xlsx"):
            return pd.read_excel(uploaded_file, engine="openpyxl")

        return None
    except Exception:
        return None


def auto_detect_columns(df: pd.DataFrame) -> dict:
    """Auto-detect the most likely column roles in the DataFrame.

    Returns a dict with keys:
        date_col, amount_col, product_col, category_col
    Each value is either a column name or None.
    """
    result = {"date_col": None, "amount_col": None, "product_col": None, "category_col": None}

    if df.empty:
        return result

    name_scores = {col: _score_column_by_name(col, _DATE_PATTERNS) for col in df.columns}
    value_scores = {
        col: _score_date_by_values(df[col]) * 100 for col in df.columns
    }
    # Combined: give name match a slight edge
    combined_date = {
        col: name_scores[col] * 0.4 + value_scores[col] * 0.6
        for col in df.columns
    }
    best_date = max(combined_date, key=combined_date.get) if combined_date else None
    if best_date and combined_date[best_date] > 20:
        result["date_col"] = best_date

    # --- Amount column ---
    name_scores_amount = {
        col: _score_column_by_name(col, _AMOUNT_PATTERNS) for col in df.columns
    }
    value_scores_amount = {
        col: _score_amount_by_values(df[col]) * 100 for col in df.columns
    }
    combined_amount = {
        col: name_scores_amount[col] * 0.3 + value_scores_amount[col] * 0.7
        for col in df.columns
    }
    # Exclude the date column
    for col in df.columns:
        if col == result["date_col"]:
            combined_amount[col] = 0
    best_amount = max(combined_amount, key=combined_amount.get) if combined_amount else None
    if best_amount and combined_amount[best_amount] > 20:
        result["amount_col"] = best_amount

    # --- Product column ---
    name_scores_product = {
        col: _score_column_by_name(col, _PRODUCT_PATTERNS) for col in df.columns
    }
    best_product = max(name_scores_product, key=name_scores_product.get) if name_scores_product else None
    if best_product and name_scores_product[best_product] > 30:
        result["product_col"] = best_product

    # --- Category column ---
    name_scores_cat = {
        col: _score_column_by_name(col, _CATEGORY_PATTERNS) for col in df.columns
    }
    best_cat = max(name_scores_cat, key=name_scores_cat.get) if name_scores_cat else None
    if best_cat and name_scores_cat[best_cat] > 30:
        result["category_col"] = best_cat

    return result


def clean_data_with_report(
    df: pd.DataFrame,
    date_col: Optional[str] = None,
    amount_col: Optional[str] = None,
    product_col: Optional[str] = None,
    category_col: Optional[str] = None,
) -> tuple[pd.DataFrame, dict]:
    """Return a cleaned copy of the DataFrame plus a data-quality report.

    Steps:
    1. Drop fully empty rows/columns.
    2. Parse the date column (if specified) — rows whose date can't be
       parsed are dropped and counted.
    3. Clean the amount column (if specified) — rows with invalid amounts
       are dropped and counted.
    4. Fill missing product/category with "Unknown" / "Uncategorised" and
       count the defaults.

    The report dict contains:
        rows_source           — rows before any cleaning
        rows_blank_dropped    — fully-empty rows removed
        rows_date_dropped     — rows with unparseable dates removed
        rows_amount_dropped   — rows with invalid/missing amounts removed
        rows_used             — rows that made it into the analysis
        products_defaulted    — product cells filled with "Unknown"
        categories_defaulted  — category cells filled with "Uncategorised"
        date_parse_failed     — True if the whole date column failed to parse
    """
    df = df.copy()

    report = {
        "rows_source": len(df),
        "rows_blank_dropped": 0,
        "rows_date_dropped": 0,
        "rows_amount_dropped": 0,
        "rows_used": 0,
        "products_defaulted": 0,
        "categories_defaulted": 0,
        "date_parse_failed": False,
    }

    # Drop rows / columns that are entirely NaN
    before = len(df)
    df = df.dropna(how="all").dropna(axis=1, how="all")
    report["rows_blank_dropped"] = before - len(df)

    if date_col and date_col in df.columns:
        df[date_col] = _try_parse_date(df[date_col])
        if pd.api.types.is_datetime64_any_dtype(df[date_col]):
            # Drop rows where the date could not be parsed (only if date_col is set)
            report["rows_date_dropped"] = int(df[date_col].isna().sum())
            df = df.dropna(subset=[date_col])
        else:
            # Entire column failed to parse — flag it, keep rows for now
            report["date_parse_failed"] = True

    if amount_col and amount_col in df.columns:
        df[amount_col] = _strip_currency(df[amount_col])
        # Also drop rows where amount is invalid
        report["rows_amount_dropped"] = int(df[amount_col].isna().sum())
        df = df.dropna(subset=[amount_col])

    if product_col and product_col in df.columns:
        report["products_defaulted"] = int(df[product_col].isna().sum())
        df[product_col] = df[product_col].fillna("Unknown").astype(str).str.strip()

    if category_col and category_col in df.columns:
        report["categories_defaulted"] = int(df[category_col].isna().sum())
        df[category_col] = df[category_col].fillna("Uncategorised").astype(str).str.strip()

    # Reset index after dropping rows
    df = df.reset_index(drop=True)
    report["rows_used"] = len(df)

    return df, report


def get_data_preview(
    df: pd.DataFrame,
    date_col: Optional[str] = None,
    amount_col: Optional[str] = None,
) -> dict:
    """Return a dictionary of high-level statistics for the data preview.

    Amount stats are computed defensively: the column is coerced to numeric
    first so a string column can never crash the preview with a
    ``ValueError`` (e.g. when a mis-detected column ends up mapped as the
    amount column).
    """
    preview = {
        "row_count": len(df),
        "columns": list(df.columns),
        "date_col": date_col,
        "amount_col": amount_col,
        "total_sales": None,
        "date_range": None,
        "avg_order_value": None,
    }

    if amount_col and amount_col in df.columns:
        amount_series = pd.to_numeric(df[amount_col], errors="coerce")
        total_sales = amount_series.sum()
        preview["total_sales"] = float(total_sales) if pd.notna(total_sales) else 0.0
        avg = amount_series.mean()
        preview["avg_order_value"] = float(avg) if pd.notna(avg) else 0.0

    if date_col and date_col in df.columns and pd.api.types.is_datetime64_any_dtype(df[date_col]):
        min_date = df[date_col].min()
        max_date = df[date_col].max()
        if pd.notna(min_date) and pd.notna(max_date):
            preview["date_range"] = (min_date, max_date)

    return preview
