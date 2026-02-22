import os
from dotenv import load_dotenv
from typing import TypedDict, Optional, List, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
from pydantic import BaseModel, Field

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

# Import our agents
from logger import extract_biometrics, extract_meal, log_biometrics, log_meal
from strategist import generate_strategy

load_dotenv()

# Setup GenAI model
LLM_MODEL = "gemini-2.5-pro"
llm = ChatGoogleGenerativeAI(model=LLM_MODEL, temperature=0)

# --- Define the State Schema ---
class AgentState(TypedDict):
    messages: List[BaseMessage]
    image_paths: List[str]
    intent: Optional[str] # "LOG_BIOMETRICS", "LOG_MEAL", "GET_STRATEGY", "CHAT", "SET_GOAL"
    recent_logs: List[str]
    report_requested: bool

# --- Helper DB functions ---
def get_active_goals() -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT goal FROM user_goals WHERE status = 'Active'")
    goals = cursor.fetchall()
    conn.close()
    if not goals:
        return "No active long-term goals set yet."
    return "\n".join([f"- {g[0]}" for g in goals])

def save_goal(goal: str) -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO user_goals (goal) VALUES (?)", (goal,))
    conn.commit()
    conn.close()
    return "Goal saved successfully."

# --- Router Node ---
class IntentOutput(BaseModel):
    intent: str = Field(description="The user's intent. Must be exactly one of: 'LOG_BIOMETRICS', 'LOG_MEAL', 'GET_STRATEGY', 'CHAT', 'SET_GOAL'")

def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        return " ".join([item["text"] for item in content if isinstance(item, dict) and item.get("type") == "text"])
    return str(content)

def route_conversation(state: AgentState) -> dict:
    """Classifies the user's intent to route to the correct agent node."""
    messages = state["messages"]
    if not messages:
        return {"intent": "CHAT"}
        
    last_message = _extract_text(messages[-1].content)
    has_image = len(state.get("image_paths", [])) > 0
    
    # Simple rule-based routing to start
    if has_image:
        if "food" in str(last_message).lower() or "meal" in str(last_message).lower() or "eat" in str(last_message).lower() or "dinner" in str(last_message).lower() or "lunch" in str(last_message).lower() or "breakfast" in str(last_message).lower():
            return {"intent": "LOG_MEAL"}
        else:
            return {"intent": "LOG_BIOMETRICS"}
            
    # Or use LLM to classify intent
    structured_llm = llm.with_structured_output(IntentOutput)
    prompt = f"Analyze the following user input and determine their intent.\nInput: {last_message}"
    try:
        classification = structured_llm.invoke(prompt)
        intent = classification.intent
    except Exception:
        intent = "CHAT"
        
    return {"intent": intent}

# --- Action Nodes ---
def logger_biometrics_node(state: AgentState) -> dict:
    """Extracts and logs biometric data from images."""
    if not state.get("image_paths"):
        return {"messages": [AIMessage(content="I need an image to log biometrics.")]}
        
    image_path = state["image_paths"][0]
    result = extract_biometrics(image_path)
    
    if result:
        db_msg = log_biometrics(result)
        message = f"Successfully extracted your biometrics!\nWeight: {result.weight_lb} lbs, Body Fat: {result.body_fat_percentage}%\nDB Status: {db_msg}"
        return {
            "messages": [AIMessage(content=message)],
            "recent_logs": state.get("recent_logs", []) + [f"Biometrics: Weight {result.weight_lb}, Body Fat {result.body_fat_percentage}"]
        }
    else:
        return {"messages": [AIMessage(content="Failed to extract biometrics from the image. Please try again.")]}

def logger_meal_node(state: AgentState) -> dict:
    """Extracts and logs meal data from images."""
    if not state.get("image_paths"):
        return {"messages": [AIMessage(content="I need an image to log a meal.")]}
        
    image_path = state["image_paths"][0]
    result = extract_meal(image_path)
    
    if result:
        db_msg = log_meal(result)
        message = f"Successfully extracted your meal!\nItems: {result.items}\nEstimated Calories: {result.calories} kcal\nDB Status: {db_msg}"
        return {
            "messages": [AIMessage(content=message)],
            "recent_logs": state.get("recent_logs", []) + [f"Meal: {result.items} ({result.calories} kcal)"]
        }
    else:
        return {"messages": [AIMessage(content="Failed to extract meal details from the image. Please try again.")]}

