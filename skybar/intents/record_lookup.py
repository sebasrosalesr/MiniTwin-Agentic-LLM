import re
import pandas as pd

from skybar.utils.formatting import format_money


def _norm(series: pd.Series) -> pd.Series:
    """Normalize IDs for comparison."""
    return (
        series.astype(str)
        .str.strip()
        .str.upper()
        .str.replace(" ", "", regex=False)
    )


def _extract_ids(query: str) -> list[str]:
    """
    Pull possible ticket / invoice IDs out of the query text.
    Examples it will catch:
      - R-040699
      - r-045013
      - INV14068709
      - 14068709  (plain number, often invoice)
    """
    ids: set[str] = set()

    # Ticket style: R-123456 or r-1234
    for m in re.findall(r"\bR-\d{3,}\b", query, flags=re.IGNORECASE):
        ids.add(m.upper())

    # Invoice style: INV + digits
    for m in re.findall(r"\bINV-?\d{4,}\b", query, flags=re.IGNORECASE):
        ids.add(m.upper().replace("-", ""))

    # Plain long numbers (6+ digits) – likely invoices
    for m in re.findall(r"\b\d{6,}\b", query):
        ids.add(m)

    return list(ids)


def intent_record_lookup(query: str, df: pd.DataFrame) -> str | None:
    """
    Handle queries like:
      - "Is ticket R-040699 logged in the system?"
      - "Do we have invoice 14068709 in the credit file?"
      - "Is invoice INV14068709 on record?"

    It checks Ticket Number and Invoice Number and reports
    whether we have any matching rows, plus a short summary.
    """
    q_low = query.lower()

    # Only trigger when the user is asking about existence / being logged
    keywords = ["logged", "in the system", "on record", "on file", "do we have", "exist"]
    if not any(k in q_low for k in keywords):
        return None

    # Must look like a ticket / invoice question
    if "ticket" not in q_low and "invoice" not in q_low and "credit" not in q_low:
        # Let other intents try
        return None

    # Need at least one of these columns to do anything
    has_ticket_col = "Ticket Number" in df.columns
    has_invoice_col = "Invoice Number" in df.columns
    if not (has_ticket_col or has_invoice_col):
        return (
            "I can't check whether a record is logged because I don't see "
            "`Ticket Number` or `Invoice Number` columns in the dataset."
        )

    ids = _extract_ids(query)
    if not ids:
        # No ID found – let other intents maybe handle it
        return None

    # Normalized columns
    ticket_norm = _norm(df["Ticket Number"]) if has_ticket_col else None
    invoice_norm = _norm(df["Invoice Number"]) if has_invoice_col else None

    lines: list[str] = []
    lines.append("🔍 **Record lookup – is this ticket / invoice logged?**")
    lines.append("")

    for rid in ids:
        masks = []

        if has_ticket_col:
            masks.append(ticket_norm == rid)

        if has_invoice_col:
            # Accept exact invoice ID or with INV prefix stripped
            rid_clean = rid.replace("INV", "").replace("INV-", "")
            invoice_mask = (invoice_norm == rid) | (invoice_norm == rid_clean)
            masks.append(invoice_mask)

        if not masks:
            continue

        mask_all = masks[0]
        for m in masks[1:]:
            mask_all = mask_all | m

        found_df = df[mask_all].copy()
        count = len(found_df)

        if count == 0:
            lines.append(f"❌ **{rid}** — not found in this dataset.")
            continue

        # Optional money summary
        total_amt = None
        if "Credit Request Total" in found_df.columns:
            total_amt = pd.to_numeric(
                found_df["Credit Request Total"], errors="coerce"
            ).sum()

        lines.append(f"✅ **{rid}** — found **{count}** record(s).")

        if total_amt is not None:
            lines.append(f"   • Sum of `Credit Request Total`: {format_money(total_amt)}")

        # Show up to 3 example rows with key info
        sample = found_df.head(3)
        for _, r in sample.iterrows():
            tnum = r.get("Ticket Number", "")
            inv = r.get("Invoice Number", "")
            date = r.get("Date", "")
            status = r.get("Status", "")
            reason = str(r.get("Reason for Credit", "")).replace("\n", " ").strip()
            if len(reason) > 90:
                reason = reason[:87] + "..."

            parts = []
            if pd.notna(tnum) and str(tnum).strip():
                parts.append(f"Ticket **{tnum}**")
            if pd.notna(inv) and str(inv).strip():
                parts.append(f"Invoice **{inv}**")
            if pd.notna(date) and str(date).strip():
                parts.append(f"Date: {date}")
            if pd.notna(status) and str(status).strip():
                parts.append(f"Status: {status}")

            header = " | ".join(parts) if parts else "Record:"
            if reason:
                lines.append(f"   • {header} — _{reason}_")
            else:
                lines.append(f"   • {header}")

        lines.append("")  # blank line between IDs

    return "\n".join(lines)
