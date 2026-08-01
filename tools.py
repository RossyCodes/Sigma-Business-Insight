"""
tools.py — Agent tool functions that the AI chat assistant can call.

Each function receives the cleaned DataFrame plus detected column names and
returns structured data (dicts / lists) that the Gemini agent will convert
into natural-language responses.  All functions handle missing columns and
empty data gracefully.
"""

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Tool 1: get_sales_summary
# ---------------------------------------------------------------------------

def get_sales_summary(
    df: pd.DataFrame,
    amount_col: Optional[str] = None,
    date_col: Optional[str] = None,
) -> dict:
    """Return overall sales statistics for the loaded dataset."""
    if df is None or df.empty:
        return {"error": "No data available."}

    result = {"total_sales": 0.0, "transaction_count": 0, "avg_order_value": 0.0}

    result["transaction_count"] = len(df)

    if amount_col and amount_col in df.columns:
        result["total_sales"] = round(float(df[amount_col].sum()), 2)
        result["avg_order_value"] = round(float(df[amount_col].mean()), 2)

    if date_col and date_col in df.columns and pd.api.types.is_datetime64_any_dtype(df[date_col]):
        result["start_date"] = df[date_col].min().strftime("%d %b %Y")
        result["end_date"] = df[date_col].max().strftime("%d %b %Y")
        result["date_range_days"] = (df[date_col].max() - df[date_col].min()).days + 1
    else:
        result["start_date"] = "Unknown"
        result["end_date"] = "Unknown"
        result["date_range_days"] = 0

    return result


# ---------------------------------------------------------------------------
# Tool 2: get_top_products
# ---------------------------------------------------------------------------

def get_top_products(
    df: pd.DataFrame,
    product_col: Optional[str] = None,
    amount_col: Optional[str] = None,
    n: int = 10,
) -> list:
    """Return the top N products/items by total sales.

    Returns a list of dicts with keys: product, total_sales, percentage, quantity.
    If sales data is available but no product column, returns an informative error.
    """
    if df is None or df.empty:
        return [{"error": "No data available."}]

    if not product_col or product_col not in df.columns:
        return [{"error": "Product/Item column not found in the dataset."}]

    if not amount_col or amount_col not in df.columns:
        return [{"error": "Sales/Amount column not found in the dataset."}]

    total = float(df[amount_col].sum())
    grouped = df.groupby(product_col, as_index=False)[amount_col].sum()
    grouped = grouped.sort_values(amount_col, ascending=False).head(n)

    products = []
    for _, row in grouped.iterrows():
        p_total = float(row[amount_col])
        pct = round((p_total / total * 100), 1) if total > 0 else 0.0
        products.append({
            "product": str(row[product_col]),
            "total_sales": round(p_total, 2),
            "percentage": pct,
        })

    return products if products else [{"info": "No product data available."}]


# ---------------------------------------------------------------------------
# Tool 3: compare_periods
# ---------------------------------------------------------------------------

