import streamlit as st
import pandas as pd
import sqlite3
from groq import Groq
from dotenv import load_dotenv
import os
import tempfile

# Load API key
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Page config
st.set_page_config(page_title="SQL Chatbot", page_icon="🗄️", layout="wide")
st.title("🗄️ SQL Chatbot")
st.caption("Upload your SQLite database and ask anything about your data!")

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "df" not in st.session_state:
    st.session_state.df = None
if "tables" not in st.session_state:
    st.session_state.tables = []

# Sidebar
with st.sidebar:
    st.header("📁 Upload SQL Database")
    uploaded_file = st.file_uploader(
        "Choose your SQLite database file",
        type=["db", "sqlite", "sqlite3"]
    )

    if uploaded_file:
        # Save uploaded file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        # Connect to database
        conn = sqlite3.connect(tmp_path)

        # Get all tables
        tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)
        st.session_state.tables = tables['name'].tolist()

        # Read all tables into one dataframe
        dfs = []
        for table in st.session_state.tables:
            df = pd.read_sql(f"SELECT * FROM {table}", conn)
            df['_table'] = table
            dfs.append(df)

        st.session_state.df = pd.concat(dfs, ignore_index=True)
        conn.close()

        st.success(f"✅ Database loaded!")
        st.write(f"**Tables found:** {len(st.session_state.tables)}")
        for table in st.session_state.tables:
            st.write(f"- {table}")
        st.write(f"**Total Rows:** {st.session_state.df.shape[0]}")
        st.write(f"**Columns:** {st.session_state.df.shape[1]}")

    st.divider()
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# Show data table
if st.session_state.df is not None:
    with st.expander("👀 View your data", expanded=False):
        st.dataframe(st.session_state.df, use_container_width=True)

# Chat interface
st.subheader("💬 Chat")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask anything about your SQL database..."):
    if st.session_state.df is None:
        st.warning("⚠️ Please upload a database file first!")
    else:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Convert dataframe to text
        data_summary = f"""
        The database has the following tables: {st.session_state.tables}
        Total rows: {st.session_state.df.shape[0]}
        Columns: {list(st.session_state.df.columns)}

        Here is the full data:
        {st.session_state.df.to_string()}

        Basic statistics:
        {st.session_state.df.describe().to_string()}
        """

        # Send to Groq
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {
                            "role": "system",
                            "content": f"""You are a helpful SQL data analyst assistant.
                            You have access to a SQLite database with the following data:
                            {data_summary}
                            Answer the user's questions based on this data clearly and concisely.
                            If they ask for calculations, do them accurately.
                            If they ask to filter data, show the relevant rows.
                            Always be helpful and explain your answers."""
                        },
                        *[{"role": m["role"], "content": m["content"]}
                          for m in st.session_state.messages]
                    ]
                )
                answer = response.choices[0].message.content
                st.markdown(answer)

        # Save response
        st.session_state.messages.append({"role": "assistant", "content": answer})