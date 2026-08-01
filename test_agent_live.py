"""
test_agent_live.py — End-to-end live test of the AI chat agent.

Runs the FULL pipeline exactly like the app does:

    load_file -> auto_detect_columns -> clean_data_with_report
    -> BusinessAgent.process_message (real Gemini call + function calling)

on the CLEANED DataFrame, then asserts that the agent's answer contains the
REAL totals computed from that cleaned data — proving the function-calling
round-trip works end-to-end and the model is not hallucinating numbers.

Requires a Gemini API key (reads ``.streamlit/secrets.toml``, the
``GEMINI_API_KEY`` env var, or ``--api-key``).  Skips (exit 0) when no key is
available so the offline suite still works on machines without one.

Usage:
    python test_agent_live.py                          # sample_sales_data.csv
    python test_agent_live.py --file test_messy_1_dates_missing.csv
    python test_agent_live.py --api-key AIza...

Note: on Python 3.9/3.10 the ``tomllib`` stdlib module does not exist, so
this script falls back to the ``tomli`` backport — install it with
``pip install tomli`` if you run this test on those versions.
"""

import argparse
import os
import re
import sys

try:  # Python 3.11+
    import tomllib
except ImportError:  # Python 3.9/3.10 — use the backport
    import tomli as tomllib  # type: ignore[no-redef]

from agent import BusinessAgent
from data_utils import auto_detect_columns, clean_data_with_report, load_file

TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data")


class _FakeUpload:
    """Minimal stand-in for a Streamlit UploadedFile (only .name/.read used)."""

    def __init__(self, path: str):
        self.name = os.path.basename(path)
        self._path = path

    def read(self, *args, **kwargs):
        with open(self._path, "rb") as fh:
            return fh.read()


def _get_api_key(cli_key: str) -> str:
    """Resolve the Gemini API key: CLI arg > env var > secrets.toml."""
    if cli_key:
        return cli_key
    env_key = os.environ.get("GEMINI_API_KEY", "")
    if env_key:
        return env_key
    secrets_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), ".streamlit", "secrets.toml"
    )
    if os.path.exists(secrets_path):
        with open(secrets_path, "rb") as fh:
            return tomllib.load(fh).get("GEMINI_API_KEY", "")
    return ""


def _extract_numbers(text: str) -> list[float]:
    """Extract every decimal number (incl. comma thousands) from text."""
    return [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]


def _numbers_near(text: str, keywords, window: int = 40) -> list[float]:
    """Extract numbers that appear within ``window`` chars of any keyword.

    Used to anchor the transaction-count assertion so digits inside dates or
    unrelated figures can't false-positive it.
    """
    if isinstance(keywords, str):
        keywords = (keywords,)
    found = []
    for kw in keywords:
        for m in re.finditer(kw, text, re.IGNORECASE):
            snippet = text[max(0, m.start() - window): m.start() + window]
            found.extend(_extract_numbers(snippet))
    return found


def _run(path: str, api_key: str) -> int:
    """Run the pipeline + live agent call; return process exit code."""
    # --- Run the exact pipeline the app uses ---
    df = load_file(_FakeUpload(path))
    if df is None or df.empty:
        print(f"FAIL: load_file returned empty/None for {os.path.basename(path)}")
        return 1

    detected = auto_detect_columns(df)
    cleaned, report = clean_data_with_report(
        df,
        date_col=detected["date_col"],
        amount_col=detected["amount_col"],
        product_col=detected["product_col"],
        category_col=detected["category_col"],
    )
    if cleaned.empty:
        print(f"FAIL: no rows survived cleaning for {os.path.basename(path)}")
        return 1

    amount_col = detected["amount_col"]
    if not amount_col or amount_col not in cleaned.columns:
        print(f"FAIL: no amount column detected for {os.path.basename(path)}")
        return 1

    # --- Ground truth computed from the CLEANED data ---
    expected_total = round(float(cleaned[amount_col].sum()), 2)
    expected_count = len(cleaned)
    print(f"File: {os.path.basename(path)}  ({report['rows_used']}/{report['rows_source']} rows used)")
    print(f"Ground truth: total = RM {expected_total:,.2f}, transactions = {expected_count}")

    # --- Live agent call (full function-calling loop) ---
    agent = BusinessAgent(api_key=api_key)
    if agent.model_name != "gemini-3.5-flash":
        print(f"FAIL: unexpected model '{agent.model_name}' (expected gemini-3.5-flash)")
        return 1
    print(f"Model: {agent.model_name}")

    question = "What were my total sales and how many transactions did I have?"
    response = agent.process_message(question, cleaned, detected)
    print(f"\nAgent response:\n{response}\n")

    # --- Assert the response contains the REAL totals, not hallucinations ---
    # Tolerance: allow normal rounding (to whole RM / nearest 100) but catch
    # hallucinated values, which are typically far off.
    tol = max(1.0, expected_total * 0.02)
    numbers = _extract_numbers(response)
    total_match = any(abs(n - expected_total) <= tol for n in numbers)

    # Anchor the count to words the model may use for it ("transaction(s)",
    # "order(s)", "sale(s)") so digits inside dates can't false-positive it.
    count_numbers = _numbers_near(response, ("transaction", "order", "sale"))
    count_match = expected_count in {round(n) for n in count_numbers}

    if not total_match or not count_match:
        print(
            f"FAIL: response missing real totals "
            f"(expected RM {expected_total:,.2f} / {expected_count} txn; "
            f"all numbers found: {numbers}; near 'transaction': {count_numbers})"
        )
        return 1

    print(f"PASS: agent answered with real totals (RM {expected_total:,.2f}, {expected_count} transactions)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-key", default="",
        help="Gemini API key (defaults to secrets.toml / GEMINI_API_KEY env)",
    )
    parser.add_argument(
        "--file", default="sample_sales_data.csv",
        help="CSV in test_data/ to run through the agent",
    )
    args = parser.parse_args()

    api_key = _get_api_key(args.api_key)
    if not api_key:
        print("SKIP: no Gemini API key found (secrets.toml / GEMINI_API_KEY / --api-key). Live test not run.")
        return 0

    path = os.path.join(TEST_DATA_DIR, args.file)
    if not os.path.exists(path):
        print(f"FAIL: {path} not found")
        return 1

    try:
        return _run(path, api_key)
    except Exception as exc:  # noqa: BLE001 — report any failure cleanly
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
