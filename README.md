# 🌿 Ayurvedic Health Companion

An intelligent, multi-agent AI system built to provide highly personalized, proactive Ayurvedic health advice based on your daily biometrics and diet. 

Powered by Google Gemini 2.5 Pro, LangGraph, ChromaDB, and Streamlit.

## ✨ Features
- **Visual Log Ingestion**: Upload photos of your smart scale or your meals. The `Logger Agent` uses Gemini Vision to automatically extract caloric count and full biometric tables directly into a local SQLite database. 
- **Ayurvedic Knowledge Base (RAG)**: The `Strategist Agent` reads any text or PDF documents placed in the `/knowledge_base/` folder and chunks/embeds them using ChromaDB, acting as your local Ayurvedic textbook to cross-reference your personal data against. 
- **Event-Driven Orchestrator**: The central `Brain Agent` manages conversational memory across sessions and leverages LangGraph StateGraphs to route your intents to the correct nodes without relying on unpredictable LLM loops. 
- **Persistent Goal Tracking**: You can formally declare long-term health goals (e.g. "I want to lose 10 lbs before summer"), which are instantly persisted into `health_companion.db` and injected into the Brain Agent's persona for constant awareness.
- **Dynamic Scheduled Reporting**: A complete internal chron scheduler. Users can define custom prompts ("Summarize my meals over the last 3 days against my Ayurvedic goals") and schedule an automated backend script to generate reports offline.
- **Database Explorer UI**: Easily visualize and inspect your raw Biometrics, Meals, Goals, and Reports tables right in the browser using the built-in Pandas dashboard. 

## 🚀 Getting Started

1. **Clone the repository:**
   ```bash
   git clone https://github.com/arasam23/health-companion.git
   cd health-companion
   ```

2. **Setup your environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure API Keys:**
   Create a `.env` file in the root directory based on `.env.example` and add your Google Gemini API Key.
   ```
   GEMINI_API_KEY="your_api_key_here"
   ```

4. **Initialize your Local Vector DB:**
   Run the strategist agent once standalone to chunk and embed any texts/PDFs placed in the `/knowledge_base/` folder.
   ```bash
   python strategist.py
   ```

5. **Start the Frontend UI:**
   ```bash
   streamlit run frontend.py
   ```

## 📂 Architecture Stack
* **LLM Engine**: `langchain-google-genai` (Gemini 2.5 Pro / Gemini Embeddings 001)
* **Agentic Control**: `langgraph`
* **Local RAG DB**: `chromadb`
* **Data Persistence**: `sqlite3` + `sqlalchemy`
* **Frontend UI**: `streamlit` + `pandas`

## 📡 Automated Reports Setup
If you would like the application to run the scheduled reports autonomously in the background, simply run the standalone background script. (Recommended to deploy this script via GCP Cloud Scheduler in production):
```bash
python scheduler.py
```
