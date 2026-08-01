"""
dashboard_utils.py — Dashboard display logic (KPI cards, charts, breakdowns).

All functions here are pure display helpers that receive a cleaned DataFrame
and render Streamlit/Plotly elements.  They do not handle file I/O or
data transformation — that belongs in data_utils.py.

Now includes bilingual (EN/BM) label support via the ``lang`` parameter.

Styled to match the Sigma landing page design language:
void/ink dark palette, Space Grotesk / Inter / JetBrains Mono type,
glassy cards and a layered-blue chart theme.
"""

from typing import Optional

import pandas as pd
import plotly.express as px
import streamlit as st

from translations import t


# ---------------------------------------------------------------------------
# Shared styling helpers (Sigma design tokens)
# ---------------------------------------------------------------------------

_CHART_TEMPLATE = "plotly_dark"
_COLOR_SIGNAL = "#2F6FED"  # primary blue
_COLOR_ICE = "#8FD4FF"     # light blue accent
_COLOR_INK = "#0B1830"
_FONT_DISPLAY = "Space Grotesk, system-ui, sans-serif"
_FONT_BODY = "Inter, system-ui, sans-serif"
_FONT_MONO = "'JetBrains Mono', ui-monospace, monospace"


def _apply_sigma_theme(fig) -> None:
    """Apply the Sigma layered-blue dark theme to a Plotly figure."""
    fig.update_layout(
        template=_CHART_TEMPLATE,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=_FONT_BODY, color="rgba(232,238,249,.72)", size=12),
        title_font=dict(family=_FONT_DISPLAY, color="#E8EEF9", size=16),
        title_x=0,
        xaxis=dict(
            gridcolor="rgba(143,212,255,.10)",
            zeroline=False,
            linecolor="rgba(143,212,255,.22)",
            tickfont=dict(family=_FONT_MONO, color="rgba(232,238,249,.5)", size=11),
        ),
        yaxis=dict(
            gridcolor="rgba(143,212,255,.10)",
            zeroline=False,
            linecolor="rgba(143,212,255,.22)",
            tickfont=dict(family=_FONT_MONO, color="rgba(232,238,249,.5)", size=11),
        ),
        hoverlabel=dict(
            bgcolor=_COLOR_INK,
            bordercolor="rgba(143,212,255,.4)",
            font=dict(family=_FONT_BODY, color="#E8EEF9"),
        ),
        legend=dict(font=dict(family=_FONT_BODY, color="rgba(232,238,249,.72)")),
        margin=dict(l=20, r=20, t=55, b=20),
    )


# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------


