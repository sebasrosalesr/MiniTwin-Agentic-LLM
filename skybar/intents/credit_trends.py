import re
import pandas as pd

from skybar.utils.df_cleaning import coerce_date
from skybar.utils.formatting import format_money


def intent_credit_trends(query: str, df: pd.DataFrame) -> str | None:
    """
    Handle queries like:
      - "Are there any trends in credits worth sharing?"
      - "What trends do you see in credits?"
      - "Any recent credit patterns?"

    Compares last 30 days vs previous 30 days:
      - volume (rows)
      - total dollars
      - top customers
      - top items
      - top sales reps
    """

    q_low = query.lower()

    if not (
        "trend" in q_low
        or "pattern" in q_low
        or "insight" in q_low
        or "what's happening" in q_low
        or "whats happening" in q_low
    ):
        return None

    if "credit" not in q_low and "ticket" not in q_low:
        # Let other intents handle non-credit questions
        return None

    if "Date" not in df.columns:
        return "I can't analyze credit trends because the `Date` column is missing."

    dv = df.copy()
    dv["Date"] = coerce_date(dv["Date"])
    dv = dv.dropna(subset=["Date"])

    if dv.empty:
        return "I don't have enough dated records to analyze trends."

    # Last 60 days split into 2 windows of 30
    latest = dv["Date"].max().normalize()
    cutoff_30 = latest - pd.Timedelta(days=30)
    cutoff_prev = cutoff_30 - pd.Timedelta(days=30)

    last_30 = dv[dv["Date"].between(cutoff_30, latest)].copy()
    prev_30 = dv[dv["Date"].between(cutoff_prev, cutoff_30 - pd.Timedelta(days=1))].copy()

    if last_30.empty or prev_30.empty:
        return (
            "I don't have enough data in the last 60 days to compare "
            "the last 30 days vs the previous 30."
        )

    # Numeric credit total
    if "Credit Request Total" in dv.columns:
        dv["Credit Request Total"] = pd.to_numeric(
            dv["Credit Request Total"], errors="coerce"
        ).fillna(0.0)
        last_30["Credit Request Total"] = dv.loc[last_30.index, "Credit Request Total"]
        prev_30["Credit Request Total"] = dv.loc[prev_30.index, "Credit Request Total"]
    else:
        last_30["Credit Request Total"] = 0.0
        prev_30["Credit Request Total"] = 0.0

    # ---------- Volume & dollars ----------
    n_last = len(last_30)
    n_prev = len(prev_30)
    diff_n = n_last - n_prev
    pct_n = (diff_n / max(n_prev, 1)) * 100

    amt_last = last_30["Credit Request Total"].sum()
    amt_prev = prev_30["Credit Request Total"].sum()
    diff_amt = amt_last - amt_prev
    pct_amt = (diff_amt / max(amt_prev, 1)) * 100

    # ---------- Top customers (last 30) ----------
    if "Customer Number" in last_30.columns:
        top_cust = (
            last_30.groupby("Customer Number", dropna=False)["Credit Request Total"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )
    else:
        top_cust = pd.Series(dtype=float)

    # ---------- Top items (last 30) ----------
    if "Item Number" in last_30.columns:
        top_items = (
            last_30.groupby("Item Number", dropna=False)["Credit Request Total"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )
    else:
        top_items = pd.Series(dtype=float)

    # ---------- Top sales reps (last 30) ----------
    if "Sales Rep" in last_30.columns:
        top_reps = (
            last_30.groupby("Sales Rep", dropna=False)["Credit Request Total"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )
    else:
        top_reps = pd.Series(dtype=float)

    # ---------- Build answer ----------
    lines: list[str] = []

    lines.append("📊 **Credit Trends – Last 30 vs Previous 30 Days**")
    lines.append(
        f"- Previous 30 days: **{cutoff_prev.date()} → {(cutoff_30 - pd.Timedelta(days=1)).date()}**"
    )
    lines.append(
        f"- Last 30 days: **{cutoff_30.date()} → {latest.date()}**"
    )
    lines.append("")

    # Volume
    lines.append(
        f"📈 **Volume:** {n_last} rows vs {n_prev} rows "
        f"(Δ {diff_n:+}, {pct_n:+.1f}% change)."
    )

    # Dollars
    lines.append(
        f"💲 **Total credits:** {format_money(amt_last)} vs {format_money(amt_prev)} "
        f"(Δ {format_money(diff_amt)}, {pct_amt:+.1f}% change)."
    )
    lines.append("")

    # Top customers
    if not top_cust.empty:
        lines.append("🏷️ **Top customers in the last 30 days:**")
        for cust, val in top_cust.items():
            label = cust if pd.notna(cust) else "UNKNOWN"
            lines.append(f"- {label}: {format_money(val)} in credits")
        lines.append("")

    # Top items
    if not top_items.empty:
        lines.append("📦 **Top items in the last 30 days:**")
        for item, val in top_items.items():
            label = item if pd.notna(item) else "UNKNOWN"
            lines.append(f"- Item {label}: {format_money(val)} in credits")
        lines.append("")

    # Top sales reps
    if not top_reps.empty:
        lines.append("🧑‍💼 **Top sales reps in the last 30 days:**")
        for rep, val in top_reps.items():
            label = rep if pd.notna(rep) else "UNKNOWN"
            lines.append(f"- {label}: {format_money(val)} in credits")
        lines.append("")

    lines.append(
        "📝 **Summary:** This view is meant as a conversation starter for leadership – "
        "volume, dollars, and who/what (customers, items, and sales reps) "
        "is driving the most credits."
    )

    return "\n".join(lines)
