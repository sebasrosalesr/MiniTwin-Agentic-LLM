import re
import pandas as pd

from skybar.utils.df_cleaning import coerce_date
from skybar.utils.formatting import format_money


def intent_credit_anomalies(query: str, df: pd.DataFrame) -> str | None:
    """
    Handle queries like:
      - "Any anomalies in credits?"
      - "MiniTwin, show unusual credits"
      - "Are there suspicious credit amounts lately?"

    MVP logic:
      - Look at last 90 days
      - Use Credit Request Total (numeric)
      - Compute z-score
      - Flag rows with abs(z) >= 3 and amount >= $500
    """

    q_low = query.lower()

    # Trigger words
    if not (
        "anomal" in q_low
        or "unusual" in q_low
        or "suspicious" in q_low
        or "outlier" in q_low
        or "weird" in q_low
    ):
        return None

    if "credit" not in q_low and "ticket" not in q_low:
        # Let other intents try if it's not clearly about credits
        return None

    # Required columns
    if "Date" not in df.columns or "Credit Request Total" not in df.columns:
        return (
            "I can't run anomaly detection because I need both `Date` and "
            "`Credit Request Total` columns."
        )

    dv = df.copy()
    dv["Date"] = coerce_date(dv["Date"])
    dv = dv.dropna(subset=["Date"])

    if dv.empty:
        return "I don't have any dated records to run anomaly detection."

    # Last 90 days window
    latest = dv["Date"].max().normalize()
    cutoff = latest - pd.Timedelta(days=90)
    recent = dv[dv["Date"].between(cutoff, latest)].copy()

    if recent.empty:
        return "There are no credit records in the last 90 days to analyze."

    # Numeric credits
    recent["Credit Request Total"] = pd.to_numeric(
        recent["Credit Request Total"], errors="coerce"
    ).fillna(0.0)

    if recent["Credit Request Total"].std() == 0:
        return "All recent credits are roughly the same size – no clear anomalies."

    # z-score
    mu = recent["Credit Request Total"].mean()
    sigma = recent["Credit Request Total"].std()
    recent["z_score"] = (recent["Credit Request Total"] - mu) / sigma

    # Anomaly rule: big & statistically unusual
    amount_threshold = 500.0  # configurable
    z_threshold = 3.0

    anomalies = recent[
        (recent["Credit Request Total"].abs() >= amount_threshold)
        & (recent["z_score"].abs() >= z_threshold)
    ].copy()

    if anomalies.empty:
        return (
            f"I don't see any large, statistically unusual credits in the last 90 days "
            f"(amount ≥ {format_money(amount_threshold)}, |z| ≥ {z_threshold})."
        )

    total_anom = len(anomalies)
    total_anom_amt = anomalies["Credit Request Total"].sum()

    # Grouped views
    # 1) By customer
    if "Customer Number" in anomalies.columns:
        by_cust = (
            anomalies.groupby("Customer Number", dropna=False)["Credit Request Total"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )
    else:
        by_cust = pd.Series(dtype=float)

    # 2) By item
    if "Item Number" in anomalies.columns:
        by_item = (
            anomalies.groupby("Item Number", dropna=False)["Credit Request Total"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )
    else:
        by_item = pd.Series(dtype=float)

    # 3) By sales rep
    if "Sales Rep" in anomalies.columns:
        by_rep = (
            anomalies.groupby("Sales Rep", dropna=False)["Credit Request Total"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )
    else:
        by_rep = pd.Series(dtype=float)

    # Top raw anomaly rows (sorted by |z|)
    anomalies["abs_z"] = anomalies["z_score"].abs()
    top_rows = anomalies.sort_values("abs_z", ascending=False).head(15)

    lines: list[str] = []

    lines.append("🚨 **Credit Anomaly Scan – Last 90 Days**")
    lines.append(
        f"- Window analyzed: **{cutoff.date()} → {latest.date()}**"
    )
    lines.append(
        f"- Anomalous credits found: **{total_anom}** "
        f"totalling **{format_money(total_anom_amt)}**"
    )
    lines.append(
        f"- Rule: amount ≥ {format_money(amount_threshold)}, |z-score| ≥ {z_threshold:.1f}"
    )
    lines.append("")

    # Group summaries
    if not by_cust.empty:
        lines.append("👥 **Top customers with anomalous credits:**")
        for cust, val in by_cust.items():
            label = cust if pd.notna(cust) else "UNKNOWN"
            lines.append(f"- {label}: {format_money(val)} in anomalies")
        lines.append("")

    if not by_item.empty:
        lines.append("📦 **Top items with anomalous credits:**")
        for item, val in by_item.items():
            label = item if pd.notna(item) else "UNKNOWN"
            lines.append(f"- Item {label}: {format_money(val)} in anomalies")
        lines.append("")

    if not by_rep.empty:
        lines.append("🧑‍💼 **Top sales reps with anomalous credits:**")
        for rep, val in by_rep.items():
            label = rep if pd.notna(rep) else "UNKNOWN"
            lines.append(f"- {label}: {format_money(val)} in anomalies")
        lines.append("")

    # Detailed list
    lines.append("🔍 **Most extreme anomalous credits (top 15 by |z-score|):**")
    for _, r in top_rows.iterrows():
        d = r.get("Date")
        d_str = d.strftime("%Y-%m-%d") if isinstance(d, pd.Timestamp) else "Unknown"

        tnum = r.get("Ticket Number", "N/A")
        cust = r.get("Customer Number", "N/A")
        item = r.get("Item Number", "N/A")
        rep = r.get("Sales Rep", "N/A")
        amt = float(r.get("Credit Request Total", 0.0))
        z = float(r.get("z_score", 0.0))

        lines.append(
            f"- **{d_str}** — Ticket **{tnum}** | Cust **{cust}** | "
            f"Item **{item}** | Rep **{rep}** — Amount: {format_money(amt)} "
            f"(z = {z:+.2f})"
        )

    lines.append(
        "\n📝 **Use case:** This view is perfect for weekly risk reviews – it surfaces a "
        "short list of unusually large credits by customer, item, and rep."
    )

    return "\n".join(lines)
