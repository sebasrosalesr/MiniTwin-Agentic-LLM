import pandas as pd

from skybar.utils.df_cleaning import coerce_date
from skybar.utils.formatting import format_money
from skybar.utils.matching import normalize


def intent_rtn_summary(query: str, df: pd.DataFrame) -> str | None:
    """
    Handle queries like:
      - "How many credits have a credit number?"
      - "Show me records with RTN_CR_No"
      - "SkyBar, which credits have RTNs?"
    """
    q_low = query.lower()

    # Intent trigger rules
    if (
        ("credit number" not in q_low)
        and ("rtn_cr_no" not in q_low)
        and not ("rtn" in q_low and "credit" in q_low)
    ):
        return None  # Not for this intent

    colname = "RTN_CR_No"
    if colname not in df.columns:
        return "I can’t find the `RTN_CR_No` column in the dataset."

    dv = df.copy()

    # Non-empty RTN filter
    rtn_col = dv[colname].astype(str).str.strip()
    valid_mask = rtn_col.ne("") & ~rtn_col.str.upper().isin(["NAN", "NONE", "NULL"])
    rtn_df = dv[valid_mask].copy()

    if rtn_df.empty:
        return "I don’t see any credits with a populated `RTN_CR_No` yet."

    total_with_rtn = len(rtn_df)

    # Clean up dates for sorting
    if "Date" in rtn_df.columns:
        rtn_df["Date"] = coerce_date(rtn_df["Date"])
        rtn_df = rtn_df.sort_values("Date", ascending=False)

    lines = [
        f"I currently see **{total_with_rtn}** credit request(s) with a non-empty **RTN_CR_No**.",
        "",
        "Here are some of the most recent ones:"
    ]

    sample = rtn_df.head(20)

    for _, r in sample.iterrows():
        d = r.get("Date")
        d_str = d.strftime("%Y-%m-%d") if isinstance(d, pd.Timestamp) else "Unknown date"
        cust = r.get("Customer Number", "N/A")
        inv  = r.get("Invoice Number", "N/A")
        tnum = r.get("Ticket Number", "N/A")
        rtn  = r.get("RTN_CR_No", "N/A")

        lines.append(
            f"- **{d_str}** — Customer **{cust}**, Invoice **{inv}**, "
            f"Ticket **{tnum}**, Credit Number (RTN_CR_No): **{rtn}**"
        )

    if len(rtn_df) > 20:
        lines.append(f"...and **{len(rtn_df) - 20}** more record(s) with a credit number.")

    return "\n".join(lines)
