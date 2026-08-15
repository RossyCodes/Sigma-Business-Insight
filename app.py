"""
app.py — Business Insight Agent (Part 1 + Part 2)

Part 1: Data upload + auto-generated dashboard (KPI cards, trend chart,
         top-products chart, category breakdown).
Part 2: Bilingual UI (EN / BM) + Gemini-powered AI chat agent with manual
         function calling — ask questions about your data in either language.
"""

import calendar
import html
import os
import re
from datetime import datetime

import pandas as pd
import streamlit as st

from agent import BusinessAgent
from data_utils import (
    auto_detect_columns,
    clean_data_with_report,
    get_data_preview,
    load_file,
)
from dashboard_utils import (
    render_category_breakdown,
    render_kpi_cards,
    render_sales_trend,
    render_top_products,
)
from tools import (
    compare_periods,
    generate_insight,
    get_sales_summary,
    get_top_products,
)
from translations import t
from pdf_report import build_report_pdf

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

# Same Σ favicon as the landing page (landing.html) so both feel like one product.
_FAVICON_SIGMA = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
    "%3Crect width='32' height='32' rx='7' fill='%230B1830'/%3E"
    "%3Cpath d='M9 9h14l-8 7 8 7H9z' fill='none' stroke='%238FD4FF' "
    "stroke-width='2' stroke-linejoin='round'/%3E%3C/svg%3E"
)

