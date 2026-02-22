import os
import sqlite3
import time
from datetime import datetime
from brain import brain_agent
from langchain_core.messages import HumanMessage
from db import get_connection

def run_due_reports():
    """
    In a real environment, this would be a CRON job.
    For this prototype, it fetches all active schedules and runs them immediately.
    """
    print("Checking for due reports...")
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, user_prompt FROM report_schedules WHERE is_active = 1")
    schedules = cursor.fetchall()
    
    for schedule_id, prompt in schedules:
        print(f"Processing schedule {schedule_id}: {prompt}")
        
        # Invoke the brain agent (using a specific thread for the scheduler so it has history, or a distinct one)
        # We'll use a specific thread ID so it can see past logs if we use persistent memory correctly.
        config = {"configurable": {"thread_id": "user_demo_123"}}
        initial_state = {
            "messages": [HumanMessage(content=prompt)],
            "image_paths": [],
            "intent": "GET_STRATEGY" # Force it to act as a strategist/analyzer
        }
        
        # Use stream to force it through graph
        events = brain_agent.stream(initial_state, config, stream_mode="updates")
        
        final_response = ""
        for event in events:
            for node_name, node_data in event.items():
                if "messages" in node_data and node_data["messages"]:
                    final_response += f"**[{node_name.upper()}]**\n{node_data['messages'][-1].content}\n\n"
        
        # Save report
        cursor.execute("INSERT INTO reports (schedule_id, content) VALUES (?, ?)", (schedule_id, final_response))
        
        # Update last run
        cursor.execute("UPDATE report_schedules SET last_run_at = ? WHERE id = ?", (datetime.now().isoformat(), schedule_id))
        
        print(f"Report {schedule_id} generated and saved.")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    run_due_reports()