def render_kpi_cards(
    df: pd.DataFrame,
    amount_col: Optional[str] = None,
    date_col: Optional[str] = None,
    lang: str = "en",
) -> None:
    """Render 4 KPI metric cards in a row with bilingual labels.

    Cards follow the landing page's ``clean-kpi`` tile look: mono uppercase
    labels in faint, values in ice blue on a glassy ink panel.
    """
    total_sales = df[amount_col].sum() if amount_col and amount_col in df.columns else 0
    total_transactions = len(df)
    avg_order = df[amount_col].mean() if amount_col and amount_col in df.columns else 0

    # Best-selling day
    best_day_str = "—"
    if date_col and date_col in df.columns and amount_col and amount_col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[date_col]):
            daily_sales = df.groupby(df[date_col].dt.day_name())[amount_col].sum()
            if not daily_sales.empty:
                best_day = daily_sales.idxmax()
                best_day_str = best_day

    kpis = [
        (t("total_sales", lang), f"RM {total_sales:,.2f}"),
        (t("transactions_kpi", lang), f"{total_transactions:,}"),
        (t("avg_order_value", lang), f"RM {avg_order:,.2f}"),
        (t("best_day", lang), best_day_str),
    ]

    cols = st.columns(4, gap="medium")
    for i, (label, value) in enumerate(kpis):
        with cols[i]:
            st.markdown(
                f"""
                <div class="sigma-kpi" style="
                    background: rgba(11,24,48,.88);
                    border-radius: 14px;
                    padding: 20px 16px;
                    box-shadow: 0 14px 34px -14px rgba(0,0,0,.7);
                    border: 1px solid rgba(143,212,255,.14);
                    text-align: center;
                    height: 100%;
                    transition: border-color .3s ease, background .3s ease, transform .2s ease;
                ">
                    <p style="
                        font-family: {_FONT_MONO};
                        font-size: 0.62rem;
                        color: rgba(232,238,249,.38);
                        margin: 0 0 10px 0;
                        font-weight: 500;
                        text-transform: uppercase;
                        letter-spacing: 0.22em;
                        white-space: nowrap;
                    ">{label}</p>
                    <p style="
                        font-family: {_FONT_MONO};
                        font-size: 1.4rem;
                        font-weight: 600;
                        color: {_COLOR_ICE};
                        margin: 0;
                        white-space: nowrap;
                    ">{value}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Sales trend line chart
# ---------------------------------------------------------------------------


def render_sales_trend(
    df: pd.DataFrame,
    date_col: Optional[str] = None,
    amount_col: Optional[str] = None,
    lang: str = "en",
) -> None:
    """Interactive line chart of sales over time with bilingual labels."""
    if not date_col or not amount_col:
        st.info(t("trend_no_data", lang))
        return
    if date_col not in df.columns or amount_col not in df.columns:
        st.info(t("trend_col_missing", lang))
        return
    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        st.info(t("trend_no_parse", lang))
        return

    trend = df.groupby(df[date_col].dt.date, as_index=False)[amount_col].sum()
    trend = trend.sort_values(date_col)

    fig = px.line(
        trend,
        x=date_col,
        y=amount_col,
        title=t("sales_trend_title", lang),
        markers=True,
        color_discrete_sequence=[_COLOR_SIGNAL],
    )
    fig.update_traces(
        line=dict(width=2.5, color=_COLOR_SIGNAL),
        marker=dict(size=6, color=_COLOR_ICE, line=dict(width=1, color=_COLOR_INK)),
    )
    fig.update_layout(
        xaxis_title=t("sales_trend_x", lang),
        yaxis_title=t("sales_trend_y", lang),
        hovermode="x unified",
        height=400,
    )
    _apply_sigma_theme(fig)
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Top products bar chart
# ---------------------------------------------------------------------------


def render_top_products(
    df: pd.DataFrame,
    product_col: Optional[str] = None,
    amount_col: Optional[str] = None,
    top_n: int = 10,
    lang: str = "en",
) -> None:
    """Horizontal bar chart of top N products/items by sales with bilingual labels."""
    if not product_col or not amount_col:
        st.info(t("products_no_col", lang))
        return
    if product_col not in df.columns or amount_col not in df.columns:
        return

    product_sales = df.groupby(product_col, as_index=False)[amount_col].sum()
    product_sales = product_sales.sort_values(amount_col, ascending=False).head(top_n)

    if product_sales.empty:
        st.info(t("products_no_data", lang))
        return

    fig = px.bar(
        product_sales,
        x=amount_col,
        y=product_col,
        orientation="h",
        title=t("top_products_title", lang).replace("{n}", str(top_n)),
        color_discrete_sequence=[_COLOR_SIGNAL],
        text=product_sales[amount_col].apply(lambda v: f"RM {v:,.0f}"),
    )
    fig.update_layout(
        xaxis_title=t("top_products_x", lang),
        yaxis_title="",
        hovermode="y unified",
        height=400,
        yaxis=dict(categoryorder="total ascending"),
    )
    fig.update_traces(
        textposition="outside",
        marker=dict(line=dict(width=0)),
        textfont=dict(family=_FONT_MONO, color="rgba(232,238,249,.8)", size=10),
    )
    _apply_sigma_theme(fig)
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Category breakdown (optional)
# ---------------------------------------------------------------------------


def render_category_breakdown(
    df: pd.DataFrame,
    category_col: Optional[str] = None,
    amount_col: Optional[str] = None,
    lang: str = "en",
) -> None:
    """Pie or donut chart showing sales breakdown by category/segment with bilingual labels."""
    if not category_col or not amount_col:
        return
    if category_col not in df.columns or amount_col not in df.columns:
        return

    cat_sales = df.groupby(category_col, as_index=False)[amount_col].sum()
    cat_sales = cat_sales.sort_values(amount_col, ascending=False)

    if cat_sales.empty or len(cat_sales) < 2:
        return

    fig = px.pie(
        cat_sales,
        values=amount_col,
        names=category_col,
        title=t("category_title", lang),
        hole=0.4,
        color_discrete_sequence=[
            _COLOR_SIGNAL,
            _COLOR_ICE,
            "#1B3A6B",
            "#4A8BF5",
            "#5EA8FF",
            "#2457C4",
            "#8FB8F0",
        ],
    )
    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        textfont=dict(family=_FONT_BODY, color="#E8EEF9", size=11),
        marker=dict(line=dict(color=_COLOR_INK, width=2)),
        hovertemplate="%{label}<br>RM %{value:,.2f} · %{percent:.1%}<extra></extra>",
    )
    fig.update_layout(
        height=400,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.18,
            xanchor="center",
            x=0.5,
            font=dict(family=_FONT_BODY, color="rgba(232,238,249,.72)", size=11),
        ),
    )
    _apply_sigma_theme(fig)
    st.plotly_chart(fig, use_container_width=True)