def compare_periods(
    df: pd.DataFrame,
    date_col: Optional[str] = None,
    amount_col: Optional[str] = None,
    period_a_start: str = "",
    period_a_end: str = "",
    period_b_start: str = "",
    period_b_end: str = "",
) -> dict:
    """Compare sales between two date periods.

    Each period is defined by start_date and end_date (inclusive).  Date strings
    should be in YYYY-MM-DD format.  Returns sales, transaction count, and
    average for each period plus the percentage change.
    """
    if df is None or df.empty:
        return {"error": "No data available to compare."}

    if not date_col or date_col not in df.columns:
        return {"error": "Date column not found or not parsed."}

    if not amount_col or amount_col not in df.columns:
        return {"error": "Amount column not found."}

    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        return {"error": "Date column could not be parsed as dates."}

    # --- Parse period dates ---
    def _parse_date(d: str):
        """Try parsing YYYY-MM-DD, then DD/MM/YYYY, then fallback."""
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(d.strip(), fmt)
            except (ValueError, AttributeError):
                continue
        return None

    start_a = _parse_date(period_a_start)
    end_a = _parse_date(period_a_end)
    start_b = _parse_date(period_b_start)
    end_b = _parse_date(period_b_end)

    # Handle missing dates gracefully
    date_col_series = df[date_col]

    if start_a is None or end_a is None:
        return {"error": f"Could not understand period A dates: '{period_a_start}' – '{period_a_end}'. Please use YYYY-MM-DD format."}
    if start_b is None or end_b is None:
        return {"error": f"Could not understand period B dates: '{period_b_start}' – '{period_b_end}'. Please use YYYY-MM-DD format."}

    # Ensure end_dates are inclusive (add one day for filtering)
    end_a_adj = end_a + timedelta(days=1)
    end_b_adj = end_b + timedelta(days=1)

    mask_a = (date_col_series >= start_a) & (date_col_series < end_a_adj)
    mask_b = (date_col_series >= start_b) & (date_col_series < end_b_adj)

    period_a_df = df[mask_a]
    period_b_df = df[mask_b]

    def _stats(sub_df):
        return {
            "sales": round(float(sub_df[amount_col].sum()), 2),
            "transactions": len(sub_df),
            "avg_order": round(float(sub_df[amount_col].mean()), 2) if len(sub_df) > 0 else 0.0,
            "days": (sub_df[date_col].max() - sub_df[date_col].min()).days + 1 if len(sub_df) > 0 else 0,
        }

    stats_a = _stats(period_a_df)
    stats_b = _stats(period_b_df)

    # Percentage change (A -> B)
    if stats_a["sales"] > 0:
        pct_change = round(((stats_b["sales"] - stats_a["sales"]) / stats_a["sales"]) * 100, 1)
    else:
        pct_change = 0.0 if stats_b["sales"] == 0 else 100.0

    # Determine direction
    if pct_change > 0:
        direction = "increased"
    elif pct_change < 0:
        direction = "decreased"
    else:
        direction = "unchanged"

    # Graceful messaging for empty periods
    if stats_a["transactions"] == 0 and stats_b["transactions"] == 0:
        return {"info": "No data found for either period. The available data spans a different date range."}
    if stats_a["transactions"] == 0:
        return {"info": f"No data found for Period A ({period_a_start} to {period_a_end}).", "period_b": stats_b}
    if stats_b["transactions"] == 0:
        return {"info": f"No data found for Period B ({period_b_start} to {period_b_end}).", "period_a": stats_a}

    return {
        "period_a": {
            "label": f"{period_a_start} to {period_a_end}",
            **stats_a,
        },
        "period_b": {
            "label": f"{period_b_start} to {period_b_end}",
            **stats_b,
        },
        "change": {
            "sales_difference": round(stats_b["sales"] - stats_a["sales"], 2),
            "percentage_change": pct_change,
            "direction": direction,
        },
    }


# ---------------------------------------------------------------------------
# Tool 4: generate_insight
# ---------------------------------------------------------------------------

