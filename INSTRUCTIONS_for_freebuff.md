Once the current bug fix (date parsing / crash on messy data) is done, please do the following:

## 1. Set up a test data folder

- Create a new folder in the repo: `test_data/`
- Move the existing `sample_sales_data.csv` into `test_data/` (update any file path references in the code that point to it, e.g. in `app.py` or wherever the sample file is loaded/referenced)
- I'm attaching 4 additional CSV files — add them to the same `test_data/` folder:
  - `test_messy_1_dates_missing.csv` — mixed date formats + missing values + a blank row
  - `test_messy_2_columns_currency.csv` — non-standard column names/order + inconsistent currency formatting (e.g. "RM4.50", "6", "rm2.00")
  - `test_messy_3_typos_duplicates.csv` — inconsistent category casing/whitespace ("Food" vs "food" vs "FOOD ") + duplicate rows
  - `test_messy_4_worst_case.csv` — combines all of the above, plus a title row before the actual header, a refund/negative amount, and Bahasa Melayu column names

Final structure should look like:
```
test_data/
├── sample_sales_data.csv
├── test_messy_1_dates_missing.csv
├── test_messy_2_columns_currency.csv
├── test_messy_3_typos_duplicates.csv
└── test_messy_4_worst_case.csv
```

## 2. Verify the fix against all test files

After the current bug is patched, please manually test by uploading each of the 4 messy files above into the app (not just the file that caused the original crash) and confirm for each one:

- The app does NOT crash
- The date column parses as many valid rows as possible, rather than failing the whole column if even one row has a different format
- Any row that is excluded or defaulted (e.g. missing Amount, missing Product) shows a clear warning banner to the user — something like "X rows were excluded due to incomplete data" — instead of silently dropping data
- KPI totals (Total Sales, Transactions, Avg Order Value) reflect only valid rows, and that count is visible/explained somewhere in the UI

## 3. (Optional but preferred) Add an automated test script

If time allows, write a small script `test_data_cleaning.py` that:
- Loops through all files in `test_data/`
- Runs each through the existing data cleaning / preview function(s) in `data_utils.py`
- Asserts that no exception is raised for any file
- Prints a summary of rows loaded vs rows excluded per file

This makes it easy to re-run all test cases at once in the future instead of manually uploading files one by one through the UI.

## 4. Test with different industry data structures (not just F&B)

The current sample data and test files are all F&B-style (Product, Category, Amount). Real clients will come from different industries with very different column structures. I'm attaching 3 more test files:

- `test_industry_retail.csv` — retail/fashion structure: SKU, Size, Colour, Quantity, Unit Price (no single "Amount" column — total needs to be calculated from Quantity × Unit Price)
- `test_industry_service.csv` — service business (salon) structure: Staff, Duration, Price (no "Product/Category" in the usual sense — service type is the closest equivalent)
- `test_industry_ecommerce_wide.csv` — e-commerce structure with 15 columns, many of which are irrelevant to the core analysis (Tracking Number, Payment Method, Buyer Username, Order Status, etc.) — this tests whether the app can correctly identify the relevant columns (Date, Amount/Total, Product) and ignore the noise, rather than getting confused by extra columns

Please add these 3 files to `test_data/` as well, and test the Column Mapping feature against each one. The goal is to confirm the auto-detect + manual override dropdowns genuinely work across different data shapes, not just the F&B format the app was originally built around.

## 5. Critical: No silent assumptions, no silent data deletion

This is important for client trust, so please treat it as a hard rule, not a nice-to-have:

- **Never auto-delete or auto-exclude rows without telling the user.** If a row can't be processed (bad date, missing amount, etc.), it must be visibly flagged to the user (e.g. in a warning banner or a "rows excluded" summary), not silently dropped from calculations.
- **Never guess or fill in missing values without flagging it.** If a Product name, Amount, or Date is missing, do not invent a placeholder value that looks like real data (e.g. don't fill in an average price or a guessed date). Either leave it clearly marked as missing/incomplete, or exclude it and report the exclusion.
- **If the AI chat agent is asked a question that depends on incomplete data, it should say so** — e.g. "Note: 3 rows had missing dates and were excluded from this trend analysis" — rather than answering as if the full dataset was clean.
- The reasoning here: this tool will be used by real SME owners making real business decisions. A wrong number presented with confidence is more dangerous than an error message. Silent data manipulation (deleting, guessing, assuming) is not acceptable anywhere in this app, even if it makes the dashboard "look" cleaner.

## Reference

Full bug report with reproduction steps and root cause analysis for the original crash is in `BUG_REPORT_messy_data_handling.md` (attached separately) — use it as context for what "correct" behavior should look like after the fix.
