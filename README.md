# 🚨 IncidentIQ — AI-Powered DevOps Incident Commander

> Paste a stack trace. Get root cause analysis, fix suggestions, and runbook-matched resolutions — in seconds.

## 🎯 Problem

Production incidents cost an average of **$5,600 per minute** in downtime. Engineers spend 40-70% of incident time searching logs, docs, Stack Overflow, and Slack channels instead of fixing the issue.

## 💡 Solution

**IncidentIQ** is a LangGraph-powered multi-tool agent that investigates production incidents autonomously — parsing logs, searching runbooks, researching the web, and generating structured Root Cause Analysis reports.

## 🏗️ Architecture (LangGraph StateGraph)

```
┌───────────────────────────────────────────────────────────┐
│                      Streamlit UI                          │
│        (Chat Input → Real-time Agent Stream → RCA)         │
├───────────────────────────────────────────────────────────┤
│              LangGraph StateGraph (ReAct)                   │
│                                                             │
│   START → [Agent Node] → tools_condition?                   │
│               ↓ yes              ↓ no                       │
│         [Tools Node]             END                        │
│               ↓                                             │
│         [Agent Node] ← loop back                            │
│                                                             │
│   State: MessagesState (full conversation history)          │
│   Checkpointer: MemorySaver (thread persistence)            │
├──────────┬──────────┬───────────┬──────────┬───────────────┤
│  Log     │ Runbook  │ Web       │ Stack    │ Incident      │
│ Analyzer │ RAG      │ Search    │ Overflow │ Memory        │
│ (regex+  │(ChromaDB)│ (Tavily)  │ (Serper) │ (SQLite+      │
│  patterns│          │           │          │  ChromaDB)    │
├──────────┴──────────┴───────────┴──────────┴───────────────┤
│               OpenRouter LLM (GPT-4o / Claude)              │
├───────────────────────────────────────────────────────────┤
│                   LangSmith Observability                    │
└───────────────────────────────────────────────────────────┘
```

### Why LangGraph over LangChain AgentExecutor?

| Feature | AgentExecutor (old) | LangGraph (our choice) |
|---------|-------------------|----------------------|
| Architecture | Black-box loop | Explicit state graph |
| State Management | Limited | Full MessagesState with checkpointer |
| Streaming | Basic callbacks | Native `stream_mode="updates"` |
| Visualization | None | Mermaid graph export |
| Debugging | Opaque | Node-by-node tracing via LangSmith |
| Industry Status | Deprecated | Recommended by LangChain |

## 🚀 Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/YOUR_USERNAME/incidentiq.git
cd incidentiq
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure API Keys
```bash
cp .env.example .env
# Edit .env with your API keys
```

| Service | Purpose | Get Key |
|---------|---------|---------|
| OpenRouter | LLM access (GPT-4o) | [openrouter.ai/keys](https://openrouter.ai/keys) |
| OpenAI | Embeddings | [platform.openai.com](https://platform.openai.com/api-keys) |
| Tavily | Web search | [tavily.com](https://tavily.com) — Free: 1000/mo |
| Serper | Google search | [serper.dev](https://serper.dev) — Free: 2500 |
| LangSmith | Agent tracing | [smith.langchain.com](https://smith.langchain.com) |

### 3. Run
```bash
streamlit run app.py
```

### 4. Demo
1. Click **"Load Sample Runbooks"** in the sidebar
2. Select a sample error scenario from **"Sample Scenarios"** tab
3. Click **"Investigate Incident"**
4. Watch the agent reason and call tools in real-time!

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **LangGraph Agent** | StateGraph with ReAct pattern, ToolNode, and MemorySaver |
| **Smart Log Parsing** | Auto-detects language, error type, severity from raw logs |
| **Real-time Streaming** | Watch agent tool calls and reasoning live via `stream_mode` |
| **Runbook RAG** | Upload team docs — ChromaDB semantic search retrieval |
| **Structured RCA** | Root cause, confidence score, evidence, remediation steps |
| **Incident Memory** | Stores past incidents, finds similar issues |
| **LangSmith Traces** | Full node-by-node execution trace |
| **Graph Visualization** | Mermaid diagram of the agent workflow |

## 🛠️ Tech Stack

- **Agent Framework:** LangGraph (StateGraph, ToolNode, MemorySaver)
- **LLM:** OpenRouter (GPT-4o, Claude, Gemini)
- **Search:** Tavily + Serper
- **Vector DB:** ChromaDB
- **Embeddings:** OpenAI text-embedding-3-small
- **Observability:** LangSmith
- **Frontend:** Streamlit
- **Storage:** SQLite + ChromaDB

## 📁 Project Structure

```
incidentiq/
├── app.py                    # Streamlit UI with LangGraph streaming
├── agent.py                  # LangGraph StateGraph + ReAct agent
├── config.py                 # Configuration & API keys
├── requirements.txt          # Dependencies (includes langgraph)
├── .env.example              # API key template
├── tools/
│   ├── log_analyzer.py       # Stack trace parsing tool
│   ├── web_search.py         # Tavily + Serper dual search
│   ├── runbook_rag.py        # ChromaDB RAG tool
│   └── incident_memory.py    # Past incident matching
├── utils/
│   └── streamlit_callback.py # Real-time stream event renderer
└── data/
    ├── sample_logs.py        # 4 demo error scenarios
    └── sample_runbooks/      # Sample runbook documents
```

## 👤 Author

**[Your Name]** — Senior Software Development Engineer (12+ years)

## 📜 License

MIT
