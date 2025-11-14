import re
import pandas as pd
from datetime import timedelta

from skybar.utils.df_cleaning import coerce_date
from skybar.utils.formatting import format_money


def _has_rtn(series: pd.Series) -> pd.Series:
    """
    Return a boolean mask where True = row HAS a credit number (RTN_CR_No).
    Treats NaN / '', 'NONE', 'NULL', 'NAN' as 'no credit number'.
    """
    s = series.astype(str).str.strip()
    return (s != "") & ~s.str.upper().isin(["NAN", "NONE", "NULL", "NA"])


def intent_credit_aging(query: str, df: pd.DataFrame) -> str | None:
    """
    Handle queries like:
      - "SkyBar, show the credit aging summary"
      - "SkyBar, show credits over 60 days"
      - "What does credit aging look like right now?"

    Uses `Date` as the open date and looks ONLY at tickets WITHOUT RTN_CR_No.
    Buckets:
      - 0–7
      - 8–15
      - 16–30
      - 31–60
      - 61–90
      - 90+ days
    """
    q_low = query.lower()

    # Basic intent detection
    if (
        "aging" not in q_low
        and "ageing" not in q_low
        and not re.search(r"\bover\s+\d+\s+day", q_low)
        and not re.search(r"older than\s+\d+\s+day", q_low)
    ):
        return None

    if "credit" not in q_low and "ticket" not in q_low:
        # Feels like some other aging question, let other intents try
        return None

    # Determine a "highlight" threshold if user says:
    #   "over 60 days" / "older than 45 days"
    m = re.search(r"(?:over|older than)\s+(\d+)\s+day", q_low)
    highlight_threshold = int(m.group(1)) if m else 60

    if "Date" not in df.columns:
        return "I can't compute aging without a `Date` column in the dataset."

    dv = df.copy()
    dv["Date"] = coerce_date(dv["Date"])
    dv = dv.dropna(subset=["Date"])

    today = pd.Timestamp.today().normalize()
    dv["Days Open"] = (today - dv["Date"]).dt.days

    # Filter to tickets WITHOUT a credit number
    if "RTN_CR_No" in dv.columns:
        has_rtn_mask = _has_rtn(dv["RTN_CR_No"])
        open_mask = ~has_rtn_mask
    else:
        open_mask = pd.Series(True, index=dv.index)

    open_df = dv[open_mask & (dv["Days Open"] >= 0)].copy()

    if open_df.empty:
        return (
            "I don't see any open credits without a `RTN_CR_No` to build an aging summary."
        )

    # Define aging buckets
    bins = [0, 7, 15, 30, 60, 90, 10**9]
    labels = ["0–7", "8–15", "16–30", "31–60", "61–90", "90+"]

    open_df["Aging Bucket"] = pd.cut(
        open_df["Days Open"],
        bins=bins,
        labels=labels,
        right=True,
        include_lowest=True,
    )

    bucket_counts = open_df["Aging Bucket"].value_counts().reindex(labels, fill_value=0)

    lines: list[str] = [
        "Here’s the **credit aging summary** for open tickets *without* a credit number (RTN_CR_No):",
        "",
        "Buckets (days open):",
    ]

    total_open = len(open_df)
    for label in labels:
        lines.append(f"- **{label} days**: {int(bucket_counts[label])} ticket(s)")

    lines.append(f"\nTotal open tickets without RTN_CR_No: **{total_open}**")

    # Optional total dollar value
    if "Credit Request Total" in open_df.columns:
        total_credits = pd.to_numeric(
            open_df["Credit Request Total"], errors="coerce"
        ).sum()
        lines.append(
            f"- Sum of `Credit Request Total`: **{format_money(total_credits)}**"
        )

    # Highlight *oldest* tickets above the threshold
    critical = (
        open_df[open_df["Days Open"] >= highlight_threshold]
        .sort_values("Days Open", ascending=False)
        .head(20)
    )

    if not critical.empty:
        lines.append("")
        lines.append(
            f"Oldest tickets (≥ **{highlight_threshold}** days open, up to 20 shown):"
        )
        for _, r in critical.iterrows():
            d = r.get("Date")
            d_str = d.strftime("%Y-%m-%d") if isinstance(d, pd.Timestamp) else "Unknown"
            tnum = r.get("Ticket Number", "N/A")
            cust = r.get("Customer Number", "N/A")
            days_open = int(r.get("Days Open", 0))

            # Prefer a short snippet from Status / Reason for Credit
            reason = (
                str(r.get("Status") or r.get("Reason for Credit") or "")
                .replace("\n", " ")
                .strip()
            )
            if len(reason) > 160:
                reason = reason[:157] + "..."

            lines.append(
                f"- **{d_str}** — Ticket **{tnum}** (Customer **{cust}**) "
                f"— *{reason}* — **{days_open} days open**"
            )

        if len(open_df[open_df["Days Open"] >= highlight_threshold]) > len(critical):
            remaining = (
                len(open_df[open_df["Days Open"] >= highlight_threshold]) - len(critical)
            )
            lines.append(f"...and **{remaining}** more ticket(s) in that range.")

    return "\n".join(lines)
