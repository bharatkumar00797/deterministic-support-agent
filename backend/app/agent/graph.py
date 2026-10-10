"""
Deterministic LangGraph for customer support.
Control flow is explicit; LLM only influences proposals.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage

from app.agent.state import SupportState
from app.agent.nodes import (
    classify_intent,
    propose_action,
    check_approval,
    execute_tool,
    generate_response,
)


def route_entry(state: SupportState) -> str:
    """Resume a parked approval instead of reclassifying the word 'approve'."""
    if state.get("current_step") == "awaiting_approval" and state.get("approved") is not None:
        return "resolve"
    return "classify"


def resolve_approval(state: SupportState):
    if state.get("approved"):
        return {"current_step": "ready_to_execute", "needs_approval": False}
    tool = (state.get("proposed_action") or {}).get("tool") or "the proposed tool"
    return {
        "current_step": "rejected",
        "needs_approval": False,
        "messages": [
            AIMessage(content=f"Rejected. I did not run {tool}. Nothing was changed.")
        ],
    }


def route_after_resolve(state: SupportState) -> str:
    if state.get("current_step") == "rejected":
        return "end"
    return "execute"


def route_after_classification(state: SupportState) -> str:
    intent = state.get("intent")
    if intent in ("refund", "cancel", "update_account"):
        return "propose"
    return "respond"


def route_after_proposal(state: SupportState) -> str:
    if state.get("current_step") == "needs_detail":
        return "end"
    if state.get("needs_approval") and not state.get("approved"):
        return "await_approval"
    return "execute"


def route_after_approval_check(state: SupportState) -> str:
    if state.get("current_step") == "awaiting_approval":
        return "end"
    return "execute"


def start_node(state: SupportState):
    return {}


def build_support_graph():
    graph = StateGraph(SupportState)

    graph.add_node("start", start_node)
    graph.add_node("classify", classify_intent)
    graph.add_node("propose", propose_action)
    graph.add_node("check_approval", check_approval)
    graph.add_node("resolve", resolve_approval)
    graph.add_node("execute", execute_tool)
    graph.add_node("respond", generate_response)

    graph.set_entry_point("start")

    graph.add_conditional_edges(
        "start",
        route_entry,
        {"classify": "classify", "resolve": "resolve"},
    )

    graph.add_conditional_edges(
        "classify",
        route_after_classification,
        {"propose": "propose", "respond": "respond"},
    )

    graph.add_conditional_edges(
        "propose",
        route_after_proposal,
        {
            "await_approval": "check_approval",
            "execute": "execute",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "check_approval",
        route_after_approval_check,
        {"end": END, "execute": "execute"},
    )

    graph.add_conditional_edges(
        "resolve",
        route_after_resolve,
        {"end": END, "execute": "execute"},
    )

    graph.add_edge("execute", "respond")
    graph.add_edge("respond", END)

    memory = MemorySaver()
    return graph.compile(checkpointer=memory)


support_agent = build_support_graph()
