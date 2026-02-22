import streamlit as st
import os
import tempfile
from langchain_core.messages import HumanMessage, AIMessage
from brain import brain_agent
import time
import pandas as pd
from db import get_connection

st.set_page_config(page_title="Health Companion", page_icon="🌿", layout="centered")

col1, col2 = st.columns([5, 1])
with col1:
    st.title("🌿 Ayurvedic Health Companion")
with col2:
    st.write("") # some spacing
    st.write("")
    with st.popover("⚙️ Settings"):
        st.subheader("Schedule New Report")
        with st.form("new_schedule_form"):
            prompt = st.text_input("Report Prompt", "Summarize today's meals against my strategy")
            freq = st.selectbox("Frequency", ["Daily", "Weekly", "Monthly"])
            time_val = st.time_input("Run Time")
            submitted = st.form_submit_button("Save Schedule")
            if submitted:
                # Basic conversion to cron
                cron = f"{time_val.minute} {time_val.hour} * * *"
                if freq == "Weekly":
                    cron = f"{time_val.minute} {time_val.hour} * * 0"
                elif freq == "Monthly":
                    cron = f"{time_val.minute} {time_val.hour} 1 * *"
                
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO report_schedules (user_prompt, cron_schedule) VALUES (?, ?)", (prompt, cron))
                conn.commit()
                conn.close()
                st.success("Schedule saved!")
                
        st.subheader("Saved Schedules")
        conn = get_connection()
        df_sched = pd.read_sql_query("SELECT id, user_prompt, cron_schedule FROM report_schedules", conn)
        conn.close()
        if not df_sched.empty:
            st.dataframe(df_sched, hide_index=True)
        else:
            st.info("No saved schedules yet.")

# Use Streamlit tabs to separate Chat and Database views
tab_chat, tab_data = st.tabs(["💬 Chat Companion", "🗄️ Raw Database Explorer"])

with tab_chat:
    st.markdown("Upload a photo of your smart scale (biometrics) or your meal, or just ask for advice based on your history.")

    # Initialize chat history and thread ID
if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    # Use a static thread ID for the user session to test persistent memory
    st.session_state.thread_id = "user_demo_123"

for msg in st.session_state.messages:
    if isinstance(msg, HumanMessage):
        with st.chat_message("user"):
            st.write(msg.content)
            # We don't replay images in the UI strictly for simplicity here, but we could
    elif isinstance(msg, AIMessage):
        with st.chat_message("assistant"):
            st.write(msg.content)

# Use columns for explicit scheduling options
with st.sidebar:
    st.header("🗂️ Generated Reports")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, generated_at, content FROM reports ORDER BY generated_at DESC LIMIT 5")
    reports = cursor.fetchall()
    conn.close()
    
    if reports:
        for rid, created_at, content in reports:
            with st.expander(f"Report: {created_at}"):
                st.write(content)
    else:
        st.info("No reports generated yet. Run scheduler.py to generate them.")

    st.markdown("---")
    st.markdown("### Agent Architecture")
    if os.path.exists("brain_graph.png"):
        st.image("brain_graph.png", caption="LangGraph State Diagram")

user_input = st.chat_input("Ask for advice or describe your meal...")
uploaded_file = st.file_uploader("Upload Image (Optional)", type=["jpg", "jpeg", "png"])

if user_input or uploaded_file:
    # Build the state inputs
    image_paths = []
    content_list = []
    
    if user_input:
        content_list.append({"type": "text", "text": user_input})
    else:
        # Provide default text if only an image is uploaded
        content_list.append({"type": "text", "text": "Please analyze this image."})
        user_input = "Uploaded an Image."

    if uploaded_file:
        # Save to temp file
        temp_dir = tempfile.mkdtemp()
        path = os.path.join(temp_dir, uploaded_file.name)
        with open(path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        image_paths.append(path)
        content_list.append({"type": "text", "text": f"\n[Attached Image: {uploaded_file.name}]"})
        
        # Display user message instantly
        st.session_state.messages.append(HumanMessage(content=user_input))
        with st.chat_message("user"):
            st.write(user_input)
            if uploaded_file:
                st.image(uploaded_file, width=200)

        # We send the inputs to LangGraph
        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        
        new_message = HumanMessage(content=content_list)
        initial_state = {
            "messages": [new_message],
            "image_paths": image_paths
        }
        
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            with st.spinner("Brain Agent processing..."):
                events = brain_agent.stream(initial_state, config, stream_mode="updates")
                final_response = ""
                for event in events:
                    for node_name, node_data in event.items():
                        if node_data and "messages" in node_data and node_data["messages"]:
                            node_resp = node_data["messages"][-1].content
                            st.write(f"**[{node_name.upper()}]**:\n{node_resp}")
                            final_response += f"\n\n**[{node_name.upper()}]**:\n{node_resp}"
                
                st.session_state.messages.append(AIMessage(content=final_response))

# --- Database Explorer Tab ---
with tab_data:
    st.header("🗄️ SQLite Database Explorer")
    st.markdown("View all raw tables directly from `health_companion.db` without writing SQL.")
    
    conn = get_connection()
    tables_to_view = ["user_goals", "biometrics", "meals", "report_schedules", "reports"]
    
    selected_table = st.selectbox("Select a Table to View", tables_to_view)
    
    if selected_table:
        try:
            # Load the table into a Pandas DataFrame
            query = f"SELECT * FROM {selected_table} ORDER BY id DESC"
            df = pd.read_sql_query(query, conn)
            
            if df.empty:
                st.info(f"The `{selected_table}` table is currently empty.")
            else:
                st.dataframe(df, use_container_width=True)
                
                # Show some basic stats if relevant
                if selected_table == "biometrics":
                    st.line_chart(df.set_index("timestamp")["weight_lb"])
        except Exception as e:
            st.error(f"Error loading table: {e}")
            
    conn.close()
