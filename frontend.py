import os
import tempfile

import pandas as pd
import streamlit as st
from langchain_core.messages import HumanMessage

from brain import brain_agent, memory
from db import get_connection
from demo_data import reset_demo, seed_sample_data

st.set_page_config(page_title="Ayurvedic Health Companion", page_icon="🌿", layout="wide")

# Shared demo space: every visitor talks to the same memory thread and database.
THREAD_ID = "user_demo_123"
CONFIG = {"configurable": {"thread_id": THREAD_ID}}
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_assets")
SAMPLE_MEAL = os.path.join(ASSETS, "sample_meal.jpg")
SAMPLE_SCALE = os.path.join(ASSETS, "sample_scale.jpg")

NODE_LABELS = {
    "router": "🧭 Router",
    "log_biometrics": "⚖️ Logger · Biometrics (Gemini Vision)",
    "log_meal": "🍛 Logger · Meal (Gemini Vision)",
    "strategist": "🌿 Strategist · Ayurveda RAG",
    "set_goal": "🎯 Goal Keeper",
    "general_chat": "💬 Companion",
    "brain_review": "🧠 Brain Review",
}

DEMOS = [
    {
        "key": "meal", "icon": "📸", "title": "Log a meal from a photo",
        "desc": "Gemini Vision identifies the dishes, estimates calories, saves it, then the Brain reviews it against Ayurvedic guidance.",
        "text": "Here is my lunch today, please log this meal.", "image": SAMPLE_MEAL,
    },
    {
        "key": "scale", "icon": "⚖️", "title": "Log smart-scale biometrics",
        "desc": "Extracts every metric from a scale-app screenshot (weight, body fat, BMR…) into the database.",
        "text": "Log my smart scale reading from this morning.", "image": SAMPLE_SCALE,
    },
    {
        "key": "goal", "icon": "🎯", "title": "Set a long-term goal",
        "desc": "Goals are persisted and injected into every future conversation.",
        "text": "I want to set a goal: lose 10 lbs before summer while keeping my Pitta balanced.", "image": None,
    },
    {
        "key": "advice", "icon": "🌿", "title": "Ask for Ayurvedic advice",
        "desc": "The Strategist retrieves passages from the Ayurveda knowledge base (RAG) and combines them with your goals.",
        "text": "Based on my goals, what should an ideal Pitta-balancing breakfast look like?", "image": None,
    },
]

SUGGESTIONS = [
    "What are my current goals?",
    "Which foods aggravate Pitta?",
    "How was my diet this week?",
    "Suggest a light dinner for tonight",
]

# ---------------------------------------------------------------- state
st.session_state.setdefault("chat", [])        # [{role, text, image, trace, replies}]
st.session_state.setdefault("pending", None)   # (text, image_path) queued by a button
st.session_state.setdefault("flash", None)


def queue(text, image=None):
    st.session_state.pending = (text, image)


def query_df(sql, params=()):
    conn = get_connection()
    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


def run_agent(text, image_path=None, live=None):
    """Streams the LangGraph agent; returns (trace, replies). Writes progress into `live` (st.status)."""
    content = [{"type": "text", "text": text}]
    if image_path:
        content.append({"type": "text", "text": f"\n[Attached Image: {os.path.basename(image_path)}]"})
    state = {"messages": [HumanMessage(content=content)], "image_paths": [image_path] if image_path else []}

    trace, replies = [], []
    for event in brain_agent.stream(state, CONFIG, stream_mode="updates"):
        for node, data in event.items():
            data = data or {}
            step = NODE_LABELS.get(node, node)
            if node == "router":
                step += f" → intent **{data.get('intent', '?')}**"
            trace.append(step)
            if live is not None:
                live.write(step)
            for msg in data.get("messages") or []:
                txt = msg.content if isinstance(msg.content, str) else msg.text
                replies.append((node, txt))
    return trace, replies


def render_turn(turn):
    with st.chat_message(turn["role"], avatar="🧑" if turn["role"] == "user" else "🌿"):
        if turn.get("text"):
            st.markdown(turn["text"])
        if turn.get("image"):
            st.image(turn["image"], width=220)
        if turn.get("trace"):
            with st.expander("Agent path: " + " → ".join(t.split(" ")[0] for t in turn["trace"]), expanded=False):
                for t in turn["trace"]:
                    st.markdown(f"- {t}")
        for node, reply in turn.get("replies", []):
            st.caption(NODE_LABELS.get(node, node))
            st.markdown(reply)