def strategist_node(state: AgentState) -> dict:
    """Generates health advice using RAG and context."""
    user_query = _extract_text(state["messages"][-1].content)
    recent_context = "\n".join(state.get("recent_logs", []))
    active_goals = get_active_goals()
    
    strategy = generate_strategy(user_query, user_context=f"Active User Goals:\n{active_goals}\n\nRecent logs:\n{recent_context}")
    return {"messages": [AIMessage(content=strategy)]}

def set_goal_node(state: AgentState) -> dict:
    """Extracts a goal from the user query and saves it to the database."""
    user_query = _extract_text(state["messages"][-1].content)
    
    # We can ask the LLM to summarize the goal nicely before saving
    summary_prompt = f"Summarize the core health goal the user is trying to set based on this input: '{user_query}'"
    goal_summary = llm.invoke([HumanMessage(content=summary_prompt)]).content
    
    save_goal(goal_summary)
    
    return {"messages": [AIMessage(content=f"I have successfully recorded your long-term goal: **{goal_summary}**.\n\nI will keep this in my permanent persistent memory and ensure our future strategies align with it!")]}

from langchain_core.messages import SystemMessage

def general_chat_node(state: AgentState) -> dict:
    """Handles general chit-chat and fallback using full conversation history."""
    # Build a persona system message
    active_goals = get_active_goals()
    system_prompt = f"""You are a persistent, empathetic, and intelligent Health Companion. 
    Unlike a standard stateless AI, you HAVE persistent long-term memory via a database. 
    You are aware of the user's specific long-term goals below and must help them achieve them.
    
    User's Active Goals:
    {active_goals}
    
    Always act as a supportive companion who remembers their journey. Feel free to reference their goals."""
    
    # Pass the full chat history up to the last 10 messages so context window isn't blown, plus the system prompt
    chat_history = state["messages"][-10:]
    payload = [SystemMessage(content=system_prompt)] + chat_history
    
    response = llm.invoke(payload)
    return {"messages": [response]}

def brain_review_node(state: AgentState) -> dict:
    """Evaluates the logged meal against the Ayurvedic strategy."""
    last_message = _extract_text(state["messages"][-1].content)
    # Simple check if the last node was the logger
    if "Successfully extracted your meal" in last_message:
        eval_query = "A meal was just logged. Please evaluate it against my Ayurvedic guidelines. Is this meal aligned with my strategy? If not, what should I do to recover?"
        recent_context = "\n".join(state.get("recent_logs", []))
        evaluation = generate_strategy(eval_query, user_context=f"Recent events:\n{recent_context}")
        
        return {"messages": [AIMessage(content=evaluation)]}
    return {}

# --- Edge Logic ---
def get_next_node(state: AgentState) -> str:
    intent = state.get("intent", "CHAT")
    if intent == "LOG_BIOMETRICS":
        return "log_biometrics"
    elif intent == "LOG_MEAL":
        return "log_meal"
    elif intent == "GET_STRATEGY":
        return "strategist"
    elif intent == "SET_GOAL":
        return "set_goal"
    else:
        return "general_chat"

# --- Building the Graph ---
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("router", route_conversation)
workflow.add_node("log_biometrics", logger_biometrics_node)
workflow.add_node("log_meal", logger_meal_node)
workflow.add_node("strategist", strategist_node)
workflow.add_node("set_goal", set_goal_node)
workflow.add_node("general_chat", general_chat_node)
workflow.add_node("brain_review", brain_review_node)

# Set entry point
workflow.set_entry_point("router")

# Add conditional routing
workflow.add_conditional_edges(
    "router",
    get_next_node,
    {
        "log_biometrics": "log_biometrics",
        "log_meal": "log_meal",
        "strategist": "strategist",
        "set_goal": "set_goal",
        "general_chat": "general_chat"
    }
)

# After logging, go to brain review
workflow.add_edge("log_biometrics", "brain_review")
workflow.add_edge("log_meal", "brain_review")

# The others go straight to END
workflow.add_edge("strategist", END)
workflow.add_edge("set_goal", END)
workflow.add_edge("general_chat", END)
workflow.add_edge("brain_review", END)

# Compile graph with SQL checkpointer
conn = sqlite3.connect("health_companion_graph.db", check_same_thread=False)
memory = SqliteSaver(conn)
brain_agent = workflow.compile(checkpointer=memory)

if __name__ == "__main__":
    print("Brain Agent LangGraph compiled successfully.")
    # Export graph image to verify
    try:
        image_data = brain_agent.get_graph().draw_mermaid_png()
        with open("brain_graph.png", "wb") as f:
            f.write(image_data)
        print("Exported graph visualization to brain_graph.png")
    except Exception as e:
        print(f"Failed to generate diagram: {e}")
