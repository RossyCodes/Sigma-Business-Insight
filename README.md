# Σ Sigma Business Insight

An AI-powered business analytics dashboard built with **Streamlit**, **Gemini**, and **Plotly**. Upload your sales data (CSV or Excel), and instantly get KPI cards, trend charts, product rankings, category breakdowns, period comparisons, PDF reports — plus a bilingual (English / Bahasa Melayu) AI chat agent that answers questions about your data.

## ✨ Features

- **📤 Upload & Auto-Detect** — Drop in a CSV or XLSX file; the app auto-detects date, amount, product, and category columns (adjustable).
- **📊 Instant Dashboard** — KPI cards (total sales, transactions, avg order value), sales trend, top products, category breakdown, and a raw-data viewer.
- **🔍 Smart Filters** — Filter by year, month, product, category, and amount range. All charts, KPIs, and exports respect your filters.
- **📄 PDF Report** — Export the filtered dashboard as a polished PDF report with one click.
- **🤖 AI Chat Agent** — Ask questions about your data in plain English or Bahasa Melayu. The agent uses **manual function calling** (`google.genai` SDK) to run real analysis tools on your dataset.
- **⚡ Quick Insights** — One-click report that runs all 4 analysis tools directly (works even **without** an API key).
- **🌐 Bilingual UI** — Switch between English and Bahasa Melayu anytime.
- **🌙 Dark Sigma Design** — Custom dark theme with layered-blue glows, Space Grotesk / Inter / JetBrains Mono typography.

## 🧰 Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Streamlit (custom CSS/HTML theming) |
| Charts | Plotly |
| Data | pandas, openpyxl |
| AI Agent | Google Gemini (`google-genai` SDK, model `gemini-3.5-flash`) |
| Reports | reportlab |

## 📋 Requirements

- **Python 3.9+** (recommended: 3.11+)
- `pip` (bundled with Python)

## 🚀 Setup & Run

### 1. Clone the repository

```bash
git clone https://github.com/RossyCodes/Sigma-Business-Insight.git
cd Sigma-Business-Insight
```

### 2. (Recommended) Create a virtual environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\activate
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
streamlit run app.py
```

Your browser should open at **http://localhost:8501** automatically. If not, visit the URL shown in the terminal.

### 5. Optional — Configure a Gemini API key

The full dashboard, filters, and PDF export work with **no API key**. The AI chat agent needs a Gemini API key, which you can provide in any of these ways (in order of precedence):

1. **`.streamlit/secrets.toml`** (recommended — never commit this file):

   ```toml
   GEMINI_API_KEY = "your-api-key-here"
   ```

2. **Environment variable:**

   ```bash
   export GEMINI_API_KEY="your-api-key-here"   # macOS / Linux
   set GEMINI_API_KEY=your-api-key-here        # Windows (cmd)
   ```

3. **In the app** — paste the key in the sidebar (it stays in your browser session only).

Get a free key at [Google AI Studio](https://aistudio.google.com/).

## 🧪 Try it with sample data

Sample and test datasets live in **`test_data/`**:

- `sample_sales_data.csv` — clean F&B-style sample (upload this first to see the full dashboard in action)
- `test_messy_1..4_*.csv` — messy real-world cases (mixed date formats, missing values, inconsistent currency, duplicate rows, a title row before the header, refunds)
- `test_industry_*.csv` — different industry shapes (retail/fashion, service/salon, wide e-commerce export)

Run `python test_data_cleaning.py` to automatically push every file through the cleaning pipeline and confirm none of them crash. To also verify the AI chat agent end-to-end against the real Gemini model (needs an API key), run `python test_agent_live.py`.

## 📂 Project Structure

```
├── app.py               # Main Streamlit app (UI, dashboard, chat, PDF export)
├── agent.py             # Gemini-powered BusinessAgent with manual function calling
├── tools.py             # Analysis tools (summary, top products, period compare, insights)
├── data_utils.py        # File loading, column auto-detection, data cleaning
├── dashboard_utils.py   # KPI cards, trend chart, top products, category breakdown
├── pdf_report.py        # PDF report generation (reportlab)
├── translations.py      # English / Bahasa Melayu translations
├── landing.html         # Landing page markup
├── requirements.txt     # Python dependencies
├── test_data/           # Sample + messy + industry test CSVs
├── test_data_cleaning.py  # Automated regression tests for the cleaning pipeline
└── .streamlit/secrets.toml  # (local only — gitignored, never commit)
```

## 🔒 Security Notes

- **Never commit** `.streamlit/secrets.toml` — it is excluded via `.gitignore`.
- Runtime logs (`*.log`) are gitignored.
- Your API key is only sent to Google's Gemini API; it is never written to disk when pasted in the app.

## 📄 License

See [license](license) file for details
