import re
import pandas as pd

from skybar.utils.formatting import format_money


def _find_customer_column(df: pd.DataFrame) -> str | None:
    candidates = [
        "Customer Number",
        "Customer",
        "Customer Code",
        "Customer ID",
        "Cust #",
        "Cust",
    ]
    for col in candidates:
        if col in df.columns:
            return col
    return None


def intent_top_accounts(query: str, df: pd.DataFrame) -> str | None:
    """
    Handle questions like:
      - "Which accounts have the most credits turned in?"
      - "Which customers have the most credits issued?"
      - "Show top accounts by credit dollars."
    """
    q = query.lower()

    # Must be about accounts/customers + credits + some notion of "top"
    if not any(w in q for w in ["account", "accounts", "customer", "customers"]):
        return None
    if "credit" not in q and "credits" not in q:
        return None
    if not any(w in q for w in ["most", "top", "highest", "biggest"]):
        return None

    dv = df.copy()

    # --- find customer column ---
    cust_col = _find_customer_column(dv)
    if cust_col is None:
        return (
            "I couldn't identify a customer/account column "
            "(looked for 'Customer', 'Customer Number', etc.), "
            "so I can't rank accounts by credits."
        )

    # --- numeric credit total ---
    if "Credit Request Total" not in dv.columns:
        return (
            "I don't see a `Credit Request Total` column, so I can't compute "
            "which accounts have the most credits."
        )

    dv["Credit Request Total"] = pd.to_numeric(
        dv["Credit Request Total"], errors="coerce"
    )
    dv = dv[dv["Credit Request Total"].notna() & (dv["Credit Request Total"] != 0)]

    # --- If query sounds like "issued" / "have numbers", require RTN_CR_No ---
    if any(w in q for w in ["issued", "with credit number", "have credit numbers"]):
        if "RTN_CR_No" in dv.columns:
            dv = dv[dv["RTN_CR_No"].astype(str).str.strip().ne("")]
        # if RTN_CR_No missing, we still continue, just using all credit rows

    if dv.empty:
        return "I don't see any credit records I can use to rank accounts."

    # --- group by customer/account ---
    # Count unique tickets if available, otherwise row count
    if "Ticket Number" in dv.columns:
        grouped = (
            dv.groupby(cust_col)
            .agg(
                ticket_count=("Ticket Number", "nunique"),
                credit_total=("Credit Request Total", "sum"),
            )
            .reset_index()
        )
    else:
        grouped = (
            dv.groupby(cust_col)
            .agg(
                ticket_count=("Credit Request Total", "size"),
                credit_total=("Credit Request Total", "sum"),
            )
            .reset_index()
        )

    grouped = grouped.sort_values(
        ["credit_total", "ticket_count"], ascending=[False, False]
    )

    top_n = grouped.head(10)

    lines: list[str] = []

    lines.append(
        "Here are the **accounts/customers with the most credits** "
        "(ranked by total `Credit Request Total`):"
    )
    lines.append(f"- Total accounts in ranking: **{len(grouped)}**")
    lines.append("")
    lines.append("Top accounts (up to 10):")

    for _, row in top_n.iterrows():
        cust = row[cust_col]
        count = int(row["ticket_count"])
        total = row["credit_total"]
        total_str = format_money(total)

        cust_label = str(cust) if pd.notna(cust) and str(cust).strip() else "Unknown"
        lines.append(
            f"- **{cust_label}** — **{count}** ticket(s), "
            f"total credits **{total_str}**"
        )

    if len(grouped) > len(top_n):
        lines.append(f"...and **{len(grouped) - len(top_n)}** more account(s) below.")

    return "\n".join(lines)
