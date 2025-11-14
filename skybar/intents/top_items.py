import re
import pandas as pd

from skybar.utils.formatting import format_money


def _find_item_column(df: pd.DataFrame) -> str | None:
    candidates = [
        "Item Number",
        "Item",
        "Item ID",
        "Item Code",
        "Item #",
        "ItemNum",
    ]
    for col in candidates:
        if col in df.columns:
            return col
    return None


def intent_top_items(query: str, df: pd.DataFrame) -> str | None:
    """
    Handle questions like:
      - "Which items have the most credits issued?"
      - "Show top credited items."
      - "What items are getting the most credits?"
    """
    q = query.lower()

    # Must be about items/products + credits + some notion of "top"
    if not any(w in q for w in ["item", "items", "sku", "product", "products"]):
        return None
    if "credit" not in q and "credits" not in q:
        return None
    if not any(w in q for w in ["most", "top", "highest", "biggest"]):
        return None

    dv = df.copy()

    item_col = _find_item_column(dv)
    if item_col is None:
        return (
            "I couldn't identify an item column "
            "(looked for 'Item Number', 'Item', 'Item ID', etc.), "
            "so I can't rank items by credits."
        )

    if "Credit Request Total" not in dv.columns:
        return (
            "I don't see a `Credit Request Total` column, so I can't compute "
            "which items have the most credits."
        )

    dv["Credit Request Total"] = pd.to_numeric(
        dv["Credit Request Total"], errors="coerce"
    )
    dv = dv[dv["Credit Request Total"].notna() & (dv["Credit Request Total"] != 0)]

    # If they say "issued" or explicitly reference credit numbers, filter to RTN_CR_No
    if any(w in q for w in ["issued", "with credit number", "have credit numbers"]):
        if "RTN_CR_No" in dv.columns:
            dv = dv[dv["RTN_CR_No"].astype(str).str.strip().ne("")]

    if dv.empty:
        return "I don't see any credit records I can use to rank items."

    # Count unique tickets per item, and total credit dollars
    if "Ticket Number" in dv.columns:
        grouped = (
            dv.groupby(item_col)
            .agg(
                ticket_count=("Ticket Number", "nunique"),
                credit_total=("Credit Request Total", "sum"),
            )
            .reset_index()
        )
    else:
        grouped = (
            dv.groupby(item_col)
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
        "Here are the **items with the most credits** "
        "(ranked by total `Credit Request Total`):"
    )
    lines.append(f"- Total items in ranking: **{len(grouped)}**")
    lines.append("")
    lines.append("Top items (up to 10):")

    for _, row in top_n.iterrows():
        item = row[item_col]
        count = int(row["ticket_count"])
        total = row["credit_total"]
        total_str = format_money(total)

        item_label = str(item) if pd.notna(item) and str(item).strip() else "Unknown"
        lines.append(
            f"- **{item_label}** — **{count}** ticket(s), "
            f"total credits **{total_str}**"
        )

    if len(grouped) > len(top_n):
        lines.append(f"...and **{len(grouped) - len(top_n)}** more item(s) below.")

    return "\n".join(lines)