def generate_insight(
    df: pd.DataFrame,
    amount_col: Optional[str] = None,
    date_col: Optional[str] = None,
    product_col: Optional[str] = None,
    category_col: Optional[str] = None,
) -> dict:
    """Analyse the data and return structured business insights and
    recommendations based on actual data patterns.  No hallucinated numbers."""
    if df is None or df.empty:
        return {"error": "No data available for analysis."}

    insight = {
        "overview": {},
        "trend": {},
        "top_products": [],
        "category_performance": [],
        "recommendations": [],
    }

    # --- Overview ---
    if amount_col and amount_col in df.columns:
        total = float(df[amount_col].sum())
        count = len(df)
        avg_order = float(df[amount_col].mean())
        insight["overview"] = {
            "total_sales": round(total, 2),
            "transaction_count": count,
            "avg_order_value": round(avg_order, 2),
        }

    # --- Trend direction ---
    if date_col and date_col in df.columns and amount_col and amount_col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[date_col]):
            daily = df.groupby(df[date_col].dt.date)[amount_col].sum().sort_index()
            if len(daily) >= 3:
                first_half = daily.iloc[: len(daily) // 2].mean()
                second_half = daily.iloc[len(daily) // 2 :].mean()
                if second_half > first_half * 1.05:
                    trend = "increasing"
                    trend_detail = "Sales show an upward trend over the period."
                elif second_half < first_half * 0.95:
                    trend = "decreasing"
                    trend_detail = "Sales show a downward trend over the period."
                else:
                    trend = "stable"
                    trend_detail = "Sales have been relatively stable throughout the period."
                insight["trend"] = {
                    "direction": trend,
                    "detail": trend_detail,
                    "daily_avg_first_half": round(float(first_half), 2),
                    "daily_avg_second_half": round(float(second_half), 2),
                }

    # --- Top products (top 5) ---
    if product_col and product_col in df.columns and amount_col and amount_col in df.columns:
        total = float(df[amount_col].sum())
        top = df.groupby(product_col, as_index=False)[amount_col].sum()
        top = top.sort_values(amount_col, ascending=False).head(5)
        for _, row in top.iterrows():
            p_total = float(row[amount_col])
            insight["top_products"].append({
                "product": str(row[product_col]),
                "sales": round(p_total, 2),
                "share": round((p_total / total * 100), 1) if total > 0 else 0,
            })

    # --- Category breakdown ---
    if category_col and category_col in df.columns and amount_col and amount_col in df.columns:
        cats = df.groupby(category_col, as_index=False)[amount_col].sum()
        cats = cats.sort_values(amount_col, ascending=False)
        total = float(df[amount_col].sum())
        for _, row in cats.iterrows():
            c_total = float(row[amount_col])
            insight["category_performance"].append({
                "category": str(row[category_col]),
                "sales": round(c_total, 2),
                "share": round((c_total / total * 100), 1) if total > 0 else 0,
            })

    # --- Generate recommendations based on data ---
    recs = []

    # Check if top product dominates
    if insight["top_products"]:
        top_share = insight["top_products"][0]["share"]
        if top_share > 40:
            recs.append(
                f"Your top product, '{insight['top_products'][0]['product']}', represents "
                f"{top_share}% of all sales. Consider diversifying your menu or running "
                f"bundled offers to spread risk."
            )
        elif top_share < 15 and len(insight["top_products"]) >= 3:
            recs.append(
                "Your sales are well-distributed across products — this is healthy. "
                "Consider promoting your best-sellers more visibly to boost overall revenue."
            )

    # Trend-based recommendations
    if insight["trend"]:
        if insight["trend"]["direction"] == "increasing":
            recs.append(
                "Sales are trending upward! Great momentum. Consider stocking up on "
                "popular items and reviewing staffing levels to handle growing demand."
            )
        elif insight["trend"]["direction"] == "decreasing":
            recs.append(
                "Sales are trending downward. This may be seasonal. Consider reviewing "
                "your pricing, running a promotion, or introducing new menu items to "
                "attract customers back."
            )
        elif insight["trend"]["direction"] == "stable":
            recs.append(
                "Sales are stable — a solid foundation. Try introducing small promotions "
                "or loyalty programmes to nudge growth without taking big risks."
            )

    # Category-based recommendations
    if len(insight["category_performance"]) >= 2:
        top_cat = insight["category_performance"][0]
        recs.append(
            f"'{top_cat['category']}' leads at {top_cat['share']}% of sales. "
            f"Consider cross-promoting lower-performing categories alongside it."
        )

    # General recommendation
    recs.append(
        "Regularly track your daily sales against the same day last week to spot "
        "patterns early. Even 15 minutes a day on your numbers can make a big difference."
    )

    insight["recommendations"] = recs
    return insight
