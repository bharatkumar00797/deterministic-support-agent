"""
Deterministic LangGraph for customer support.
Control flow is explicit; LLM only influences proposals.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.agent.state import SupportState
from app.agent.nodes import (
    classify_intent,
    propose_action,
    check_approval,
    execute_tool,
    generate_response,
)

def route_after_classification(state: SupportState) -> str:
    intent = state.get("intent")
    if intent in ("refund", "cancel", "update_account"):
        return "propose"
    if intent == "escalate":
        return "respond"  # simple escalate path for MVP
    return "respond"

def route_after_proposal(state: SupportState) -> str:
    if state.get("needs_approval") and not state.get("approved"):
        return "await_approval"
    return "execute"

def route_after_approval_check(state: SupportState) -> str:
    if state.get("current_step") == "awaiting_approval":
        return "end"  # wait for next human message
    return "execute"

def build_support_graph():
    graph = StateGraph(SupportState)

    # Nodes
    graph.add_node("classify", classify_intent)
    graph.add_node("propose", propose_action)
    graph.add_node("check_approval", check_approval)
    graph.add_node("execute", execute_tool)
    graph.add_node("respond", generate_response)

    # Entry
    graph.set_entry_point("classify")

    # Edges
    graph.add_conditional_edges(
        "classify",
        route_after_classification,
        {
            "propose": "propose",
            "respond": "respond",
        }
    )

    graph.add_conditional_edges(
        "propose",
        route_after_proposal,
        {
            "await_approval": "check_approval",
            "execute": "execute",
        }
    )

    graph.add_conditional_edges(
        "check_approval",
        route_after_approval_check,
        {
            "end": END,
            "execute": "execute",
        }
    )

    graph.add_edge("execute", "respond")
    graph.add_edge("respond", END)

    # Memory for conversation continuity
    memory = MemorySaver()
    return graph.compile(checkpointer=memory)

# Singleton for the app
support_agent = build_support_graph()
