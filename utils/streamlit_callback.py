"""
IncidentIQ - Streamlit Agent Display for LangGraph
Renders real-time agent events (tool calls, results, final output)
streamed from the LangGraph graph execution.
"""

import json
import streamlit as st


TOOL_ICONS = {
    "analyze_log": "🔬",
    "search_runbooks": "📖",
    "find_similar_incidents": "🔄",
    "search_web": "🌐",
    "search_stackoverflow": "📚",
}

TOOL_DESCRIPTIONS = {
    "analyze_log": "Parsing error log & stack trace",
    "search_runbooks": "Searching internal runbooks (RAG)",
    "find_similar_incidents": "Checking incident memory",
    "search_web": "Researching the web",
    "search_stackoverflow": "Searching Stack Overflow",
}


def render_stream_event(event: dict, container, step_counter: list):
    """
    Render a single streaming event from the LangGraph agent.
    
    Args:
        event: dict with event_type, tool_name, content, etc.
        container: Streamlit container to render into
        step_counter: mutable list [count] to track step numbers
    """
    event_type = event.get("event_type", "")

    with container:
        if event_type == "tool_call":
            step_counter[0] += 1
            tool_name = event.get("tool_name", "unknown")
            tool_input = event.get("tool_input", {})
            icon = TOOL_ICONS.get(tool_name, "🔧")
            desc = TOOL_DESCRIPTIONS.get(tool_name, tool_name)

            st.markdown(
                f"**Step {step_counter[0]}:** {icon} **{desc}**"
            )

            # Show tool input in a collapsed expander
            input_str = str(tool_input)
            if len(input_str) > 200:
                input_str = input_str[:200] + "..."
            with st.expander(f"↳ {tool_name} input", expanded=False):
                st.code(input_str, language="text")

        elif event_type == "tool_result":
            tool_name = event.get("tool_name", "")
            content = event.get("content", "")
            icon = TOOL_ICONS.get(tool_name, "🔧")

            with st.expander(f"{icon} {tool_name} result", expanded=False):
                try:
                    parsed = json.loads(content)
                    st.json(parsed)
                except (json.JSONDecodeError, TypeError):
                    if len(content) > 500:
                        content = content[:500] + "..."
                    st.code(content, language="text")

        elif event_type == "agent_output":
            pass  # Final output handled separately
