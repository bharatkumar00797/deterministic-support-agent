"""
LangGraph nodes for the deterministic support agent.
LLM is used only for understanding and proposal.
Execution path is controlled by code + validation.
"""

from typing import Dict, Any, Literal
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
import os
import json
import re

from app.agent.state import SupportState
from app.tools.actions import (
    process_refund,
    cancel_subscription,
    update_account,
    RefundRequest,
    CancelSubscriptionRequest,
    UpdateAccountRequest,
)

ORDERS = {
    "ORD-12345": {"amount": 49.99, "item": "Wool overshirt"},
    "ORD-77821": {"amount": 129.00, "item": "Leather weekender"},
    "ORD-44002": {"amount": 18.50, "item": "Linen socks, 3-pack"},
}


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


def _fresh(intent: str, customer_id: str) -> Dict[str, Any]:
    return {
        "intent": intent,
        "customer_id": customer_id,
        "current_step": "classified",
        "proposed_action": None,
        "needs_approval": False,
        "approved": None,
        "tool_result": None,
        "error": None,
    }


def classify_intent(state: SupportState) -> Dict[str, Any]:
    """Node 1: Classify user intent. A fresh turn clears the previous proposal."""
    llm = get_llm()
    last_message = state["messages"][-1].content if state["messages"] else ""
    customer_id = state.get("customer_id") or "CUST-DEMO-001"

    if llm is None:
        text = str(last_message).lower()
        if "refund" in text or "money back" in text:
            intent = "refund"
        elif "cancel" in text:
            intent = "cancel"
        elif "status" in text or "where is" in text or "tracking" in text:
            intent = "order_status"
        elif "update" in text or "change" in text:
            intent = "update_account"
        elif "human" in text or "manager" in text or "escalate" in text:
            intent = "escalate"
        else:
            intent = "other"
        return _fresh(intent, customer_id)

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an intent classifier for a customer support agent. "
                   "Extract the primary intent and any customer_id mentioned. "
                   "Respond with structured output only."),
        ("human", "{message}")
    ])

    structured_llm = llm.with_structured_output(IntentClassification)
    chain = prompt | structured_llm
    result: IntentClassification = chain.invoke({"message": last_message})

    return _fresh(result.intent, result.customer_id or customer_id)


def _order_id(text: str) -> str | None:
    coded = re.search(r"\bORD[-\s]?(\d{3,})\b", text, re.I)
    if coded:
        return f"ORD-{coded.group(1)}"
    loose = re.search(r"\border\s+#?(\d{3,})\b", text, re.I)
    if loose:
        return f"ORD-{loose.group(1)}"
    return None


def _amount(text: str) -> float | None:
    match = re.search(r"\$\s?(\d+(?:\.\d{1,2})?)", text)
    return float(match.group(1)) if match else None


def _email(text: str) -> str | None:
    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.I)
    return match.group(0) if match else None


def propose_action(state: SupportState) -> Dict[str, Any]:
    """Node 2: Propose a concrete action based on intent."""
    intent = state.get("intent")
    customer_id = state.get("customer_id", "CUST-DEMO-001")
    last_message = str(state["messages"][-1].content if state["messages"] else "")

    if intent == "refund":
        order_id = _order_id(last_message)
        if not order_id:
            return {
                "current_step": "needs_detail",
                "needs_approval": False,
                "proposed_action": None,
                "messages": [AIMessage(content=(
                    "Which order should I refund? Try ORD-12345, ORD-44002, or ORD-77821."
                ))],
            }
        known = ORDERS.get(order_id)
        amount = _amount(last_message) or (known["amount"] if known else None)
        if amount is None:
            return {
                "current_step": "needs_detail",
                "needs_approval": False,
                "proposed_action": None,
                "messages": [AIMessage(content=f"I need a dollar amount for {order_id}.")],
            }
        return {
            "proposed_action": {
                "tool": "process_refund",
                "args": {
                    "order_id": order_id,
                    "amount": amount,
                    "reason": "Customer requested refund",
                    "customer_id": customer_id,
                },
            },
            "needs_approval": True,
            "current_step": "proposed",
        }

    if intent == "cancel":
        return {
            "proposed_action": {
                "tool": "cancel_subscription",
                "args": {
                    "customer_id": customer_id,
                    "subscription_id": "SUB-98765",
                    "reason": "Customer requested cancellation",
                },
            },
            "needs_approval": True,
            "current_step": "proposed",
        }

    if intent == "update_account":
        email = _email(last_message)
        if not email:
            return {
                "current_step": "needs_detail",
                "needs_approval": False,
                "proposed_action": None,
                "messages": [AIMessage(content="What email should I set on the account?")],
            }
        return {
            "proposed_action": {
                "tool": "update_account",
                "args": {"customer_id": customer_id, "email": email},
            },
            "needs_approval": False,
            "current_step": "proposed",
        }

    return {
        "proposed_action": {"tool": None, "args": {}},
        "needs_approval": False,
        "current_step": "proposed",
    }


def check_approval(state: SupportState) -> Dict[str, Any]:
    """Node 3: Decide whether we can proceed or must wait for human."""
    if state.get("needs_approval") and not state.get("approved"):
        action = state.get("proposed_action") or {}
        return {
            "current_step": "awaiting_approval",
            "messages": [AIMessage(content=(
                f"I propose to run **{action.get('tool')}** with args:\n"
                f"```json\n{json.dumps(action.get('args') or {}, indent=2)}\n```\n"
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
        content = (
            "I didn't take an action. Ask for a refund, a cancellation, "
            "or an account email change."
        )

    return {
        "messages": [AIMessage(content=content)],
        "current_step": "completed",
    }