def process(text, image_path):
    user_turn = {"role": "user", "text": text, "image": image_path}
    st.session_state.chat.append(user_turn)
    render_turn(user_turn)
    with st.chat_message("assistant", avatar="🌿"):
        with st.status("Agents at work…", expanded=True) as live:
            try:
                trace, replies = run_agent(text, image_path, live)
                live.update(label="Done — " + " → ".join(t.split(" ")[0] for t in trace), state="complete", expanded=False)
            except Exception as e:  # surface model/API errors in the UI instead of a blank page
                live.update(label="Something went wrong", state="error")
                trace, replies = [], [("general_chat", f"⚠️ Error: `{e}`")]
    st.session_state.chat.append({"role": "assistant", "trace": trace, "replies": replies})
    st.rerun()


def graph_dot():
    g = brain_agent.get_graph()
    lines = ["digraph G {", "rankdir=TB;", 'node [shape=box, style="rounded,filled", fillcolor="#eef6ee", fontname="Helvetica"];']
    for nid in g.nodes:
        label = NODE_LABELS.get(nid, nid).replace('"', "")
        if nid in ("__start__", "__end__"):
            lines.append(f'"{nid}" [label="{nid.strip("_").upper()}", shape=oval, fillcolor="#dddddd"];')
        else:
            lines.append(f'"{nid}" [label="{label}"];')
    for e in g.edges:
        style = ', style=dashed' if e.conditional else ""
        lines.append(f'"{e.source}" -> "{e.target}" [color="#5b8c5a"{style}];')
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("🎛️ Demo controls")
    if st.button("📥 Load sample data", width="stretch",
                 help="Adds 2 weeks of weights and meals plus a sample goal so the dashboard has something to show."):
        st.session_state.flash = seed_sample_data()
        st.rerun()
    if st.button("🧹 Reset demo", width="stretch", type="secondary",
                 help="Deletes ALL logs, goals, reports and the agent's memory. Shared by everyone."):
        reset_demo(memory, THREAD_ID)
        st.session_state.chat = []
        st.session_state.flash = "Demo reset — everything is clean."
        st.rerun()
    if st.button("🗑️ Clear my chat view", width="stretch"):
        st.session_state.chat = []
        st.rerun()
    st.caption("ℹ️ This is a shared demo space: everyone sees the same data and agent memory.")

    st.divider()
    counts = {t: query_df(f"SELECT COUNT(*) AS n FROM {t}")["n"][0]
              for t in ("user_goals", "biometrics", "meals", "reports")}
    c1, c2 = st.columns(2)
    c1.metric("Goals", counts["user_goals"])
    c2.metric("Weigh-ins", counts["biometrics"])
    c1.metric("Meals", counts["meals"])
    c2.metric("Reports", counts["reports"])

# ---------------------------------------------------------------- header
st.title("🌿 Ayurvedic Health Companion")
st.markdown(
    "A multi-agent health coach built with **Gemini**, **LangGraph**, **ChromaDB** and **Streamlit**. "
    "Snap a meal or a scale reading, set goals, and get advice grounded in an Ayurvedic knowledge base."
)
if st.session_state.flash:
    st.success(st.session_state.flash)
    st.session_state.flash = None

tab_chat, tab_dash, tab_reports, tab_how, tab_raw = st.tabs(
    ["💬 Try it", "📊 Dashboard", "🗓️ Reports", "🧠 How it works", "🗄️ Raw data"]
)

