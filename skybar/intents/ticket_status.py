import re
import pandas as pd

from skybar.utils.formatting import format_money


def intent_ticket_status(query, df):
    """
    Handles questions like:
      - MiniTwin, status on ticket R-040699
      - Show me ticket R-045013
      - What's happening with R-050155?
    
    Now upgraded:
      ✔ Returns ALL rows for the ticket
      ✔ Still provides a clean summary at the top
    """

    m = re.search(r"(R-\d+)", query, flags=re.IGNORECASE)
    if not m:
        return None

    ticket = m.group(1).upper()

    # Match all rows for this ticket
    mask = df["Ticket Number"].astype(str).str.upper() == ticket
    all_rows = df[mask].copy()

    if all_rows.empty:
        return f"I couldn't find any records for ticket **{ticket}**."

    # Sort by Date if available
    if "Date" in all_rows.columns:
        all_rows = all_rows.sort_values("Date", ascending=True)

    # Short high-level summary from the earliest record
    first = all_rows.iloc[0]

    date = first.get("Date")
    date_str = date.strftime("%Y-%m-%d") if isinstance(date, pd.Timestamp) else "Unknown date"

    # Total credit $ across all entries
    total_sum = None
    if "Credit Request Total" in all_rows.columns:
        total_sum = pd.to_numeric(all_rows["Credit Request Total"], errors="coerce").sum()

    out = []
    out.append(f"🧾 **Details for ticket {ticket}**\n")
    out.append(f"- Customer: **{first.get('Customer Number','N/A')}**")
    out.append(f"- First Date Seen: **{date_str}**")
    out.append(f"- Total credit across all related entries: **{format_money(total_sum)}**")
    out.append("")
    out.append("📋 **All matching entries (up to 20):**")

    # Show up to 20 rows
    subset = all_rows.head(20)

    for _, r in subset.iterrows():
        dt = r.get("Date")
        dt_str = dt.strftime("%Y-%m-%d") if isinstance(dt, pd.Timestamp) else str(dt)

        status = r.get("Status", "N/A")
        inv = r.get("Invoice Number", "N/A")
        item = r.get("Item Number", "N/A")

        amount = r.get("Credit Request Total", None)
        try:
            amt_str = format_money(float(amount))
        except:
            amt_str = "N/A"

        reason = str(r.get("Reason for Credit", "")).replace("\n", " ").strip()
        if len(reason) > 120:
            reason = reason[:117] + "..."

        out.append(
            f"- **{dt_str}** | Invoice: **{inv}** | Item: **{item}** | "
            f"Amount: **{amt_str}** | Status: _{status}_\n"
            f"  • {reason}"
        )

    return "\n".join(out)
