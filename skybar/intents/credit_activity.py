import re
from datetime import timedelta
from dateutil import parser
import pandas as pd

from skybar.utils.formatting import format_money  # you already have this


def _ensure_update_timestamp(dv: pd.DataFrame) -> pd.DataFrame:
    """
    Build 'Update Timestamp' from Status if needed.
    Status expected to contain: [YYYY-MM-DD HH:MM:SS]
    """
    dv = dv.copy()
    dv["Status"] = dv.get("Status", "").astype(str)

    timestamp_pattern = r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]"
    dv["Update Timestamp"] = dv["Status"].str.extract(timestamp_pattern)[0]
    dv["Update Timestamp"] = pd.to_datetime(dv["Update Timestamp"], errors="coerce")
    return dv


def _get_date_window(q_low: str) -> tuple[pd.Timestamp | None, pd.Timestamp]:
    """
    Turn phrases like:
      - 'from nov 1st to today?'
      - 'last 7 days'
      - 'last 30 days'
      - 'this month'
    into (start, end) timestamps.
    """
    today = pd.Timestamp.today().normalize()
    end = today
    start = None

    # strip punctuation so 'today?' -> 'today'
    q_clean = re.sub(r"[?!,\.]", " ", q_low)

    # 1) Explicit range: "from <date> to today"
    m = re.search(r"from\s+(.+?)\s+to\s+today", q_clean)
    if m:
        raw_start = m.group(1).strip()
        try:
            dt = parser.parse(raw_start, fuzzy=True, dayfirst=False)
            start = pd.Timestamp(dt.date())
        except Exception:
            start = None

    # 2) Relative windows if we still don't have a start
    if start is None:
        if ("last 7" in q_clean
            or "last seven" in q_clean
            or "last 7 days" in q_clean
            or "last week" in q_clean):
            start = today - timedelta(days=7)

        elif ("last 30" in q_clean
              or "last thirty" in q_clean
              or "last 30 days" in q_clean
              or "last month" in q_clean):
            start = today - timedelta(days=30)

        elif "this month" in q_clean:
            start = today.replace(day=1)

    return start, end


def intent_credit_activity(query: str, df: pd.DataFrame) -> str | None:
    """
    Handle queries like:
      - "SkyBar, how many credits did I update from Nov 1st to today?"
      - "SkyBar, how many credits did I update last 7 days?"
      - "SkyBar, how many credits did I update this month?"
    """
    q_low = query.lower()

    # needs to talk about credits + updates
    if ("credit" not in q_low and "credits" not in q_low) or \
       ("update" not in q_low and "updated" not in q_low):
        return None

    start, end = _get_date_window(q_low)
    if start is None:
        # Let other intents try
        return None

    dv = _ensure_update_timestamp(df)

    mask = dv["Update Timestamp"].between(start, end)
    subset = dv[mask].dropna(subset=["Update Timestamp"]).copy()

    if subset.empty:
        return (
            f"I don't see any timestamped credit updates between "
            f"**{start.date()}** and **{end.date()}**."
        )

    # ---- Metrics ----
    total_records = len(subset)
    unique_tickets = subset["Ticket Number"].nunique() if "Ticket Number" in subset.columns else None

    if "Credit Request Total" in subset.columns:
        total_credits = pd.to_numeric(subset["Credit Request Total"], errors="coerce").sum()
        total_credits_str = format_money(total_credits)
    else:
        total_credits_str = "N/A"

    lines = [
        f"For this period (**{start.date()}** to **{end.date()}**), I see:",
        f"- **{total_records}** credit request record(s) with timestamped updates",
    ]
    if unique_tickets is not None:
        lines.append(f"- **{unique_tickets}** unique ticket(s) updated")
    if "Credit Request Total" in subset.columns:
        lines.append(f"- Total `Credit Request Total`: **{total_credits_str}**")

    lines.append("")
    lines.append("Most recent updates in that range:")

    sample = (
        subset[["Ticket Number", "Update Timestamp", "Status"]]
        .sort_values(by="Update Timestamp", ascending=False)
        .head(10)
    )

    for _, r in sample.iterrows():
        ts = r["Update Timestamp"]
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if isinstance(ts, pd.Timestamp) else "Unknown time"
        tnum = r.get("Ticket Number", "N/A")
        status_text = r.get("Status", "")
        lines.append(f"- **{ts_str}** — Ticket **{tnum}** — {status_text}")

    if len(subset) > len(sample):
        lines.append(f"...and **{len(subset) - len(sample)}** more update record(s).")

    return "\n".join(lines)