# ---------------------------------------------------------------- chat / demo tab
with tab_chat:
    with st.expander("✨ **Guided demo — click any card to see a feature in action**",
                     expanded=not st.session_state.chat):
        cols = st.columns(len(DEMOS))
        for col, demo in zip(cols, DEMOS):
            with col.container(border=True, height=330):
                st.markdown(f"### {demo['icon']}\n**{demo['title']}**")
                if demo["image"] and os.path.exists(demo["image"]):
                    st.image(demo["image"], width="stretch")
                st.caption(demo["desc"])
                if st.button("▶ Try it", key=f"demo_{demo['key']}", type="primary", width="stretch"):
                    queue(demo["text"], demo["image"])
        st.caption("📊 Then open the **Dashboard** tab to see logged data, or **Reports** to generate an AI report.")

    for turn in st.session_state.chat:
        render_turn(turn)

    picked = st.pills("Try asking:", SUGGESTIONS, key=f"sugg_{len(st.session_state.chat)}")
    if picked:
        queue(picked)

    user = st.chat_input(
        "Ask for advice, set a goal, or attach 📎 a meal / scale photo…",
        accept_file=True, file_type=["jpg", "jpeg", "png"],
    )
    if user:
        image_path = None
        if user.files:
            f = user.files[0]
            image_path = os.path.join(tempfile.mkdtemp(), f.name)
            with open(image_path, "wb") as out:
                out.write(f.getbuffer())
        text = user.text or ("Please analyze this image." if image_path else "")
        if text:
            queue(text, image_path)

    if st.session_state.pending:
        text, image_path = st.session_state.pending
        st.session_state.pending = None
        process(text, image_path)

# ---------------------------------------------------------------- dashboard tab
with tab_dash:
    bio = query_df("SELECT * FROM biometrics ORDER BY timestamp")
    meals = query_df("SELECT timestamp, items, calories, notes FROM meals ORDER BY timestamp DESC")
    goals = query_df("SELECT id, goal, status, created_at FROM user_goals ORDER BY id DESC")

    if bio.empty and meals.empty and goals.empty:
        st.info("No data yet. Use **📥 Load sample data** in the sidebar, or try the guided demo in the **💬 Try it** tab.")
    else:
        m1, m2, m3, m4 = st.columns(4)
        if not bio.empty:
            latest, first = bio.iloc[-1], bio.iloc[0]
            m1.metric("Weight (lb)", f"{latest['weight_lb']:.1f}",
                      f"{latest['weight_lb'] - first['weight_lb']:+.1f} since first", delta_color="inverse")
            if pd.notna(latest["body_fat_percentage"]):
                m2.metric("Body fat", f"{latest['body_fat_percentage']:.1f}%",
                          f"{latest['body_fat_percentage'] - first['body_fat_percentage']:+.1f} pts", delta_color="inverse")
        if not meals.empty:
            m3.metric("Meals logged", len(meals))
            m4.metric("Avg kcal / meal", int(meals["calories"].mean()))

        st.subheader("🎯 Active goals")
        active = goals[goals["status"] == "Active"]
        if active.empty:
            st.caption("No goals yet — try *“I want to lose 10 lbs before summer”* in the chat.")
        for _, g in active.iterrows():
            gc1, gc2 = st.columns([6, 1])
            gc1.success(g["goal"])
            if gc2.button("✅ Achieved", key=f"goal_{g['id']}"):
                conn = get_connection()
                conn.execute("UPDATE user_goals SET status='Achieved' WHERE id=?", (int(g["id"]),))
                conn.commit()
                conn.close()
                st.rerun()

        if not bio.empty:
            bio["timestamp"] = pd.to_datetime(bio["timestamp"])
            c1, c2 = st.columns(2)
            c1.subheader("⚖️ Weight trend")
            c1.line_chart(bio.set_index("timestamp")["weight_lb"], height=250)
            c2.subheader("📉 Body fat %")
            c2.line_chart(bio.set_index("timestamp")["body_fat_percentage"], height=250)

        if not meals.empty:
            st.subheader("🍛 Recent meals")
            st.dataframe(meals.head(20), hide_index=True, width="stretch")

