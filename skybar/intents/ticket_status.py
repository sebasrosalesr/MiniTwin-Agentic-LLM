import re
import pandas as pd

def intent_ticket_status(query, df):
    m = re.search(r"(R-\d+)", query, flags=re.IGNORECASE)
    if not m:
        return None  # not this intent

    ticket = m.group(1).upper()

    row = df[df["Ticket Number"].astype(str).str.upper() == ticket]
    if row.empty:
        return f"I couldn't find a record for ticket **{ticket}**."

    row = row.iloc[0]

    date = row["Date"]
    date_str = date.strftime("%Y-%m-%d") if isinstance(date, pd.Timestamp) else "Unknown date"

    total = row.get("Credit Request Total", "N/A")
    try:
        total = f"${float(total):,.2f}"
    except:
        pass

    return (
        f"Absolutely. Here's what I see for **ticket {ticket}**:\n"
        f"- Customer: **{row.get('Customer Number','N/A')}**\n"
        f"- Date: **{date_str}**\n"
        f"- Status: **{row.get('Status','N/A')}**\n"
        f"- Invoice: **{row.get('Invoice Number','N/A')}**\n"
        f"- Item: **{row.get('Item Number','N/A')}**\n"
        f"- Credit Total: **{total}**"
    )
