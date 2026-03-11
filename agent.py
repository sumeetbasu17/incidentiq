"""
IncidentIQ - LangGraph ReAct Agent
The core reasoning engine using LangGraph's StateGraph for
stateful, graph-based incident investigation.

Architecture:
    ┌─────────┐
    │  START   │
    └────┬─────┘
         ▼
    ┌─────────────┐
    │  agent_node  │◄──────────────┐
    │  (LLM call)  │               │
    └────┬─────────┘               │
         ▼                         │
    ┌─────────────┐          ┌─────┴──────┐
    │ should_cont? │──tools──▶│ tools_node │
    └────┬─────────┘          └────────────┘
         │ end
         ▼
    ┌─────────┐
    │   END   │
    └─────────┘
"""

import os
import json
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import StateGraph, END, START, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from config import Config
from tools.log_analyzer import analyze_log
from tools.web_search import search_web, search_stackoverflow
from tools.runbook_rag import search_runbooks
from tools.incident_memory import find_similar_incidents


# ──────────────────────────────────────────────
# System Prompt
# ──────────────────────────────────────────────
SYSTEM_PROMPT = """You are IncidentIQ, an elite DevOps Incident Commander AI Agent with deep expertise 
in production systems, distributed architectures, and incident response.

Your mission: Analyze production incidents and provide actionable Root Cause Analysis (RCA) 
with remediation steps — like a senior SRE who never sleeps.

## Your Investigation Process

1. **ANALYZE the log/error first** — Always use the `analyze_log` tool first to parse the raw input 
   and extract structured information (error type, language, severity, services, stack frames).

2. **SEARCH internal runbooks** — Use `search_runbooks` to check if there are any relevant 
   internal procedures, past documentation, or known-issues guides for this type of error.

3. **CHECK incident memory** — Use `find_similar_incidents` to see if a similar incident 
   has occurred before and how it was resolved.

4. **RESEARCH the web** — Use `search_web` or `search_stackoverflow` to find community solutions, 
   known bugs, library issues, and best practices for this specific error.

5. **SYNTHESIZE your findings** into a structured RCA report.

## Output Format

After completing your investigation, provide a structured RCA in this EXACT format:

---

## 🔍 Incident Analysis Report

### Summary
[One paragraph summary of what happened]

### Severity: [CRITICAL/HIGH/MEDIUM/LOW]
### Affected Service(s): [service names]
### Error Type: [specific error]

### 📊 Root Cause Analysis
**Root Cause:** [Clear explanation of why this happened]
**Confidence:** [HIGH/MEDIUM/LOW] — based on evidence strength

**Evidence:**
1. [Evidence from log analysis]
2. [Evidence from runbooks/past incidents]  
3. [Evidence from web research]

### 🛠️ Remediation Steps
1. **Immediate Fix:** [Step-by-step commands/actions to resolve NOW]
2. **Short-term:** [What to do in the next few hours/days]
3. **Long-term Prevention:** [Architecture/config changes to prevent recurrence]

### 💻 Code/Commands
```
[Specific commands, config changes, or code fixes]
```

### 📚 References
- [Relevant links from your research]

---

## Important Rules
- Be specific and actionable — no vague suggestions
- Include actual commands, config values, and code snippets
- Cite your sources (which runbook section, which Stack Overflow answer)
- If uncertain, say so and explain what additional information would help
- Always consider both the immediate fix AND long-term prevention
"""


# ──────────────────────────────────────────────
# Tools List
# ──────────────────────────────────────────────
ALL_TOOLS = [
    analyze_log,
    search_runbooks,
    find_similar_incidents,
    search_web,
    search_stackoverflow,
]


# ──────────────────────────────────────────────
# LLM Factory
# ──────────────────────────────────────────────
def get_llm(model_name: Optional[str] = None, temperature: Optional[float] = None):
    """Create an LLM instance via OpenRouter with tools bound."""
    llm = ChatOpenAI(
        model=model_name or Config.OPENROUTER_MODEL,
        openai_api_key=Config.OPENROUTER_API_KEY,
        openai_api_base=Config.OPENROUTER_BASE_URL,
        temperature=temperature if temperature is not None else Config.AGENT_TEMPERATURE,
        max_tokens=4096,
        default_headers={
            "HTTP-Referer": "https://incidentiq.app",
            "X-Title": "IncidentIQ",
        },
    )
    return llm.bind_tools(ALL_TOOLS)


# ──────────────────────────────────────────────
# Graph Nodes
# ──────────────────────────────────────────────
# Store the selected model globally so the node can access it
_selected_model = None
_selected_temperature = None


def set_model(model_name: str = None, temperature: float = None):
    """Set the model before running the graph."""
    global _selected_model, _selected_temperature
    _selected_model = model_name
    _selected_temperature = temperature


def agent_node(state: MessagesState) -> dict:
    """
    The 'brain' node — calls the LLM with the current message history.
    The LLM decides whether to call a tool or produce a final answer.
    """
    llm_with_tools = get_llm(model_name=_selected_model, temperature=_selected_temperature)

    messages = state["messages"]
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)

    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


