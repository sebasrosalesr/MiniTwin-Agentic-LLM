from typing import Callable, List, Tuple, Union

import pandas as pd

from skybar.intents.ticket_status import intent_ticket_status
from skybar.intents.ticket_requests import intent_ticket_requests
from skybar.intents.record_lookup import intent_record_lookup
from skybar.intents.customer_tickets import intent_customer_tickets
from skybar.intents.credit_activity import intent_credit_activity
from skybar.intents.credit_numbers import intent_rtn_summary
from skybar.intents.priority_tickets import intent_priority_tickets
from skybar.intents.credit_aging import intent_credit_aging
from skybar.intents.stalled_tickets import intent_stalled_tickets
from skybar.intents.overall_summary import intent_overall_summary
from skybar.intents.top_accounts import intent_top_accounts
from skybar.intents.top_items import intent_top_items
from skybar.intents.credit_trends import intent_credit_trends
from skybar.intents.credit_anomalies import intent_credit_anomalies


# Each intent can now return:
#  - None
#  - A string
#  - (string, dataframe)
IntentReturn = Union[None, str, Tuple[str, pd.DataFrame]]


# List of all intent handlers MiniTwin will try, in order
INTENTS: List[Callable[[str, pd.DataFrame], IntentReturn]] = [
    intent_ticket_requests,     # 🔥 NEW: show all entries for a ticket (must be BEFORE ticket_status)
    intent_ticket_status,       # Single-ticket summary
    intent_record_lookup,       # Ticket / invoice existence check
    intent_customer_tickets,
    intent_credit_activity,
    intent_rtn_summary,
    intent_priority_tickets,
    intent_credit_aging,
    intent_stalled_tickets,
    intent_overall_summary,
    intent_top_accounts,
    intent_top_items,
    intent_credit_trends,
    intent_credit_anomalies,
]


def skybar_answer(query: str, df: pd.DataFrame) -> Tuple[str, pd.DataFrame | None]:
    """
    MiniTwin core dispatcher.
    Returns:
        (text_response, optional_dataframe)
    """
    for intent in INTENTS:
        result = intent(query, df)

        # --- Intent returns (text, dataframe)
        if isinstance(result, tuple) and len(result) == 2:
            text, df_result = result
            return text, df_result

        # --- Intent returns only text
        if isinstance(result, str) and result.strip():
            return result, None

    # --- Fallback help message
    help_text = (
        "MiniTwin here 🤖 I didn't fully understand that request.\n\n"
        "Right now I can help you with:\n"
        "1. Ticket status — e.g. `MiniTwin, status on ticket R-048484`\n"
        "2. Ticket requests — e.g. `MiniTwin, show me all the requests for ticket R-040699`\n"
        "3. Record lookup — e.g. `MiniTwin, is ticket R-040699 logged in the system?`\n"
        "4. Customer history — e.g. `MiniTwin, show all tickets for customer YAM in last 30 days`\n"
        "5. Credit activity — e.g. `MiniTwin, how many credits did I update from Nov 1st to today?`\n"
        "6. Credits with RTN — e.g. `MiniTwin, how many credits have a credit number?`\n"
        "7. Priority tickets — e.g. `MiniTwin, what tickets are priority right now?`\n"
        "8. Credit aging — e.g. `MiniTwin, show the credit aging summary`\n"
        "9. Stalled tickets — e.g. `MiniTwin, which tickets haven't been updated in 7 days?`\n"
        "10. Overall overview — e.g. `MiniTwin, give me a credit overview`\n"
        "11. Top accounts — e.g. `MiniTwin, which accounts have the most credits?`\n"
        "12. Top items — e.g. `MiniTwin, which items have the most credits issued?`\n"
        "13. Credit trends — e.g. `MiniTwin, are there any credit trends worth sharing?`\n"
        "14. Anomalies — e.g. `MiniTwin, any unusual or suspicious credits lately?`\n"
    )

    return help_text, None
