import pandas as pd
import re

from skybar.utils.df_cleaning import coerce_date


def _no_rtn_mask(dv: pd.DataFrame) -> pd.Series:
    """
    True = ticket still *needs* a credit number.
    False = ticket already has a credit number somewhere.

    We treat a ticket as having a credit number if:
      - RTN_CR_No column is non-empty / non-null
        OR
      - Status text mentions any kind of "credit number",
        "Credit Request No.:", or RTNCM code.
    """
    col = "RTN_CR_No"

    # 1) Normalize RTN_CR_No column if present
    if col in dv.columns:
        rtn_series = dv[col].astype(str).str.strip()
    else:
        rtn_series = pd.Series("", index=dv.index)

    bad_vals = {"", "NAN", "NONE", "NULL", "NA"}
    has_rtn_col = ~rtn_series.str.upper().isin(bad_vals)

    # 2) Look into Status text for evidence of a credit number
    status = dv.get("Status", pd.Series("", index=dv.index)).astype(str)
    status_upper = status.str.upper()

    status_has_credit = (
        status_upper.str.contains("CREDIT NUMBER", na=False) |
        status_upper.str.contains("CREDIT NUMBERS", na=False) |
        status_upper.str.contains("CREDIT REQUEST NO.:", na=False) |
        status_upper.str.contains("CREDIT REQUEST NO", na=False) |
        status_upper.str.contains("RTNCM", na=False)       # catch RTNCM0031274, etc.
    )

    # 3) Ticket is considered to HAVE a credit if either condition is true
    has_credit = has_rtn_col | status_has_credit

    # 4) We want only tickets that still need a credit number
    return ~has_credit


def intent_priority_tickets(query: str, df: pd.DataFrame) -> str | None:
    """
    Handle queries like:
      - "SkyBar, what tickets are priority?"
      - "Which tickets are priority right now?"
      - "Show priority tickets older than 15 days"

    Logic:
      * Use 'Date' as ticket creation date
      * Filter to tickets OLDER than 15 days
      * Exclude tickets that already have RTN_CR_No
      * Sort by Date ascending (oldest first)
    """
    q_low = query.lower()

    # Only trigger if user talks about tickets + priority
    if "priority" not in q_low or "ticket" not in q_low:
        return None

    if "Date" not in df.columns:
        return "I can't compute priority tickets because there is no `Date` column in the dataset."

    dv = df.copy()
    dv["Date"] = coerce_date(dv["Date"])

    # Keep only rows with a valid Date
    dv = dv.dropna(subset=["Date"])
    if dv.empty:
        return "I don't see any tickets with a valid `Date`, so I can't compute priorities yet."

    # Filter out tickets that already have a credit number (RTN_CR_No)
    mask_no_rtn = _no_rtn_mask(dv)
    dv = dv[mask_no_rtn].copy()

    if dv.empty:
        return "Nice! Every ticket with a valid date already has a credit number. No pending priority tickets."

    # Priority definition: older than 15 days
    today = pd.Timestamp.today().normalize()
    cutoff = today - pd.Timedelta(days=15)

    priority_df = dv[dv["Date"] <= cutoff].copy()
    if priority_df.empty:
        return (
            f"I don't see any tickets older than 15 days without a credit number. "
            f"Oldest open tickets are still within the 15-day window."
        )

    # Compute age in days
    priority_df["Days Open"] = (today - priority_df["Date"]).dt.days

    # Sort oldest first
    priority_df = priority_df.sort_values("Date", ascending=True)

    total_priority = len(priority_df)

    lines = [
        f"Here are **priority tickets** without a credit number (RTN_CR_No), "
        f"older than **15 days**:",
        f"- Total priority tickets: **{total_priority}**",
        "",
        "Oldest tickets first (top 20):"
    ]

    sample = priority_df.head(20)

    for _, r in sample.iterrows():
        d = r["Date"]
        d_str = d.strftime("%Y-%m-%d") if isinstance(d, pd.Timestamp) else "Unknown date"
        days_open = int(r.get("Days Open", 0)) if pd.notnull(r.get("Days Open")) else "?"
        tnum = r.get("Ticket Number", "N/A")
        cust = r.get("Customer Number", "N/A")
        status = r.get("Status", "N/A")

        lines.append(
            f"- **{d_str}** — Ticket **{tnum}** (Customer **{cust}**) — "
            f"*{status}* — **{days_open} days open**"
        )

    if total_priority > len(sample):
        lines.append(f"...and **{total_priority - len(sample)}** more priority ticket(s).")

    return "\n".join(lines)
