"""
test_data_cleaning.py — Automated regression tests for the data-cleaning pipeline.

Loops through every CSV in ``test_data/`` and runs each one through the exact
functions the app uses (``load_file`` → ``auto_detect_columns`` →
``clean_data_with_report`` → ``get_data_preview``), asserting that:

1. No exception is raised for any file (the app must never crash).
2. The date column parses as many rows as possible (not all-or-nothing).
3. Every excluded / defaulted row is visible in the cleaning report (no
   silent data loss — the "no silent assumptions" rule from INSTRUCTIONS).
4. Known correctness checks for the messy files pass (e.g. the -4.50 refund
   in ``test_messy_4`` keeps its negative sign).

Usage:
    python test_data_cleaning.py

Exit code is 0 when all files pass, 1 otherwise.
"""

import glob
import os
import sys
from typing import Optional

from data_utils import (
    auto_detect_columns,
    clean_data_with_report,
    get_data_preview,
    load_file,
)

TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data")


class _FakeUpload:
    """Minimal stand-in for a Streamlit UploadedFile (only .name/.read used)."""

    def __init__(self, path: str):
        self.name = os.path.basename(path)
        self._path = path

    def read(self, *args, **kwargs):
        with open(self._path, "rb") as fh:
            return fh.read()


def _run_pipeline(csv_path: str) -> dict:
    """Run one file through the full pipeline; return the results dict."""
    df = load_file(_FakeUpload(csv_path))
    assert df is not None and not df.empty, "load_file returned empty/None"

    detected = auto_detect_columns(df)
    cleaned, report = clean_data_with_report(
        df,
        date_col=detected["date_col"],
        amount_col=detected["amount_col"],
        product_col=detected["product_col"],
        category_col=detected["category_col"],
    )
    preview = get_data_preview(
        cleaned,
        date_col=detected["date_col"],
        amount_col=detected["amount_col"],
    )
    return {
        "df": df,
        "cleaned": cleaned,
        "detected": detected,
        "report": report,
        "preview": preview,
    }


def _fmt_mapping(detected: dict) -> str:
    parts = []
    for key in ("date_col", "amount_col", "product_col", "category_col"):
        parts.append(f"{key}={detected.get(key) or '—'}")
    return "  ".join(parts)


def _check_file(path: str) -> tuple[list[str], Optional[dict]]:
    """Run the pipeline on one file; return (failure messages, result dict).

    The result dict is returned so ``main`` can print its summary without
    re-running the whole pipeline.
    """
    name = os.path.basename(path)
    failures = []

    try:
        res = _run_pipeline(path)
    except Exception as exc:  # noqa: BLE001 — we want any exception caught here
        return [f"{name}: CRASHED with {type(exc).__name__}: {exc}"], None

    report = res["report"]
    detected = res["detected"]
    cleaned = res["cleaned"]

    # --- Assertion 1: no silent data loss — excluded rows must be counted ---
    source = report["rows_source"]
    used = report["rows_used"]
    excluded = source - used
    counted = (
        report["rows_blank_dropped"]
        + report["rows_date_dropped"]
        + report["rows_amount_dropped"]
    )
    if excluded != counted:
        failures.append(
            f"{name}: excluded ({excluded}) != counted in report ({counted})"
        )

    # --- Assertion 2: date parsing is best-effort, not all-or-nothing ---
    if detected["date_col"]:
        raw_dates = res["df"][detected["date_col"]]
        non_empty = raw_dates.notna().sum()
        parsed = cleaned[detected["date_col"]]
        if non_empty > 0 and report["date_parse_failed"]:
            failures.append(f"{name}: whole date column failed to parse")
        if non_empty > 0:
            parse_pct = (parsed.notna().sum() / non_empty) * 100
            if parse_pct < 50:
                failures.append(
                    f"{name}: date parse rate too low ({parse_pct:.0f}%)"
                )

    # --- Known-content checks for the messy files ---
    if name == "test_messy_4_worst_case.csv":
        amt = cleaned[detected["amount_col"]]
        if not (amt < 0).any():
            failures.append(f"{name}: -4.50 refund lost its negative sign!")
        if res["df"].shape[1] != 6 or "Barang" not in res["df"].columns:
            failures.append(f"{name}: header row was not detected correctly")

    if name == "test_messy_2_columns_currency.csv":
        amt = cleaned[detected["amount_col"]]
        # 10 rows: RM4.50, 6, RM 3.50, 2.00, RM5, RM6.50, rm2.00, 3.5, 4.5, 6
        if round(float(amt.sum()), 2) != 43.5:
            failures.append(f"{name}: rm2.00 / RM5 / '6' did not all parse")

    # --- Industry checks: every file must produce at least a used row ---
    if used == 0:
        failures.append(f"{name}: no rows survived cleaning")

    return failures, res


def main() -> int:
    csv_files = sorted(glob.glob(os.path.join(TEST_DATA_DIR, "*.csv")))
    if not csv_files:
        print(f"No CSV files found in {TEST_DATA_DIR}")
        return 1

    print(f"Running data-cleaning regression tests on {len(csv_files)} files...\n")
    header = f"{'File':<38} {'Source':>7} {'Used':>7} {'Blank':>7} {'DateBad':>7} {'AmtBad':>7} {'Unknown':>8}  Mapping"
    print(header)
    print("-" * len(header))

    all_failures = []
    for path in csv_files:
        name = os.path.basename(path)
        failures, res = _check_file(path)

        # Print the summary line (from the report) so it is easy to eyeball
        if not failures:
            report = res["report"]
            detected = res["detected"]
            defaults = report["products_defaulted"] + report["categories_defaulted"]
            print(
                f"{name:<38} {report['rows_source']:>7} {report['rows_used']:>7} "
                f"{report['rows_blank_dropped']:>7} {report['rows_date_dropped']:>7} "
                f"{report['rows_amount_dropped']:>7} {defaults:>8}  "
                f"{_fmt_mapping(detected)}"
            )
        else:
            for f in failures:
                print(f"FAIL  {f}")
        all_failures.extend(failures)

    print("-" * len(header))
    if all_failures:
        print(f"\n{len(all_failures)} failure(s) across {len(csv_files)} files")
        for f in all_failures:
            print(f"  - {f}")
        return 1

    print(f"\nAll {len(csv_files)} test files passed the cleaning pipeline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
