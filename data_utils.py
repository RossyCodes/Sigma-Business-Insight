"""
data_utils.py — Data cleaning, column auto-detection, and preview logic.

Kept separate from display/dashboard logic so that Part 2 (AI agent) can import
cleaning utilities without pulling in Streamlit.
"""

import re
from typing import Optional

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

# Common Malaysian date formats
_DATE_FORMATS = [
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d/%m/%y",
    "%d-%m-%y",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%Y%m%d",
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _strip_currency(series: pd.Series) -> pd.Series:
    """Remove currency symbols (RM, $, etc.), commas, and whitespace from
    string values, then attempt numeric conversion."""
    if not pd.api.types.is_numeric_dtype(series):
        cleaned = (
            series.astype(str)
            .str.replace(r"[RM$,€£¥\s()\-\+]+", "", regex=True)
            .str.strip()
        )
        cleaned = pd.to_numeric(cleaned, errors="coerce")
        return cleaned
    return series


def _try_parse_date(series: pd.Series) -> pd.Series:
    """Attempt to parse a Series as dates, trying common formats.

    Returns a datetime Series (with NaT for unparseable values) on success,
    or the original Series unchanged on failure.
    """
    # First attempt: let pandas infer (with dayfirst=True for DD/MM/YYYY)
    try:
        parsed = pd.to_datetime(series, dayfirst=True, errors="coerce")
        if parsed.notna().sum() > len(series) * 0.5:
            return parsed
    except Exception:
        pass

    # Second attempt: try explicit formats
    for fmt in _DATE_FORMATS:
        try:
            parsed = pd.to_datetime(series, format=fmt, errors="coerce")
            if parsed.notna().sum() > len(series) * 0.5:
                return parsed
        except Exception:
            continue

    # Fallback: return original unchanged (parsing failed)
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
    parsed = _try_parse_date(series.dropna().head(100))
    if not pd.api.types.is_datetime64_any_dtype(parsed):
        return 0.0
    return parsed.notna().sum() / len(parsed)


def _score_amount_by_values(series: pd.Series) -> float:
    """Return fraction of values that look numeric after stripping currency."""
    sample = series.dropna().head(100)
    if sample.empty:
        return 0.0
    # _strip_currency already returns a numeric Series with NaN for invalid
    numeric_count = _strip_currency(sample).notna().sum()
    return numeric_count / len(sample)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_file(uploaded_file) -> Optional[pd.DataFrame]:
    """Read a CSV or Excel file into a DataFrame.  Returns None on failure."""
    try:
        if uploaded_file.name.endswith(".csv"):
            # Try UTF-8 first, then common fallbacks
            encodings = ["utf-8", "latin-1", "ISO-8859-1", "cp1252"]
            for enc in encodings:
                try:
                    df = pd.read_csv(
                        uploaded_file,
                        encoding=enc,
                        on_bad_lines="skip",  # Skip rows with too many fields
                    )
                    if not df.empty:
                        return df
                except (UnicodeDecodeError, UnicodeError):
                    uploaded_file.seek(0)
                    continue
            # Last resort
            uploaded_file.seek(0)
            df = pd.read_csv(
                uploaded_file,
                encoding="utf-8",
                errors="replace",
                on_bad_lines="skip",
            )
            return df

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


def clean_data(
    df: pd.DataFrame,
    date_col: Optional[str] = None,
    amount_col: Optional[str] = None,
    product_col: Optional[str] = None,
    category_col: Optional[str] = None,
) -> pd.DataFrame:
    """Return a cleaned copy of the DataFrame.

    Steps:
    1. Drop fully empty rows/columns.
    2. Parse the date column (if specified).
    3. Clean the amount column (if specified).
    4. Forward-fill sparse categories (if useful).
    """
    df = df.copy()

    # Drop rows / columns that are entirely NaN
    df = df.dropna(how="all").dropna(axis=1, how="all")

    if date_col and date_col in df.columns:
        df[date_col] = _try_parse_date(df[date_col])
        # Drop rows where the date could not be parsed (only if date_col is set)
        df = df.dropna(subset=[date_col])

    if amount_col and amount_col in df.columns:
        df[amount_col] = _strip_currency(df[amount_col])
        # Also drop rows where amount is invalid
        df = df.dropna(subset=[amount_col])

    if product_col and product_col in df.columns:
        df[product_col] = df[product_col].fillna("Unknown").astype(str).str.strip()

    if category_col and category_col in df.columns:
        df[category_col] = df[category_col].fillna("Uncategorised").astype(str).str.strip()

    # Reset index after dropping rows
    df = df.reset_index(drop=True)

    return df


def get_data_preview(
    df: pd.DataFrame,
    date_col: Optional[str] = None,
    amount_col: Optional[str] = None,
) -> dict:
    """Return a dictionary of high-level statistics for the data preview."""
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
        preview["total_sales"] = float(df[amount_col].sum())
        preview["avg_order_value"] = float(df[amount_col].mean())

    if date_col and date_col in df.columns and pd.api.types.is_datetime64_any_dtype(df[date_col]):
        min_date = df[date_col].min()
        max_date = df[date_col].max()
        if pd.notna(min_date) and pd.notna(max_date):
            preview["date_range"] = (min_date, max_date)

    return preview
