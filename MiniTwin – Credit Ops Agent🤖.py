import streamlit as st
import pandas as pd

from skybar.intent_router import skybar_answer

st.set_page_config(
    page_title="MiniTwin – Credit Ops Agent",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 MiniTwin – Credit Operations Agent")
st.markdown(
    "Upload your **credit export CSV** and ask questions like:\n"
    "- `MiniTwin, give me a credit overview`\n"
    "- `MiniTwin, what tickets are priority right now?`\n"
    "- `MiniTwin, show the credit aging summary`\n"
    "- `MiniTwin, any unusual or suspicious credits lately?`\n"
)


# -------------------------
# 1. Data loader
# -------------------------
with st.sidebar:
    st.header("📂 Data")
    uploaded_file = st.file_uploader("Upload credit CSV", type=["csv"])

    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
        except UnicodeDecodeError:
            df = pd.read_csv(uploaded_file, encoding="latin-1")

        st.session_state["df"] = df
        st.success(f"Loaded {len(df):,} rows.")
        if st.checkbox("Show sample data"):
            st.dataframe(df.head(50))
    else:
        st.info("Upload a CSV to start.")


# If no data, stop here
if "df" not in st.session_state:
    st.stop()

df = st.session_state["df"]


# -------------------------
# 2. Simple chat interface
# -------------------------
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

    st.session_state["history"].append(
        {"role": "user", "content": query}
    )
    st.session_state["history"].append(
        {"role": "assistant", "content": answer}
    )

# Show history
for msg in st.session_state["history"]:
    if msg["role"] == "user":
        st.markdown(f"**You:** {msg['content']}")
    else:
        st.markdown(f"**MiniTwin:**\n\n{msg['content']}")
        st.markdown("---")
