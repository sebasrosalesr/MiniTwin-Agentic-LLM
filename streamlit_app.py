import streamlit as st
import pandas as pd
from dateutil.parser import parse as dtparse

import firebase_admin
from firebase_admin import credentials, db

from skybar.intent_router import skybar_answer

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(
    page_title="MiniTwin – Credit Ops Agent",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 MiniTwin – Credit Operations Agent")
st.caption(
    "Ask things like:\n"
    "- `MiniTwin, give me a credit overview`\n"
    "- `MiniTwin, what tickets are priority right now?`\n"
    "- `MiniTwin, show the credit aging summary`\n"
    "- `MiniTwin, any unusual or suspicious credits lately?`\n"
)

# -------------------------------------------------
# Firebase init + data loader
# -------------------------------------------------
def init_firebase():
    firebase_config = dict(st.secrets["firebase"])
    # fix escaped newlines in private key
    if "private_key" in firebase_config and "\\n" in firebase_config["private_key"]:
        firebase_config["private_key"] = firebase_config["private_key"].replace("\\n", "\n")

    cred = credentials.Certificate(firebase_config)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            cred,
            {"databaseURL": "https://creditapp-tm-default-rtdb.firebaseio.com/"},
        )
    return True


def safe_parse_force_string(x):
    try:
        return pd.to_datetime(dtparse(str(x), fuzzy=True))
    except Exception:
        return pd.NaT


@st.cache_data(show_spinner=True, ttl=120)
def load_data():
    cols = [
        "Record ID",
        "Ticket Number",
        "Requested By",
        "Sales Rep",
        "Issue Type",
        "Date",
        "Status",
        "RTN_CR_No",
        "Customer Number",
        "Item Number",
        "Credit Request Total",
    ]
    ref = db.reference("credit_requests")
    raw = ref.get() or {}

    df_ = pd.DataFrame([{c: v.get(c, None) for c in cols} for v in raw.values()])

    # dates
    df_["Date"] = df_["Date"].apply(safe_parse_force_string)
    df_ = df_.dropna(subset=["Date"]).copy()

    if pd.api.types.is_datetime64_any_dtype(df_["Date"]):
        try:
            df_["Date"] = df_["Date"].dt.tz_localize(None)
        except Exception:
            pass

    return df_


# init Firebase + load once
init_firebase()
if "df" not in st.session_state:
    st.session_state["df"] = load_data()

df = st.session_state["df"]

# Sidebar: data info
with st.sidebar:
    st.header("📂 Data from Firebase")
    st.write(f"Rows loaded: **{len(df):,}**")
    if st.checkbox("Show sample data"):
        st.dataframe(df.head(50), use_container_width=True)

# -------------------------------------------------
# MiniTwin chat interface
# -------------------------------------------------
if "history" not in st.session_state:
    st.session_state["history"] = []

st.subheader("💬 Ask MiniTwin")

query = st.text_input(
    "Type a question for MiniTwin:",
    placeholder="e.g. MiniTwin, give me a credit overview",
)

col1, col2 = st.columns([1, 5])
with col1:
    run_btn = st.button("Ask MiniTwin")

if run_btn and query.strip():
    try:
        answer = skybar_answer(query, df)
    except Exception as e:
        answer = f"⚠️ Error while processing your request:\n\n`{e}`"

    st.session_state["history"].append({"role": "user", "content": query})
    st.session_state["history"].append({"role": "assistant", "content": answer})

# Show history
for msg in st.session_state["history"]:
    if msg["role"] == "user":
        st.markdown(f"**You:** {msg['content']}")
    else:
        st.markdown(f"**MiniTwin:**\n\n{msg['content']}")
        st.markdown("---")

if run_btn and query.strip():
    try:
        text, df_result = skybar_answer(query, df)
    except Exception as e:
        st.session_state["history"].append({
            "role": "assistant",
            "content": f"⚠️ Error while processing your request:\n\n`{e}`"
        })
        df_result = None
        text = None

    # Store text response for chat
    st.session_state["history"].append({
        "role": "user",
        "content": query,
    })

    st.session_state["history"].append({
        "role": "assistant",
        "content": text,
    })

    # Store result dataframe separately
    if df_result is not None:
        st.session_state["last_df"] = df_result
    else:
        st.session_state["last_df"] = None


# ----- RENDER HISTORY -----
for msg in st.session_state["history"]:
    if msg["role"] == "user":
        st.markdown(f"**You:** {msg['content']}")
    else:
        st.markdown(f"**MiniTwin:**\n\n{msg['content']}")
        st.markdown("---")

# ----- SHOW DATAFRAME + EXPORT BUTTON -----
if st.session_state.get("last_df") is not None:
    df_to_show = st.session_state["last_df"]

    st.subheader("📄 Matching Entries")
    st.dataframe(df_to_show, use_container_width=True)

    csv = df_to_show.to_csv(index=False)
    st.download_button(
        "⬇️ Download results as CSV",
        data=csv,
        mime="text/csv",
        file_name="minitwin_results.csv"
    )
