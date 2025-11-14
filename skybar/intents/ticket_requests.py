# skybar/intents/ticket_requests.py
import re
import pandas as pd

def intent_ticket_requests(query: str, df: pd.DataFrame):
    """
    Detect ticket lookup and return:
      - text summary
      - matching DataFrame
    """
    m = re.search(r"(R-\d+)", query, flags=re.IGNORECASE)
    if not m:
        return None

    ticket = m.group(1).upper()

    mask = df["Ticket Number"].astype(str).str.upper() == ticket
    df_match = df[mask].copy()

    if df_match.empty:
        return f"No rows found for **{ticket}**.", None

    total_rows = len(df_match)
    total_credit = pd.to_numeric(
        df_match.get("Credit Request Total", 0), errors="coerce"
    ).sum()

    summary = (
        f"### 📄 All entries for ticket **{ticket}**\n"
        f"- Rows found: **{total_rows}**\n"
        f"- Total Credit Request Total: **${total_credit:,.2f}**\n"
    )

    return summary, df_match
