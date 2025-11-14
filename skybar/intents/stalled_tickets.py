import re
from datetime import timedelta
import pandas as pd

from skybar.utils.df_cleaning import coerce_date


def _ensure_update_timestamp(dv: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure dv has an 'Update Timestamp' column, derived from Status if needed.
    Status format is expected to have [YYYY-MM-DD HH:MM:SS] inside.
    """
    dv = dv.copy()

    if "Update Timestamp" in dv.columns:
        dv["Update Timestamp"] = pd.to_datetime(
            dv["Update Timestamp"], errors="coerce"
        )
        return dv

    if "Status" not in dv.columns:
        dv["Update Timestamp"] = pd.NaT
        return dv

    dv["Status"] = dv["Status"].astype(str)

    ts_pattern = r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]"
    dv["Update Timestamp"] = dv["Status"].str.extract(ts_pattern)[0]
    dv["Update Timestamp"] = pd.to_datetime(
        dv["Update Timestamp"], errors="coerce"
    )
    return dv


def _has_rtn(series: pd.Series) -> pd.Series:
    """
    True = row HAS a credit number (RTN_CR_No).
    """
    s = series.astype(str).str.strip()
    return (s != "") & ~s.str.upper().isin(["NAN", "NONE", "NULL", "NA"])


def intent_stalled_tickets(query: str, df: pd.DataFrame) -> str | None:
    """
    Handle queries like:
      - "SkyBar, which tickets are stalled?"
      - "Show credits that haven't been updated in 7 days"
      - "Which tickets have no recent updates?"

    Logic:
      - Only tickets WITHOUT RTN_CR_No (still open)
      - Compute days since last Update Timestamp
      - Default threshold = 7 days (can parse '14 days', '30 days', etc.)
    """
    q_low = query.lower()

    # Intent detection
    keywords = [
        "stalled",
        "no recent update",
        "no updates",
        "not updated",
        "haven't been updated",
        "haven’t been updated",
        "no movement",
    ]
    if not any(k in q_low for k in keywords):
        return None
    if "ticket" not in q_low and "credit" not in q_low:
        return None

    # Threshold for "stalled"
    m = re.search(r"(\d+)\s+day", q_low)
    stalled_days = int(m.group(1)) if m else 7

    dv = df.copy()

    # Ensure Update Timestamp exists
    dv = _ensure_update_timestamp(dv)

    if "Update Timestamp" not in dv.columns:
        return (
            "I can't detect stalled tickets because I don't see an "
            "`Update Timestamp` column or a `Status` column with timestamps."
        )

    # Optional Date -> Days Open
    if "Date" in dv.columns:
        dv["Date"] = coerce_date(dv["Date"])
    else:
        dv["Date"] = pd.NaT

    today = pd.Timestamp.today().normalize()

    dv["Days Since Update"] = (today - dv["Update Timestamp"]).dt.days

    # Use Date if available
    dv["Days Open"] = (today - dv["Date"]).dt.days

    # Only consider tickets that:
    #   - have an update timestamp
    #   - haven't been updated in >= stalled_days
    mask_stalled_basic = dv["Update Timestamp"].notna() & (
        dv["Days Since Update"] >= stalled_days
    )

    # Only *open* tickets (no RTN_CR_No)
    if "RTN_CR_No" in dv.columns:
        has_rtn = _has_rtn(dv["RTN_CR_No"])
        open_mask = ~has_rtn
    else:
        open_mask = pd.Series(True, index=dv.index)

    stalled_df = dv[mask_stalled_basic & open_mask].copy()

    if stalled_df.empty:
        return (
            f"I don't see any open tickets without RTN_CR_No that have been "
            f"stalled for **{stalled_days}+** days."
        )

    total_stalled = len(stalled_df)

    # Small breakdown by how long they've been quiet
    def bucketize(x: float | int) -> str:
        if x < stalled_days:
            return f"<{stalled_days}"
        elif x <= stalled_days + 7:
            return f"{stalled_days}–{stalled_days + 7}"
        elif x <= 30:
            return "15–30"
        else:
            return "30+"

    stalled_df["Stall Bucket"] = stalled_df["Days Since Update"].apply(bucketize)
    bucket_counts = (
        stalled_df["Stall Bucket"].value_counts().reindex(
            [f"{stalled_days}–{stalled_days + 7}", "15–30", "30+"],
            fill_value=0,
        )
    )

    lines: list[str] = [
        f"Here are **stalled tickets** (no credit number, no updates for **{stalled_days}+ days**):",
        f"- Total stalled tickets: **{total_stalled}**",
        "",
        "Stall buckets (days since last update):",
        f"- **{stalled_days}–{stalled_days + 7} days**: {int(bucket_counts[f'{stalled_days}–{stalled_days + 7}'])} ticket(s)",
        f"- **15–30 days**: {int(bucket_counts['15–30'])} ticket(s)",
        f"- **30+ days**: {int(bucket_counts['30+'])} ticket(s)",
        "",
        "Most stalled tickets first (top 20):",
    ]

    sample = stalled_df.sort_values(
        ["Days Since Update", "Days Open"], ascending=False
    ).head(20)

    for _, r in sample.iterrows():
        tnum = r.get("Ticket Number", "N/A")
        cust = r.get("Customer Number", "N/A")
        last_ts = r.get("Update Timestamp")
        last_ts_str = (
            last_ts.strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(last_ts, pd.Timestamp)
            else "Unknown time"
        )
        days_since_update = int(r.get("Days Since Update", 0))
        days_open = r.get("Days Open")
        days_open_str = (
            f", **{int(days_open)} days open**" if pd.notna(days_open) else ""
        )

        status_snip = str(r.get("Status", "")).replace("\n", " ").strip()
        if len(status_snip) > 160:
            status_snip = status_snip[:157] + "..."

        lines.append(
            f"- **{last_ts_str}** — Ticket **{tnum}** (Customer **{cust}**) — "
            f"*{status_snip}* — **{days_since_update} days since last update**{days_open_str}"
        )

    if len(stalled_df) > len(sample):
        lines.append(
            f"...and **{len(stalled_df) - len(sample)}** more stalled ticket(s)."
        )

    return "\n".join(lines)
