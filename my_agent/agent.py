# agent.py
from __future__ import annotations
from langgraph.graph import StateGraph, START, END
from utils.state import AgentState
from utils.nodes import load_personas, process_persona, write_feedback, check_status

# --- Graph Definition ---

builder = StateGraph(AgentState)

# Nodes
builder.add_node("load_personas", load_personas)
builder.add_node("process_persona", process_persona)
builder.add_node("write_feedback", write_feedback)
builder.add_node("check_status", check_status)

# Edges
builder.add_edge(START, "load_personas")
builder.add_edge("load_personas", "process_persona")
builder.add_edge("process_persona", "write_feedback")
builder.add_edge("write_feedback", "check_status")


def _should_terminate(state: AgentState) -> bool:
    """Stop the graph when work is finished or an unrecoverable error occurs."""
    return state.get("status") in ("completed", "error")


builder.add_conditional_edges(
    "check_status",
    _should_terminate,
    {
        True: END,
        False: "process_persona",
    },
)

graph = builder.compile()