st.set_page_config(
    page_title="Sigma — Business Insight Agent",
    page_icon=_FAVICON_SIGMA,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state initialisation (MUST be before any st.session_state reads)
# ---------------------------------------------------------------------------

# Part 1 state
if "df_raw" not in st.session_state:
    st.session_state.df_raw = None
if "df_clean" not in st.session_state:
    st.session_state.df_clean = None
if "detected" not in st.session_state:
    st.session_state.detected = {}
if "uploaded_filename" not in st.session_state:
    st.session_state.uploaded_filename = None
if "file_processed" not in st.session_state:
    st.session_state.file_processed = False
if "clean_report" not in st.session_state:
    st.session_state.clean_report = None


# Part 2 state
if "language" not in st.session_state:
    st.session_state.language = "en"

if "gemini_api_key" not in st.session_state:
    st.session_state.gemini_api_key = None
if "agent" not in st.session_state:
    st.session_state.agent = None
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "agent_initialized" not in st.session_state:
    st.session_state.agent_initialized = False
if "pdf_insights_text" not in st.session_state:
    st.session_state.pdf_insights_text = ""

# ---------------------------------------------------------------------------
# Dark theme CSS — Sigma layered-blue design
# ---------------------------------------------------------------------------

_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {
        --void: #050B18;
        --ink: #0B1830;
        --struct: #1B3A6B;
        --signal: #2F6FED;
        --ice: #8FD4FF;
        --text: #E8EEF9;
        --muted: rgba(232,238,249,.64);
        --faint: rgba(232,238,249,.38);
        --line: rgba(143,212,255,.14);
        --line-soft: rgba(143,212,255,.08);
        --glow: rgba(47,111,237,.55);
        --ice-glow: rgba(143,212,255,.35);
        --font-display: 'Space Grotesk', system-ui, sans-serif;
        --font-body: 'Inter', system-ui, sans-serif;
        --font-mono: 'JetBrains Mono', ui-monospace, monospace;
    }

    /* ---- Main app: deep void + layered blue glows ---- */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background: var(--void) !important;
    }
    .main .block-container {
        background: transparent !important;
        padding-top: 2.2rem;
        padding-bottom: 2.5rem;
        max-width: 1180px;
    }
    body, .stApp, .main p, .main span, .main div, .main li, .main .stMarkdown p {
        font-family: var(--font-body);
        color: var(--muted);
    }

    /* ---- Sidebar: ink panel ---- */
    section[data-testid="stSidebar"] {
        background: var(--ink) !important;
        border-right: 1px solid var(--line);
    }
    section[data-testid="stSidebar"] .block-container { padding-top: 1.6rem; }
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] div,
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] .st-cb,
    section[data-testid="stSidebar"] .st-da,
    section[data-testid="stSidebar"] .st-dc,
    section[data-testid="stSidebar"] .st-dd,
    section[data-testid="stSidebar"] .st-de {
        color: var(--text) !important;
    }
    section[data-testid="stSidebar"] .stCaption,
    section[data-testid="stSidebar"] small,
    section[data-testid="stSidebar"] .st-dg {
        color: var(--faint) !important;
    }

    /* ---- Headers: Space Grotesk ---- */
    h1, h2, h3 {
        font-family: var(--font-display);
        font-weight: 600;
        letter-spacing: -0.01em;
        color: var(--text) !important;
    }
    h4, h5, h6 { font-family: var(--font-display); color: var(--text) !important; }

    /* ---- File uploader: upload-box style ---- */
    .stFileUploader {
        background: rgba(11,24,48,.6) !important;
        border-radius: 12px;
        border: 1.5px dashed rgba(143,212,255,.34) !important;
        padding: 1rem;
        transition: border-color .3s, background .3s;
    }
    .stFileUploader:hover { border-color: rgba(143,212,255,.65) !important; background: rgba(47,111,237,.06) !important; }
    .stFileUploader label, .stFileUploader span, .stFileUploader small { color: var(--faint) !important; }

    /* ---- Buttons ---- */
    .stButton button {
        font-family: var(--font-display);
        border-radius: 12px !important;
        font-weight: 600;
        letter-spacing: .01em;
        transition: transform .2s ease, box-shadow .3s ease, background .3s ease, border-color .3s ease;
    }
    .stButton button[kind="primary"] {
        background: linear-gradient(135deg,#2F6FED 0%,#2457c4 55%,#2F6FED 120%) !important;
        color: #FFFFFF !important;
        border: none !important;
        box-shadow: 0 0 0 1px rgba(143,212,255,.22) inset, 0 10px 34px -10px var(--glow) !important;
    }
    .stButton button[kind="primary"]:hover {
        background: linear-gradient(135deg,#3a7bf7 0%,#2a63d4 55%,#3a7bf7 120%) !important;
        box-shadow: 0 0 0 1px rgba(143,212,255,.5) inset, 0 16px 44px -10px var(--glow), 0 0 28px -6px var(--ice-glow) !important;
        transform: translateY(-1px);
    }
    .stButton button[kind="secondary"] {
        background: rgba(27,58,107,.3) !important;
        color: var(--ice) !important;
        border: 1px solid var(--line) !important;
    }
    .stButton button[kind="secondary"]:hover {
        background: rgba(27,58,107,.55) !important;
        border-color: rgba(143,212,255,.45) !important;
        transform: translateY(-1px);
    }

    /* ---- Select / Input ---- */
    .stSelectbox div[data-baseweb="select"] {
        background: rgba(11,24,48,.6) !important;
        border-color: var(--line) !important;
    }
    .stSelectbox div[data-baseweb="select"] span { color: var(--text) !important; }
    div[data-baseweb="popover"] ul, div[data-baseweb="menu"] {
        background: var(--ink) !important;
        border: 1px solid var(--line) !important;
    }
    div[data-baseweb="popover"] li, div[data-baseweb="menu"] li { color: var(--muted) !important; }
    .stTextInput input {
        border-radius: 10px; background: rgba(11,24,48,.6) !important; color: var(--text) !important; border-color: var(--line) !important;
    }
    .stTextInput input:focus { border-color: var(--signal) !important; box-shadow: 0 0 0 2px rgba(47,111,237,.3); }

    /* ---- Chat: Sigma bubbles ---- */
    .stChatMessage { margin-bottom: 0.5rem; }
    .stChatMessage p { color: var(--text) !important; }
    div[data-testid="stChatMessage"] {
        background: rgba(11,24,48,.82) !important;
        border: 1px solid var(--line) !important;
        border-radius: 12px 12px 12px 3px;
        padding: 0.75rem 1rem;
        box-shadow: 0 14px 34px -14px rgba(0,0,0,.7);
    }
    .stChatInputContainer {
        background: rgba(11,24,48,.82) !important;
        border: 1px solid var(--line) !important;
        border-radius: 12px !important;
        box-shadow: 0 14px 34px -14px rgba(0,0,0,.7);
    }
    .stChatInputContainer input { color: var(--text) !important; font-family: var(--font-body); }
    .stChatInputContainer input::placeholder { color: var(--faint) !important; }

    /* ---- Status / Spinner ---- */
    .stStatus { background: rgba(11,24,48,.82) !important; border-radius: 12px; border: 1px solid var(--line); }
    .stStatus div[data-testid="stStatusCaption"] { color: var(--text) !important; }

    /* ---- Expander ---- */
    .stExpander {
        background: rgba(11,24,48,.72) !important;
        border: 1px solid var(--line) !important;
        border-radius: 14px;
    }
    .stExpander summary { color: var(--text) !important; font-family: var(--font-display); }

    /* ---- Dataframe ---- */
    .stDataFrame { color: var(--text) !important; }
    .stDataFrame div[data-testid="StyledDataFrameCol"] { color: var(--text) !important; }

    /* ---- Alerts / Dividers ---- */
    .stAlert { border-radius: 12px; border: 1px solid var(--line) !important; }
    .stAlert p { color: inherit !important; }
    hr { margin: 1.5rem 0; border-color: var(--line) !important; }

    /* ---- Info / Success ---- */
    .stInfo { background: rgba(27,58,107,.35) !important; color: var(--ice) !important; }
    .stSuccess { background: rgba(16,102,66,.3) !important; color: #A7F3D0 !important; border: 1px solid rgba(167,243,208,.25) !important; }
    .stError { background: rgba(127,29,29,.35) !important; color: #FECACA !important; border: 1px solid rgba(254,202,202,.25) !important; }
    .stWarning { background: rgba(113,63,18,.35) !important; color: #FDE68A !important; border: 1px solid rgba(253,230,138,.25) !important; }

    /* ---- Tables ---- */
    table { color: var(--muted) !important; font-family: var(--font-body); }
    table th { background: var(--ink) !important; color: var(--faint) !important; font-family: var(--font-mono); font-size: .72rem; letter-spacing: .14em; text-transform: uppercase; }
    table td { color: var(--muted) !important; }

    /* ---- Plotly cards ---- */
    div[data-testid="stPlotlyChart"] { background: transparent !important; }

    /* ---- KPI cards: responsive grid (4 -> 2 -> 1 columns) ---- */
    .sigma-kpi-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1rem;
    }
    .sigma-kpi-grid .sigma-kpi { height: 100%; }
    .sigma-kpi-grid .sigma-kpi-label { font-size: 0.62rem; }
    .sigma-kpi-grid .sigma-kpi-value { font-size: 1.4rem; }

    /* ---- KPI cards hover (matches landing tile) ---- */
    .sigma-kpi:hover {
        border-color: rgba(143,212,255,.42) !important;
        background: rgba(27,58,107,.4) !important;
        transform: translateY(-2px);
    }

    /* ============================================================
       Mobile responsiveness (viewport < 768px and small phones)
       Only affects small screens — desktop layout is untouched.
       ============================================================ */
    @media (max-width: 768px) {
        /* Stack every Streamlit column block (filters, chart pairs,
           quick-insights row) vertically so nothing gets cramped. */
        [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap;
            gap: 0.6rem 0.75rem;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
            flex: 1 1 100% !important;
            width: 100% !important;
            min-width: 0 !important;
        }

        /* KPI cards: 2x2 grid, slightly tighter padding so values fit */
        .sigma-kpi-grid {
            grid-template-columns: repeat(2, 1fr);
            gap: 0.75rem;
        }
        .sigma-kpi-grid .sigma-kpi { padding: 16px 12px; }
        .sigma-kpi-grid .sigma-kpi-label { font-size: 0.56rem; }
        .sigma-kpi-grid .sigma-kpi-value { font-size: clamp(1rem, 4.6vw, 1.25rem); }
    }
    @media (max-width: 480px) {
        /* Very small phones: KPI cards stack to a single column */
        .sigma-kpi-grid { grid-template-columns: 1fr; }
    }

</style>"""


# Apply the dark theme CSS
st.markdown(_CSS, unsafe_allow_html=True)

# Mobile-only: auto-collapse the sidebar on first load so the dashboard
# isn't hidden behind the upload panel on phones. Desktop (>=768px) is
# untouched — the script only acts on narrow parent windows and only once
# per tab. An iframe is used because Streamlit renders st.markdown
# scripts inert (inserted via innerHTML), whereas st.iframe embeds a
# real iframe whose script runs and can reach window.parent.
st.iframe(
    """
<script>
(function () {
    var w = window.parent;
    if (w.innerWidth >= 768) return;  // desktop — leave Streamlit alone
    var done = false;
    try { done = w.sessionStorage.getItem("sigma-sidebar-collapsed") === "1"; } catch (e) {}
    if (done) return;
    var tries = 0;
    var timer = setInterval(function () {
        tries += 1;
        var doc = w.document;
        var sb = doc.querySelector('section[data-testid="stSidebar"]');
        var btn = doc.querySelector('button[data-testid="stBaseButton-headerNoPadding"]')
               || doc.querySelector('button[data-testid="stSidebarCollapsedControl"]');
        if (sb && sb.getAttribute("aria-expanded") === "true" && btn) {
            btn.click();
            try { w.sessionStorage.setItem("sigma-sidebar-collapsed", "1"); } catch (e) {}
            clearInterval(timer);
        } else if (tries > 40) {
            clearInterval(timer);  // give up after ~12s if the toggle never appears
        }
    }, 300);
})();
</script>
""",
    height=1,  # 1px so the helper iframe is invisible
)

# ---------------------------------------------------------------------------
# Helper: initialise / re-initialise the agent
# ---------------------------------------------------------------------------

def init_agent(api_key: str):
    """Create or re-create the BusinessAgent."""
    try:
        st.session_state.agent = BusinessAgent(api_key=api_key)
        st.session_state.agent_initialized = True
        st.session_state.chat_messages = []
        return True
    except Exception:
        st.session_state.agent = None
        st.session_state.agent_initialized = False
        return False


# ---------------------------------------------------------------------------
# Silent auto-init: check for Gemini API key from env / secrets.toml
# This runs invisibly — no UI is rendered.
# ---------------------------------------------------------------------------

_secrets_key = ""
try:
    _secrets_key = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    pass  # No secrets.toml file exists — that's fine

_env_key = os.environ.get("GEMINI_API_KEY", "")
_session_key = st.session_state.gemini_api_key or ""

_auto_key = _session_key or _env_key or _secrets_key

if _auto_key and not st.session_state.agent_initialized:
    st.session_state.gemini_api_key = _auto_key
    init_agent(_auto_key)

# ---------------------------------------------------------------------------
# Helper: run all 4 tools and format a comprehensive report
# ---------------------------------------------------------------------------

def _run_quick_insights(df, detected, lang):
    """Run all 4 analysis tools on the data and return a formatted markdown
    report.  This function calls the actual Python tool functions directly
    (not via Gemini), so it works instantly without an API key."""
    date_col = detected.get("date_col")
    amount_col = detected.get("amount_col")
    product_col = detected.get("product_col")
    category_col = detected.get("category_col")

    lines = []

    # ---- Header ----
    lines.append(f"## {t('quick_insights_title', lang)}\n")

    # ---- 1. Sales Summary ----
    summary = get_sales_summary(df, amount_col=amount_col, date_col=date_col)
    lines.append(f"### {t('quick_insights_summary_title', lang)}")
    if "error" in summary:
        lines.append(f"⚠️ {summary['error']}")
    else:
        lines.append(f"| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| **{t('total_sales', lang)}** | RM {summary['total_sales']:,.2f} |")
        lines.append(f"| **{t('transactions_kpi', lang)}** | {summary['transaction_count']:,} |")
        lines.append(f"| **{t('avg_order_value', lang)}** | RM {summary['avg_order_value']:,.2f} |")
        lines.append(f"| **Date Range** | {summary.get('start_date', 'N/A')} – {summary.get('end_date', 'N/A')} |")
        lines.append(f"| **Days of Data** | {summary.get('date_range_days', 'N/A')} |")
    lines.append("")

    # ---- 2. Top Products ----
    lines.append(f"### {t('quick_insights_products_title', lang)}")
    products = get_top_products(df, product_col=product_col, amount_col=amount_col, n=5)
    if not products or "error" in products[0] or "info" in products[0]:
        msg = products[0].get("error", products[0].get("info", t("quick_insights_no_products", lang)))
        lines.append(f"_{msg}_")
    else:
        lines.append(f"| # | Product | Sales (RM) | Share |")
        lines.append("|---|---------|-----------|-------|")
        for i, p in enumerate(products, 1):
            lines.append(f"| {i} | {p['product']} | RM {p['total_sales']:,.2f} | {p['percentage']}% |")
    lines.append("")

    # ---- 3. Period Comparison (auto: split data into two halves) ----
    lines.append(f"### {t('quick_insights_comparison_title', lang)}")
    if (date_col and date_col in df.columns
            and amount_col and amount_col in df.columns
            and pd.api.types.is_datetime64_any_dtype(df[date_col])
            and df[date_col].nunique() >= 2):
        min_date = df[date_col].min()
        max_date = df[date_col].max()
        total_days = (max_date - min_date).days
        mid_date = min_date + (max_date - min_date) / 2

        period_a_start = min_date.strftime("%Y-%m-%d")
        period_a_end = mid_date.strftime("%Y-%m-%d")
        period_b_start = (mid_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        period_b_end = max_date.strftime("%Y-%m-%d")

        comparison = compare_periods(
            df, date_col=date_col, amount_col=amount_col,
            period_a_start=period_a_start, period_a_end=period_a_end,
            period_b_start=period_b_start, period_b_end=period_b_end,
        )

        if "error" in comparison or "info" in comparison:
            lines.append(f"_{comparison.get('error', comparison.get('info', ''))}_")
        else:
            pa = comparison["period_a"]
            pb = comparison["period_b"]
            ch = comparison["change"]

            direction_icon = "📈" if ch["direction"] == "increased" else "📉" if ch["direction"] == "decreased" else "➡️"
            lines.append(f"| Metric | Period A | Period B | Change |")
            lines.append("|--------|----------|----------|--------|")
            lines.append(f"| **Sales** | RM {pa['sales']:,.2f} | RM {pb['sales']:,.2f} | {direction_icon} {ch['percentage_change']:+.1f}% |")
            lines.append(f"| **Transactions** | {pa['transactions']} | {pb['transactions']} | — |")
            lines.append(f"| **Avg Order** | RM {pa['avg_order']:,.2f} | RM {pb['avg_order']:,.2f} | — |")
            lines.append(f"| **Days** | {pa['days']} | {pb['days']} | — |")
            lines.append("")
            lines.append(f"*Period A: {pa['label']}  ·  Period B: {pb['label']}*")
    else:
        lines.append(f"_{t('quick_insights_no_comparison', lang)}_")
    lines.append("")

    # ---- 4. Insights & Recommendations ----
    lines.append(f"### {t('quick_insights_insights_title', lang)}")
    insight = generate_insight(
        df, amount_col=amount_col, date_col=date_col,
        product_col=product_col, category_col=category_col,
    )
    if "error" in insight:
        lines.append(f"⚠️ {insight['error']}")
    else:
        # Trend
        if insight.get("trend") and insight["trend"].get("detail"):
            lines.append(f"**Trend:** {insight['trend']['detail']}")
            if "daily_avg_first_half" in insight["trend"]:
                lines.append(
                    f"*Daily average: RM {insight['trend']['daily_avg_first_half']:,.2f} "
                    f"→ RM {insight['trend']['daily_avg_second_half']:,.2f}*"
                )
            lines.append("")

        # Top performing product
        if insight.get("top_products"):
            top = insight["top_products"][0]
            lines.append(f"**Best Performer:** _{top['product']}_ — RM {top['sales']:,.2f} ({top['share']}% of sales)")
            lines.append("")

        # Category highlight
        if insight.get("category_performance"):
            top_cat = insight["category_performance"][0]
            lines.append(f"**Top Category:** _{top_cat['category']}_ — {top_cat['share']}% of sales")
            lines.append("")

        # Recommendations
        if insight.get("recommendations"):
            lines.append("**Recommendations:**")
            for i, rec in enumerate(insight["recommendations"], 1):
                lines.append(f"{i}. {rec}")

    return "\n".join(lines)


@st.cache_data(show_spinner=False)
def _build_pdf_cached(df, detected, filename, lang, filter_desc, insights_text):
    """Build the report PDF bytes, cached per filtered dataset."""
    return build_report_pdf(
        df, detected, filename, lang=lang,
        filter_desc=filter_desc, insights_text=insights_text,
    )


# ---------------------------------------------------------------------------
# Sidebar — Language toggle + Upload section
# ---------------------------------------------------------------------------

with st.sidebar:
    # --- Language toggle ---
    st.markdown(f"### 🌐 {t('language', st.session_state.language)}")
    lang_col1, lang_col2 = st.columns(2)
    with lang_col1:
        if st.button(
            "English",
            width="stretch",
            type="primary" if st.session_state.language == "en" else "secondary",
            key="btn_en",
        ):
            st.session_state.language = "en"
            st.rerun()
    with lang_col2:
        if st.button(
            "Melayu",
            width="stretch",
            type="primary" if st.session_state.language == "bm" else "secondary",
            key="btn_bm",
        ):
            st.session_state.language = "bm"
            st.rerun()

    st.markdown("---")

    # --- Upload section ---
    _L = st.session_state.language
    st.markdown(f"### {t('upload_title', _L)}")
    uploaded_file = st.file_uploader(
        t("upload_label", _L),
        type=["csv", "xlsx"],
        help=t("upload_help", _L),
    )

    if uploaded_file is not None:
        if uploaded_file.name != st.session_state.uploaded_filename:
            st.session_state.uploaded_filename = uploaded_file.name
            st.session_state.file_processed = False

        with st.spinner(t("reading_file", _L)):
            df = load_file(uploaded_file)

        if df is None or df.empty:
            st.error(t("file_error", _L))
            st.session_state.df_raw = None
            st.session_state.df_clean = None
        else:
            st.session_state.df_raw = df
            detected = auto_detect_columns(df)
            st.session_state.detected = detected

            st.markdown(f"### {t('column_mapping', _L)}")
            st.caption(t("column_mapping_hint", _L))

            # --- Helper: render an auto-detect badge ---
            def _detect_badge(col_key: str, required: bool = True):
                col_name = detected.get(col_key)
                if col_name and col_name in df.columns:
                    style = "display:inline-block;background:rgba(47,111,237,.16);color:#8FD4FF;font-family:'JetBrains Mono',monospace;font-size:0.68rem;padding:2px 10px;border-radius:20px;font-weight:500;margin:0 0 6px 0;border:1px solid rgba(143,212,255,.3);"
                    st.markdown(
                        f'<span style="{style}">✓ Auto: {html.escape(str(col_name))}</span>',
                        unsafe_allow_html=True,
                    )
                else:
                    style = "display:inline-block;background:rgba(11,24,48,.6);color:rgba(232,238,249,.38);font-family:'JetBrains Mono',monospace;font-size:0.68rem;padding:2px 10px;border-radius:20px;font-weight:500;margin:0 0 6px 0;border:1px solid rgba(143,212,255,.14);"
                    label = "— Not detected" if required else "— Optional (none detected)"
                    st.markdown(
                        f'<span style="{style}">{html.escape(label)}</span>',
                        unsafe_allow_html=True,
                    )

            _detect_badge("date_col", required=True)
            date_col = st.selectbox(
                t("date_col_label", _L),
                options=df.columns.tolist(),
                index=(
                    df.columns.get_loc(detected["date_col"])
                    if detected["date_col"] and detected["date_col"] in df.columns
                    else 0
                ),
                help="Which column contains the transaction date?",
            )

            _detect_badge("amount_col", required=True)
            amount_col = st.selectbox(
                t("amount_col_label", _L),
                options=df.columns.tolist(),
                index=(
                    df.columns.get_loc(detected["amount_col"])
                    if detected["amount_col"] and detected["amount_col"] in df.columns
                    else 0
                ),
                help="Which column contains the sales amount?",
            )

            _detect_badge("product_col", required=False)
            product_col = st.selectbox(
                t("product_col_label", _L),
                options=[None] + df.columns.tolist(),
                index=(
                    df.columns.get_loc(detected["product_col"]) + 1
                    if detected["product_col"] and detected["product_col"] in df.columns
                    else 0
                ),
                help="Which column lists the product or item name? (optional)",
            )

            _detect_badge("category_col", required=False)
            category_col = st.selectbox(
                t("category_col_label", _L),
                options=[None] + df.columns.tolist(),
                index=(
                    df.columns.get_loc(detected["category_col"]) + 1
                    if detected["category_col"] and detected["category_col"] in df.columns
                    else 0
                ),
                help="Which column has the category or segment? (optional)",
            )

            if st.button(t("generate_btn", _L), type="primary", width="stretch"):
                with st.spinner(t("generating", _L)):
                    cleaned, clean_report = clean_data_with_report(
                        df,
                        date_col=date_col,
                        amount_col=amount_col,
                        product_col=product_col,
                        category_col=category_col,
                    )
                    st.session_state.df_clean = cleaned
                    st.session_state.clean_report = clean_report
                    st.session_state.detected = {
                        "date_col": date_col,
                        "amount_col": amount_col,
                        "product_col": product_col,
                        "category_col": category_col,
                    }
                    st.session_state.file_processed = True
                    # Reset chat when new data is loaded
                    st.session_state.chat_messages = []
                    if st.session_state.agent is not None:
                        st.session_state.agent.reset_chat()
                    st.success(t("dashboard_ready", _L))
    else:
        st.session_state.df_raw = None
        st.session_state.df_clean = None
        st.session_state.file_processed = False
        st.session_state.clean_report = None

    # Sidebar footer
    st.markdown("---")
    st.markdown(
        "<p style='font-size:0.72rem;color:rgba(232,238,249,.38);font-family:'JetBrains Mono',monospace;letter-spacing:.06em;'>"
        "Σ Business Insight Agent<br>"
        "Built with Streamlit • Gemini • Plotly"
        "</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='font-size:0.72rem;color:rgba(232,238,249,.38);font-family:'JetBrains Mono',monospace;letter-spacing:.06em;margin:.5rem 0 0;'>"
        f"<a href='app/static/landing.html' target='_blank' rel='noopener' "
        f"style='color:rgba(232,238,249,.38);text-decoration:none;'>"
        f"{t('back_to_landing', _L)}</a>"
        "</p>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Main area — Empty state or Dashboard
# ---------------------------------------------------------------------------

# --- Empty state ---
if not st.session_state.file_processed or st.session_state.df_clean is None:
    _L = st.session_state.language
    st.markdown(
        f"""
        <div style="
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 6rem 2rem;
        ">
            <div style="
                width: 64px; height: 64px;
                border-radius: 16px;
                display: grid; place-items: center;
                background: linear-gradient(145deg, #13315f, #0b1830);
                border: 1px solid rgba(143,212,255,.28);
                color: #8FD4FF;
                font: 600 1.5rem 'JetBrains Mono', monospace;
                box-shadow: 0 0 24px -6px rgba(143,212,255,.35), inset 0 0 14px -8px rgba(143,212,255,.55);
                margin-bottom: 1.4rem;
            ">Σ</div>
            <p style="
                font: .72rem 'JetBrains Mono', monospace;
                letter-spacing: .3em;
                text-transform: uppercase;
                color: #2F6FED;
                margin-bottom: .8rem;
            ">// {t('empty_eyebrow', _L)}</p>
            <h1 style="font-size: 2.1rem; margin-bottom: 0.5rem; font-family: 'Space Grotesk', sans-serif;">
                {t('empty_title', _L)}
            </h1>
            <p style="font-size: 1.05rem; color: rgba(232,238,249,.64); max-width: 520px; line-height: 1.7; margin-bottom: 2rem;">
                {t('empty_desc', _L)}
            </p>
            <div style="
                background: rgba(11,24,48,.72);
                border: 1px solid rgba(143,212,255,.14);
                padding: 1.1rem 1.8rem;
                border-radius: 14px;
                color: rgba(232,238,249,.64);
                font-size: 0.88rem;
                line-height: 1.9;
            ">
                {t('empty_features', _L)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

df_clean = st.session_state.df_clean
detected = st.session_state.detected
date_col = detected.get("date_col")
amount_col = detected.get("amount_col")
product_col = detected.get("product_col")
category_col = detected.get("category_col")
_L = st.session_state.language

if df_clean is None or df_clean.empty:
    st.warning(t("no_data_warning", _L))
    st.stop()

# ===========================================================================
# Dashboard content
# ===========================================================================

with st.container():
    # --- Data preview banner ---
    preview = get_data_preview(df_clean, date_col=date_col, amount_col=amount_col)

    with st.container():
        st.markdown(
            f"""
            <div style="
                position: relative;
                overflow: hidden;
                background: linear-gradient(135deg, #2F6FED 0%, #1B3A6B 55%, #0B1830 100%);
                border: 1px solid rgba(143,212,255,.22);
                border-radius: 16px;
                padding: 1.6rem 2rem;
                margin-bottom: 1.5rem;
                color: white;
            ">
                <div style="position:absolute;inset:0;pointer-events:none;
                    background: radial-gradient(420px 220px at 88% -10%, rgba(143,212,255,.18), transparent 65%);"></div>
                <div style="position:relative;">
                <h2 style="color: #E8EEF9; margin: 0 0 0.5rem 0; font-size: 1.5rem; font-family: 'Space Grotesk', sans-serif;">
                    📈 {st.session_state.uploaded_filename}
                </h2>
                <p style="margin: 0; opacity: 0.85; font-size: 0.9rem; font-family: 'JetBrains Mono', monospace; color: #8FD4FF;">
                    {preview['row_count']:,} {t('transactions', _L)} ·
                    {f"{preview['date_range'][0].strftime('%d %b %Y')} – {preview['date_range'][1].strftime('%d %b %Y')}" if preview['date_range'] else "Unknown date range"} ·
                    {t('total_sales_label', _L)}: RM {preview['total_sales']:,.2f}
                </p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # -----------------------------------------------------------------------
    # Data-quality banner — tell the user what was dropped / defaulted
    # -----------------------------------------------------------------------

    _clean_report = st.session_state.get("clean_report")
    if _clean_report:
        _reasons = []
        _blank = _clean_report.get("rows_blank_dropped", 0)
        _bad_date = _clean_report.get("rows_date_dropped", 0)
        _bad_amount = _clean_report.get("rows_amount_dropped", 0)
        if _blank > 0:
            _reasons.append(t("data_quality_dropped_blank", _L).format(n=_blank))
        if _bad_date > 0:
            _reasons.append(t("data_quality_dropped_date", _L).format(n=_bad_date))
        if _bad_amount > 0:
            _reasons.append(t("data_quality_dropped_amount", _L).format(n=_bad_amount))
        if _clean_report.get("products_defaulted", 0) > 0:
            _reasons.append(
                t("data_quality_unknown_products", _L).format(
                    n=_clean_report["products_defaulted"]
                )
            )
        if _clean_report.get("date_parse_failed"):
            _reasons.append(t("data_quality_date_failed", _L))

        if _reasons:
            st.warning(
                f"**{t('data_quality_rows_used', _L).format(used=_clean_report['rows_used'], source=_clean_report['rows_source'])}** — "
                + " · ".join(_reasons)
            )

    # -----------------------------------------------------------------------
    # Filters — filter dashboard by actual data values
    # -----------------------------------------------------------------------

    st.markdown(f"### 🔍 {t('filter_title', _L)}")

    fcol1, fcol2, fcol3, fcol4 = st.columns(4)

    # --- Year / Month filter ---
    with fcol1:
        if date_col and date_col in df_clean.columns and pd.api.types.is_datetime64_any_dtype(df_clean[date_col]):
            year_options = sorted(df_clean[date_col].dt.year.unique(), reverse=True)
            filter_year = st.selectbox(
                t("filter_year_label", _L),
                options=["All"] + [str(y) for y in year_options],
                key="filter_year",
            )
            month_names = df_clean[date_col].dt.strftime("%B").unique()
            _month_index = {m: i for i, m in enumerate(calendar.month_name)}
            month_options = sorted(
                month_names,
                key=lambda m: _month_index.get(m, 99),
            )
            filter_month = st.selectbox(
                t("filter_month_label", _L),
                options=["All"] + month_options,
                key="filter_month",
            )
        else:
            filter_year = "All"
            filter_month = "All"
            st.selectbox(t("filter_year_label", _L), options=["All"], disabled=True, key="filter_year_d")
            st.selectbox(t("filter_month_label", _L), options=["All"], disabled=True, key="filter_month_d")

    # --- Product filter ---
    with fcol2:
        if product_col and product_col in df_clean.columns:
            product_options = sorted(df_clean[product_col].astype(str).unique())
            filter_product = st.selectbox(
                t("filter_product_label", _L),
                options=["All"] + product_options,
                key="filter_product",
            )
        else:
            filter_product = "All"
            st.selectbox(t("filter_product_label", _L), options=["All"], disabled=True, key="filter_product_d")

    # --- Category filter ---
    with fcol3:
        if category_col and category_col in df_clean.columns:
            cat_options = sorted(df_clean[category_col].astype(str).unique())
            filter_category = st.selectbox(
                t("filter_category_label", _L),
                options=["All"] + cat_options,
                key="filter_category",
            )
        else:
            filter_category = "All"
            st.selectbox(t("filter_category_label", _L), options=["All"], disabled=True, key="filter_category_d")

    # --- Amount range filter ---
    with fcol4:
        if amount_col and amount_col in df_clean.columns:
            min_amt = float(df_clean[amount_col].min())
            max_amt = float(df_clean[amount_col].max())
            if max_amt > min_amt:
                filter_amt_range = st.slider(
                    t("filter_amount_label", _L),
                    min_value=0.0,
                    max_value=float(max_amt),
                    value=(float(min_amt), float(max_amt)),
                    step=10.0,
                    key="filter_amount",
                )
            else:
                filter_amt_range = (min_amt, max_amt)
                st.slider(t("filter_amount_label", _L), disabled=True, key="filter_amount_d")
        else:
            filter_amt_range = (0.0, 0.0)
            st.slider(t("filter_amount_label", _L), disabled=True, key="filter_amount_d")

    # --- Apply filters ---
    df_filtered = df_clean.copy()

    if filter_year != "All" and date_col and date_col in df_clean.columns:
        df_filtered = df_filtered[df_filtered[date_col].dt.year == int(filter_year)]

    if filter_month != "All" and date_col and date_col in df_clean.columns:
        df_filtered = df_filtered[df_filtered[date_col].dt.strftime("%B") == filter_month]

    if filter_product != "All" and product_col and product_col in df_clean.columns:
        df_filtered = df_filtered[df_filtered[product_col].astype(str) == filter_product]

    if filter_category != "All" and category_col and category_col in df_clean.columns:
        df_filtered = df_filtered[df_filtered[category_col].astype(str) == filter_category]

    if amount_col and amount_col in df_clean.columns:
        lo, hi = filter_amt_range
        df_filtered = df_filtered[(df_filtered[amount_col] >= lo) & (df_filtered[amount_col] <= hi)]

    # --- Filter status badge ---
    if len(df_filtered) < len(df_clean):
        st.markdown(
            f"<div style='text-align:right;font-size:0.72rem;color:rgba(232,238,249,.5);font-family:'JetBrains Mono',monospace;padding:0 0 8px 0;'>"
            f"📊 {t('filter_showing', _L)} {len(df_filtered):,} / {len(df_clean):,} {t('transactions', _L)}"
            f"</div>",
            unsafe_allow_html=True,
        )

    # --- PDF export (respects active filters) ---
    filter_desc = ""
    if filter_year != "All":
        filter_desc += f"{t('pdf_f_year', _L)}: {filter_year}; "
    if filter_month != "All":
        filter_desc += f"{t('pdf_f_month', _L)}: {filter_month}; "
    if filter_product != "All":
        filter_desc += f"{t('pdf_f_product', _L)}: {filter_product}; "
    if filter_category != "All":
        filter_desc += f"{t('pdf_f_category', _L)}: {filter_category}; "
    if amount_col and amount_col in df_clean.columns:
        lo, hi = filter_amt_range
        if lo > float(df_clean[amount_col].min()) or hi < float(df_clean[amount_col].max()):
            filter_desc += f"{t('pdf_f_amount', _L)}: RM {lo:,.0f} – {hi:,.0f}; "
    filter_desc = filter_desc.rstrip("; ")

    _pdf_bytes = _build_pdf_cached(
        df_filtered,
        st.session_state.detected,
        st.session_state.uploaded_filename or "report",
        _L,
        filter_desc,
        st.session_state.pdf_insights_text,
    )
    # Include the uploaded file's name in the downloaded PDF name (no underscores)
    _base_name = os.path.splitext(st.session_state.uploaded_filename or "report")[0]
    _safe_name = re.sub(r"[^A-Za-z0-9]+", "-", _base_name).strip("-") or "report"
    st.download_button(
        t("pdf_btn", _L),
        data=_pdf_bytes,
        file_name=f"sigma-report-{_safe_name}-{datetime.now():%Y%m%d-%H%M}.pdf",
        mime="application/pdf",
        type="primary",
        width="stretch",
    )

    # --- KPI cards (bilingual) ---
    render_kpi_cards(df_filtered, amount_col=amount_col, date_col=date_col, lang=_L)

    st.markdown("---")

    # --- Charts in a two-column layout ---
    col_left, col_right = st.columns(2, gap="large")

    with col_left:
        render_sales_trend(df_filtered, date_col=date_col, amount_col=amount_col, lang=_L)

    with col_right:
        render_top_products(df_filtered, product_col=product_col, amount_col=amount_col, lang=_L)

    # Category breakdown (full width if available)
    render_category_breakdown(df_filtered, category_col=category_col, amount_col=amount_col, lang=_L)

    # --- Raw data expander ---
    with st.expander(t("raw_data", _L)):
        st.dataframe(
            df_filtered.head(100),
            width="stretch",
            hide_index=True,
        )

# ---------------------------------------------------------------------------
# Ask the AI Agent (full-width, below the dashboard)
# ---------------------------------------------------------------------------

st.markdown("---")
st.markdown(
    f"""
    <div style="margin-bottom: 1rem;">
        <p style="font:.72rem 'JetBrains Mono',monospace;letter-spacing:.3em;text-transform:uppercase;color:#2F6FED;margin:0 0 .4rem 0;">// Ask</p>
        <h3 style="margin-bottom: 0.25rem;">{t('chat_title', _L)}</h3>
        <p style="color: rgba(232,238,249,.64); font-size: 0.9rem; margin: 0;">
            {t('chat_desc', _L)}
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Check prerequisites for chat
agent_ready = (
    st.session_state.agent_initialized
    and st.session_state.agent is not None
    and st.session_state.df_clean is not None
)

if not agent_ready:
    if not st.session_state.agent_initialized:
        st.info(t("chat_no_api_key", _L))
    elif st.session_state.df_clean is None:
        st.info(t("chat_no_data", _L))
else:
    # --- Display chat history ---
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # --- Chat input ---
    if prompt := st.chat_input(placeholder=t("chat_input_placeholder", _L)):
        # Add user message to display
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Show a welcome message on first interaction
        with st.chat_message("assistant"):
            with st.status(t("chat_thinking", _L), expanded=True) as status:
                try:
                    response_text = st.session_state.agent.process_message(
                        user_message=prompt,
                        df=st.session_state.df_clean,
                        detected=st.session_state.detected,
                    )
                    status.update(label="✅ Done!", state="complete", expanded=False)
                except Exception as e:
                    response_text = f"{t('chat_error', _L)}\n\n{str(e)}"
                    status.update(label="❌ Error", state="error", expanded=False)

            st.markdown(response_text)

        st.session_state.chat_messages.append({"role": "assistant", "content": response_text})
        st.session_state.pdf_insights_text = response_text

    # If no messages yet, show a welcome prompt + quick insights button
    if not st.session_state.chat_messages:
        st.markdown(
            f"<div style='text-align:center;padding:2rem 2rem 1rem 2rem;color:rgba(232,238,249,.64);'>"
            f"<p style='font-size:1.05rem;line-height:1.7;'>{t('chat_welcome', _L)}</p>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # Quick Insights button — runs all 4 tools directly (no Gemini call)
        col_a, col_b, col_c = st.columns([1, 2, 1])
        with col_b:
            if st.button(
                t("quick_insights_btn", _L),
                type="primary",
                width="stretch",
                help=t("quick_insights_btn_hint", _L),
            ):
                with st.chat_message("assistant"):
                    with st.status(t("quick_insights_running", _L), expanded=True) as status:
                        report = _run_quick_insights(
                            st.session_state.df_clean,
                            st.session_state.detected,
                            _L,
                        )
                        status.update(
                            label=t("quick_insights_ready", _L),
                            state="complete",
                            expanded=False,
                        )
                    st.markdown(report)

                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": report,
                })
                st.session_state.pdf_insights_text = report

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown("---")
st.markdown(
    f"<p style='text-align:center;font-size:0.72rem;color:rgba(232,238,249,.38);font-family:'JetBrains Mono',monospace;letter-spacing:.08em;'>"
    f"<strong>{t('footer', _L)}</strong></p>",
    unsafe_allow_html=True,
)