# ---------------------------------------------------------------- reports tab
with tab_reports:
    st.markdown("Reports are AI summaries generated by the agents over your logged data. "
                "Save a schedule, then click **Run now** (in production a cron job runs them automatically).")

    with st.form("new_schedule", border=True):
        st.subheader("➕ New report")
        fc1, fc2, fc3 = st.columns([4, 1, 1])
        prompt = fc1.text_input("What should the report cover?", "Summarize my meals and weight this week against my Ayurvedic goals")
        freq = fc2.selectbox("Frequency", ["Daily", "Weekly", "Monthly"])
        time_val = fc3.time_input("Run time")
        bc1, bc2 = st.columns(2)
        save = bc1.form_submit_button("💾 Save schedule", width="stretch")
        run_once = bc2.form_submit_button("⚡ Generate now", type="primary", width="stretch")

    def generate_report(schedule_id, report_prompt):
        with st.status(f"Generating: {report_prompt}", expanded=True) as live:
            trace, replies = run_agent(report_prompt, live=live)
            live.update(label="Report ready", state="complete", expanded=False)
        body = "\n\n".join(r for _, r in replies)
        conn = get_connection()
        conn.execute("INSERT INTO reports (schedule_id, content) VALUES (?, ?)", (schedule_id, body))
        if schedule_id:
            conn.execute("UPDATE report_schedules SET last_run_at = datetime('now') WHERE id = ?", (schedule_id,))
        conn.commit()
        conn.close()

    if save or run_once:
        sid = None
        if save:
            cron = {"Daily": f"{time_val.minute} {time_val.hour} * * *",
                    "Weekly": f"{time_val.minute} {time_val.hour} * * 0",
                    "Monthly": f"{time_val.minute} {time_val.hour} 1 * *"}[freq]
            conn = get_connection()
            sid = conn.execute("INSERT INTO report_schedules (user_prompt, cron_schedule) VALUES (?, ?)",
                               (prompt, cron)).lastrowid
            conn.commit()
            conn.close()
        if run_once:
            generate_report(sid, prompt)
        st.rerun()

    sched = query_df("SELECT id, user_prompt, cron_schedule, last_run_at FROM report_schedules ORDER BY id DESC")
    if not sched.empty:
        st.subheader("🗓️ Saved schedules")
        for _, s in sched.iterrows():
            sc1, sc2 = st.columns([6, 1])
            sc1.markdown(f"**{s['user_prompt']}**  \n`{s['cron_schedule']}` · last run: {s['last_run_at'] or 'never'}")
            if sc2.button("▶ Run now", key=f"run_{s['id']}"):
                generate_report(int(s["id"]), s["user_prompt"])
                st.rerun()

    st.subheader("📄 Generated reports")
    reps = query_df("SELECT id, generated_at, content FROM reports ORDER BY id DESC LIMIT 10")
    if reps.empty:
        st.caption("No reports yet — click **⚡ Generate now** above.")
    for i, r in reps.iterrows():
        with st.expander(f"Report #{r['id']} · {r['generated_at']}", expanded=(i == 0)):
            st.markdown(r["content"])

# ---------------------------------------------------------------- how it works tab
with tab_how:
    hc1, hc2 = st.columns([3, 2])
    with hc1:
        st.subheader("LangGraph agent flow")
        st.graphviz_chart(graph_dot(), width="stretch")
        st.caption("Dashed arrows are conditional routes chosen by the Router.")
    with hc2:
        st.subheader("Agents")
        st.markdown(
            "- **🧭 Router** – classifies intent (image + keywords, else Gemini structured output).\n"
            "- **⚖️/🍛 Logger** – Gemini Vision extracts biometrics or meal details into SQLite.\n"
            "- **🧠 Brain Review** – after a meal is logged, evaluates it against Ayurvedic strategy.\n"
            "- **🌿 Strategist** – RAG over `knowledge_base/` using ChromaDB + Gemini embeddings.\n"
            "- **🎯 Goal Keeper** – summarizes and persists long-term goals.\n"
            "- **💬 Companion** – empathetic chat with conversation memory and goal awareness."
        )
        st.subheader("Stack")
        st.markdown("Gemini (`gemini-pro-latest`, `gemini-embedding-001`) · LangGraph + SQLite checkpointer · "
                    "ChromaDB · SQLite · Streamlit")

# ---------------------------------------------------------------- raw data tab
with tab_raw:
    table = st.selectbox("Table", ["user_goals", "biometrics", "meals", "report_schedules", "reports"])
    df = query_df(f"SELECT * FROM {table} ORDER BY id DESC")
    if df.empty:
        st.info(f"`{table}` is empty.")
    else:
        st.dataframe(df, width="stretch", hide_index=True)
