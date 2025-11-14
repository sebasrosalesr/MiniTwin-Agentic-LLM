import re
import pandas as pd
import streamlit as st
from io import StringIO

def intent_ticket_requests(query: str, df: pd.DataFrame) -> str | None:
    """
    Example trigger phrases:
      - "show me all the requests for ticket R-040699"
      - "MiniTwin, all entries for R-045013"
      - "display every record for ticket R-XXXXXX"
    """

    m = re.search(r"(R-\d+)", query, flags=re.IGNORECASE)
    if not m:
        return None

    ticket = m.group(1).upper()

    mask = df["Ticket Number"].astype(str).str.upper() == ticket
    df_match = df[mask].copy()

    if df_match.empty:
        return f"No rows found for **{ticket}**."

    # ---- SUMMARY OUTPUT ----
    total_rows = len(df_match)
    total_credit = pd.to_numeric(df_match.get("Credit Request Total", 0), errors="coerce").sum()

    st.markdown(f"### 📄 All entries for ticket **{ticket}**")
    st.markdown(f"- Rows found: **{total_rows}**")
    st.markdown(f"- Total Credit Request Total: **${total_credit:,.2f}**")

    # ---- SHOW TABLE ----
    st.dataframe(df_match)

    # ---- CSV EXPORT ----
    csv = df_match.to_csv(index=False)
    st.download_button(
        label="⬇️ Download these entries as CSV",
        data=csv,
        file_name=f"{ticket}_entries.csv",
        mime="text/csv"
    )

    return ""  # Streamlit already rendered everything
