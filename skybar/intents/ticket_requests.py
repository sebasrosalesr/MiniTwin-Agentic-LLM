# /content/skybar/intents/ticket_requests.py
import re
import pandas as pd

def intent_ticket_requests(query: str, df: pd.DataFrame) -> str | None:
    """
    Handle queries like:
      - "Show me all the requests for ticket R-040699"
      - "Display all data for ticket R-048484"
      - "List everything related to ticket R-123456"
    """

    q_low = query.lower()
    if "ticket" not in q_low and "r-" not in q_low:
        return None

    # Extract ticket IDs
    matches = re.findall(r"R-\d{3,}", query, flags=re.IGNORECASE)
    if not matches:
        return None

    # Normalize
    ticket_ids = [m.upper().strip() for m in matches]

    # Make sure column exists
    if "Ticket Number" not in df.columns:
        return "I can't find ticket details because the `Ticket Number` column is missing."

    df_norm = df.copy()
    df_norm["Ticket Number"] = df_norm["Ticket Number"].astype(str).str.upper().str.strip()

    all_lines = []
    global LAST_TICKET_LOOKUP
    LAST_TICKET_LOOKUP = None  # reset for Streamlit

    for tid in ticket_ids:
        subset = df_norm[df_norm["Ticket Number"] == tid]

        if subset.empty:
            all_lines.append(f"❌ No records found for **{tid}**.")
            continue

        # Save for Streamlit UI layer to show as dataframe
        LAST_TICKET_LOOKUP = subset.copy()

        all_lines.append(
            f"📄 **Found {len(subset)} record(s) for ticket {tid}.**\n"
            f"Displaying full table below 👇"
        )

    return "\n\n".join(all_lines) if all_lines else None