# ──────────────────────────────────────────────
# Build the Graph
# ──────────────────────────────────────────────
def build_graph(checkpointer=None):
    """
    Construct the LangGraph StateGraph for incident investigation.

    Graph structure:
        START → agent → (tools_condition?)
            → tools → agent  (loop back)
            → END             (no more tool calls)
    """
    tool_node = ToolNode(ALL_TOOLS)

    graph_builder = StateGraph(MessagesState)

    # Add nodes
    graph_builder.add_node("agent", agent_node)
    graph_builder.add_node("tools", tool_node)

    # Edges
    graph_builder.add_edge(START, "agent")

    # Conditional: after agent, route to tools or END
    graph_builder.add_conditional_edges(
        "agent",
        tools_condition,  # routes to "tools" if tool_calls, else END
    )

    # After tools run, loop back to agent
    graph_builder.add_edge("tools", "agent")

    if checkpointer:
        return graph_builder.compile(checkpointer=checkpointer)
    return graph_builder.compile()


# ──────────────────────────────────────────────
# Graph Singleton & Visualization
# ──────────────────────────────────────────────
_graph = None
_checkpointer = None


def get_graph():
    """Get or create the compiled graph (singleton)."""
    global _graph, _checkpointer
    if _graph is None:
        _checkpointer = MemorySaver()
        _graph = build_graph(checkpointer=_checkpointer)
    return _graph


def get_graph_mermaid() -> str:
    """Get Mermaid diagram string for the graph (for UI display)."""
    graph = get_graph()
    try:
        return graph.get_graph().draw_mermaid()
    except Exception:
        return ""


# ──────────────────────────────────────────────
# Main Investigation Runner (invoke mode)
# ──────────────────────────────────────────────
def run_investigation(
    log_text: str,
    model_name: Optional[str] = None,
    thread_id: Optional[str] = None,
    callbacks: Optional[list] = None,
) -> dict:
    """
    Run a full incident investigation using the LangGraph agent.

    Returns:
        dict: output (RCA text), messages, tool_calls
    """
    set_model(model_name=model_name)
    graph = get_graph()

    input_message = HumanMessage(content=(
        "Investigate this production incident. Follow your investigation process step by step.\n\n"
        "--- ERROR LOG / INCIDENT DESCRIPTION ---\n"
        f"{log_text}\n"
        "--- END ---\n\n"
        "Analyze this incident thoroughly using all available tools, "
        "then provide a complete RCA report."
    ))

    config = {
        "configurable": {
            "thread_id": thread_id or "default",
            "model_name": model_name,
        },
    }
    if callbacks:
        config["callbacks"] = callbacks

    result = graph.invoke(
        {"messages": [input_message]},
        config=config,
    )

    messages = result.get("messages", [])

    # Get final AI message (the RCA)
    final_output = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            final_output = msg.content
            break

    # Extract tool call trace
    tool_calls = []
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append({
                    "tool": tc["name"],
                    "input": str(tc.get("args", {}))[:300],
                })
        elif isinstance(msg, ToolMessage):
            if tool_calls and "output" not in tool_calls[-1]:
                tool_calls[-1]["output"] = str(msg.content)[:500]

    return {
        "output": final_output,
        "messages": messages,
        "tool_calls": tool_calls,
    }


# ──────────────────────────────────────────────
# Streaming Investigation Runner
# ──────────────────────────────────────────────
def stream_investigation(
    log_text: str,
    model_name: Optional[str] = None,
    thread_id: Optional[str] = None,
):
    """
    Stream the investigation for real-time Streamlit UI updates.

    Yields:
        dict with: event_type, node, tool_name/content
    """
    set_model(model_name=model_name)
    graph = get_graph()

    input_message = HumanMessage(content=(
        "Investigate this production incident. Follow your investigation process step by step.\n\n"
        "--- ERROR LOG / INCIDENT DESCRIPTION ---\n"
        f"{log_text}\n"
        "--- END ---\n\n"
        "Analyze this incident thoroughly using all available tools, "
        "then provide a complete RCA report."
    ))

    config = {
        "configurable": {
            "thread_id": thread_id or "default",
            "model_name": model_name,
        },
    }

    for event in graph.stream(
        {"messages": [input_message]},
        config=config,
        stream_mode="updates",
    ):
        for node_name, node_output in event.items():
            messages = node_output.get("messages", [])
            for msg in messages:
                if isinstance(msg, AIMessage):
                    if msg.tool_calls:
                        for tc in msg.tool_calls:
                            yield {
                                "event_type": "tool_call",
                                "node": node_name,
                                "tool_name": tc["name"],
                                "tool_input": tc.get("args", {}),
                            }
                    elif msg.content:
                        yield {
                            "event_type": "agent_output",
                            "node": node_name,
                            "content": msg.content,
                        }
                elif isinstance(msg, ToolMessage):
                    yield {
                        "event_type": "tool_result",
                        "node": node_name,
                        "tool_name": msg.name,
                        "content": str(msg.content)[:500],
                    }
