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
st.set_page_config(page_title="Combined Chatbot", page_icon="🤖", layout="wide")
st.title("🤖 Combined Chatbot")
st.caption("Upload both Excel and SQL database to ask questions across both!")

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "combined_df" not in st.session_state:
    st.session_state.combined_df = None

# Sidebar
with st.sidebar:
    st.header("📁 Upload Files")

    # Excel upload
    st.subheader("📊 Step 1 — Upload Excel File")
    excel_file = st.file_uploader(
        "Choose Excel file",
        type=["xlsx", "xls", "csv"],
        key="excel"
    )

    # SQL upload
    st.subheader("🗄️ Step 2 — Upload SQL Database")
    sql_file = st.file_uploader(
        "Choose SQLite database file",
        type=["db", "sqlite", "sqlite3"],
        key="sql"
    )

    # Combine button
    if st.button("🔗 Combine Both Databases"):
        if excel_file and sql_file:
            # Read Excel
            if excel_file.name.endswith(".csv"):
                excel_df = pd.read_csv(excel_file)
            else:
                excel_df = pd.read_excel(excel_file)

            # Read SQL
            with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
                tmp.write(sql_file.read())
                tmp_path = tmp.name

            conn = sqlite3.connect(tmp_path)
            tables = pd.read_sql(
                "SELECT name FROM sqlite_master WHERE type='table'",
                conn
            )
            sql_df = pd.read_sql(
                f"SELECT * FROM {tables['name'][0]}",
                conn
            )
            conn.close()

            # Merge on employee_id
            if 'employee_id' in excel_df.columns and 'employee_id' in sql_df.columns:
                st.session_state.combined_df = pd.merge(
                    excel_df,
                    sql_df,
                    on="employee_id",
                    how="inner"
                )
                st.success("✅ Both databases combined successfully!")
                st.write(f"**Total Rows:** {st.session_state.combined_df.shape[0]}")
                st.write(f"**Total Columns:** {st.session_state.combined_df.shape[1]}")
                st.write("**Columns:**")
                for col in st.session_state.combined_df.columns:
                    st.write(f"- {col}")
            else:
                st.error("❌ Both files must have employee_id column to combine!")

    st.divider()
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# Show combined data
if st.session_state.combined_df is not None:
    with st.expander("👀 View Combined Data", expanded=False):
        st.dataframe(st.session_state.combined_df, use_container_width=True)

# Chat interface
st.subheader("💬 Chat")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask anything across both Excel and SQL data..."):
    if st.session_state.combined_df is None:
        st.warning("⚠️ Please upload both files and click Combine first!")
    else:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Convert combined dataframe to text
        data_summary = f"""
        This is a combined dataset from Excel and SQL database.
        Total rows: {st.session_state.combined_df.shape[0]}
        Columns: {list(st.session_state.combined_df.columns)}

        Excel columns: employee_id, department, base_salary, bonus, total_package, grade
        SQL columns: employee_id, name, role, location, join_date, status

        Here is the full combined data:
        {st.session_state.combined_df.to_string()}

        Basic statistics:
        {st.session_state.combined_df.describe().to_string()}
        """

        # Send to Groq
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {
                            "role": "system",
                            "content": f"""You are a helpful data analyst assistant.
                            You have access to a combined dataset from Excel and SQL database.
                            
                            {data_summary}
                            
                            Answer the user's questions based on this combined data.
                            You can now answer questions that need both salary info and employee details.
                            For example:
                            - Who has the highest salary? (salary from Excel + name from SQL)
                            - Show all Engineering employees with their names (dept from Excel + name from SQL)
                            - Which location has highest average salary? (location from SQL + salary from Excel)
                            Always be helpful and explain your answers clearly."""
                        },
                        *[{"role": m["role"], "content": m["content"]}
                          for m in st.session_state.messages]
                    ]
                )
                answer = response.choices[0].message.content
                st.markdown(answer)

        # Save response
        st.session_state.messages.append({"role": "assistant", "content": answer})
