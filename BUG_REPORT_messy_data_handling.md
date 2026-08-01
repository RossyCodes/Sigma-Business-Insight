# Bug Report: Messy Data Handling — Sigma Business Insight

**Reported by:** Rozana
**Date:** 2026-08-01
**App:** Business Insight Agent (Sigma) — `app.py`, `data_utils.py`
**Test files used:** `test_messy_1_dates_missing.csv` (mixed date formats + missing values + blank row)

---

## Summary

App does not gracefully handle real-world messy sales data. When uploaded with mixed date formats, missing values, and a blank row, the app either **crashes entirely** or **silently drops/mislabels data** without informing the user. For a production tool aimed at SME clients, this is a critical issue — clients could lose trust if their sales numbers appear wrong with no explanation.

---

## Bug 1: App crash on mixed date formats + blank row

**Severity:** High (app unusable, full crash)

**Steps to reproduce:**
1. Upload a CSV with dates in multiple formats (`01/03/2026`, `2026-03-02`, `03-04-2026`, `2026.03.05`, `11-3-26`) and a blank row in the middle of the data
2. Confirm auto-detected column mapping (Date, Amount, Product, Category all correctly identified)
3. Click "Generate Dashboard"

**Expected behavior:**
Dashboard generates, with unparseable rows either cleaned or clearly flagged/excluded.

**Actual behavior:**
App throws:
```
ValueError: could not convert string to float: '01/03/20262026-03-0203-04-20262026.03.0506/03/20267/3/202608-03-20262026/03/0910/03/202611-3-26'
```
Traceback points to `data_utils.py` line 319, inside `get_data_preview()`:
```python
preview["total_sales"] = float(df[amount_col].sum())
```

**Root cause (suspected):**
The `Amount` column values appear to have been concatenated with `Date` column values into one long string before the `.sum()` call — likely caused by the blank row shifting column alignment during parsing, or a merge/concat step that isn't correctly excluding blank rows before this stage.

---

## Bug 2: Date parser fails completely instead of parsing what it can

**Severity:** High (core feature broken — trend chart + best day insight)

**Steps to reproduce:**
1. Upload the same file as Bug 1, but with the blank row removed (isolate the date-format issue only)
2. Generate dashboard

**Actual behavior:**
- Banner shown: `"Date column could not be parsed. Trend chart unavailable."`
- "Best Day" KPI card shows `–` (blank) since it depends on date parsing
- The **entire** date column is abandoned rather than parsing the rows that are in a recognizable format

**Expected behavior:**
Parser should attempt multiple common formats per row (e.g. `pd.to_datetime(df[date_col], errors='coerce', dayfirst=True)` combined with a fallback format-guessing loop) so that valid dates are parsed even if a few rows use inconsistent formats. Only genuinely unparseable individual rows should be excluded — not the whole column.

---

## Bug 3: Silent data loss — no user-facing warning

**Severity:** Medium (data integrity / trust issue)

**Observed behavior:**
- Source file had 12 rows; dashboard shows only 10 transactions used in Total Sales / Avg Order Value
- 2 rows with missing Amount or unparseable data were dropped with **no notification** to the user
- A row with a missing Product name appears in "Top Products" labeled `Unknown`, with no explanation of what that means

**Expected behavior:**
Any time rows are excluded or values are defaulted (e.g. missing product → "Unknown"), show a visible banner, e.g.:
> ⚠️ 2 baris data tidak lengkap telah diabaikan daripada analisis ini.

This keeps the client aware their numbers reflect only valid data — critical for trust when this tool is used with real business data.

---

## Suggested Fixes (priority order)

1. **Date parsing** — replace strict single-format parsing with a tolerant multi-format parser (`errors='coerce'` + fallback format attempts), so partial success is possible instead of all-or-nothing.
2. **Blank row / malformed row handling** — explicitly drop fully-blank rows *before* type conversion steps, and verify column alignment isn't affected by them.
3. **Row-level fallback instead of column-level failure** — if a single row's Amount or Date can't be converted, exclude just that row (with logging), not the entire column/feature.
4. **User-facing data quality banner** — after cleaning, show a summary like "X of Y rows used in this analysis" and list what was excluded and why.

---

## Test file for reproduction

`test_messy_1_dates_missing.csv` — attached separately. Contains:
- 5 different date formats
- Missing values in Date, Amount, Product, and Customer columns
- 1 blank row in the middle of the data
