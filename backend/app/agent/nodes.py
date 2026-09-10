"""
LangGraph nodes for the deterministic support agent.
LLM is used only for understanding and proposal.
Execution path is controlled by code + validation.
"""

from typing import Dict, Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
import os
import json

from app.agent.state import SupportState
from app.tools.actions import (
    process_refund,
    cancel_subscription,
    update_account,
    RefundRequest,
    CancelSubscriptionRequest,
    UpdateAccountRequest,
)

# Lightweight model for classification / proposal
# Falls back gracefully if no key is set (for local testing without LLM)
def get_llm():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return ChatOpenAI(model="gpt-4o-mini", temperature=0)

class IntentClassification(BaseModel):
    intent: Literal["refund", "cancel", "update_account", "order_status", "escalate", "other"]
    confidence: float = Field(ge=0, le=1)
    customer_id: str | None = None
    reasoning: str

def classify_intent(state: SupportState) -> Dict[str, Any]:
    """Node 1: Classify user intent."""
    llm = get_llm()
    last_message = state["messages"][-1].content if state["messages"] else ""

    if llm is None:
        # Fallback heuristic for demo without API key
        text = last_message.lower()
        if "refund" in text:
            intent = "refund"
        elif "cancel" in text:
            intent = "cancel"
        elif "update" in text or "change" in text:
            intent = "update_account"
        elif "status" in text or "order" in text:
            intent = "order_status"
        else:
            intent = "other"
        return {
            "intent": intent,
            "current_step": "classified",
            "customer_id": state.get("customer_id") or "CUST-DEMO-001",
        }

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an intent classifier for a customer support agent. "
                   "Extract the primary intent and any customer_id mentioned. "
                   "Respond with structured output only."),
        ("human", "{message}")
    ])

    structured_llm = llm.with_structured_output(IntentClassification)
    chain = prompt | structured_llm
    result: IntentClassification = chain.invoke({"message": last_message})

    return {
        "intent": result.intent,
        "customer_id": result.customer_id or state.get("customer_id") or "CUST-DEMO-001",
        "current_step": "classified",
    }

def propose_action(state: SupportState) -> Dict[str, Any]:
    """Node 2: Propose a concrete action based on intent."""
    intent = state.get("intent")
    customer_id = state.get("customer_id", "CUST-DEMO-001")
    last_message = state["messages"][-1].content if state["messages"] else ""

    proposed = None
    needs_approval = False

    if intent == "refund":
        # Simple extraction for demo; in production use structured extraction
        proposed = {
            "tool": "process_refund",
            "args": {
                "order_id": "ORD-12345",
                "amount": 49.99,
                "reason": "Customer requested refund",
                "customer_id": customer_id,
            }
        }
        needs_approval = True  # money movement always needs approval in this MVP
    elif intent == "cancel":
        proposed = {
            "tool": "cancel_subscription",
            "args": {
                "customer_id": customer_id,
                "subscription_id": "SUB-98765",
                "reason": "Customer requested cancellation",
            }
        }
        needs_approval = True
    elif intent == "update_account":
        proposed = {
            "tool": "update_account",
            "args": {
                "customer_id": customer_id,
                "email": None,  # would be extracted
                "address": None,
            }
        }
        needs_approval = False
    else:
        proposed = {"tool": None, "args": {}}

    return {
        "proposed_action": proposed,
        "needs_approval": needs_approval,
        "current_step": "proposed",
    }

def check_approval(state: SupportState) -> Dict[str, Any]:
    """Node 3: Decide whether we can proceed or must wait for human."""
    if state.get("needs_approval") and not state.get("approved"):
        return {
            "current_step": "awaiting_approval",
            "messages": [AIMessage(content=(
                f"I propose to run **{state['proposed_action']['tool']}** with args:\n"
                f"```json\n{json.dumps(state['proposed_action']['args'], indent=2)}\n```\n"
                "Please reply with **approve** or **reject**."
            ))]
        }
    return {"current_step": "ready_to_execute"}

def execute_tool(state: SupportState) -> Dict[str, Any]:
    """Node 4: Actually execute the validated tool. Pure deterministic code."""
    proposed = state.get("proposed_action") or {}
    tool_name = proposed.get("tool")
    args = proposed.get("args") or {}

    try:
        if tool_name == "process_refund":
            req = RefundRequest(**args)
            result = process_refund(req)
        elif tool_name == "cancel_subscription":
            req = CancelSubscriptionRequest(**args)
            result = cancel_subscription(req)
        elif tool_name == "update_account":
            req = UpdateAccountRequest(**args)
            result = update_account(req)
        else:
            result = {"status": "skipped", "message": "No actionable tool for this intent"}

        return {
            "tool_result": result,
            "current_step": "executed",
            "error": None,
        }
    except Exception as e:
        return {
            "tool_result": None,
            "current_step": "error",
            "error": str(e),
        }

def generate_response(state: SupportState) -> Dict[str, Any]:
    """Node 5: Produce the final user-facing message."""
    if state.get("error"):
        content = f"Sorry, I encountered an error while processing your request: {state['error']}"
    elif state.get("tool_result"):
        result = state["tool_result"]
        content = result.get("message", "Action completed successfully.")
        if result.get("status") == "success":
            content = f"✅ {content}"
    else:
        content = "I understand your request. How else can I help you today?"

    return {
        "messages": [AIMessage(content=content)],
        "current_step": "completed",
    }
