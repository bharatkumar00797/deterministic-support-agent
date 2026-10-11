"""
LangGraph nodes for the deterministic support agent.
LLM is used only for understanding and proposal.
Execution path is controlled by code + validation.
"""

from typing import Dict, Any, Literal
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field
import os
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
    "ORD-12345": {"amount": 49.99, "item": "Wool overshirt", "status": "delivered"},
    "ORD-77821": {"amount": 129.00, "item": "Leather weekender", "status": "refunded"},
    "ORD-44002": {"amount": 18.50, "item": "Linen socks, 3-pack", "status": "shipped"},
}


def get_llm():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI
    except Exception:
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
        return _fresh(_rules_intent(str(last_message)), customer_id)

    from langchain_core.prompts import ChatPromptTemplate

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


def _amount(text: str, order_id: str | None = None) -> float | None:
    """A stated refund amount.

    `$10` was the only form that counted, so "10 dollars" or
    "refund 10 on order 12345" opened a gate for the full order total.
    """
    dollar = re.search(r"\$\s?(\d+(?:\.\d{1,2})?)", text)
    if dollar:
        return float(dollar.group(1))
    words = re.search(
        r"\b(\d+(?:\.\d{1,2})?)\s*(?:dollars?|usd|bucks)\b",
        text,
        re.I,
    )
    if words:
        return float(words.group(1))
    order_digits = order_id.split("-", 1)[1] if order_id and "-" in order_id else None
    leftovers = [
        n for n in re.findall(r"\b(\d+(?:\.\d{1,2})?)\b", text) if n != order_digits
    ]
    if len(leftovers) == 1:
        return float(leftovers[0])
    return None


def _email(text: str) -> str | None:
    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.I)
    return match.group(0) if match else None


def _rules_intent(text: str) -> str:
    """Same order as the browser agent, so production and /api/chat agree."""
    lowered = text.lower()
    if re.search(r"\b(refund|money back|chargeback)\b", lowered):
        return "refund"
    if "cancel" in lowered:
        return "cancel"
    if re.search(r"\b(status|tracking|where is|shipped|delivered)\b", lowered):
        return "order_status"
    if re.search(r"\b(human|manager|escalate|supervisor)\b", lowered):
        return "escalate"
    if _is_account_change(text):
        return "update_account"
    if re.search(r"\border\b", lowered):
        return "order_status"
    return "other"


def _is_account_change(text: str) -> bool:
    lowered = text.lower()
    if re.search(r"\baddress\s*:", text, re.I):
        return True
    mentions_field = re.search(r"\b(email|address|phone)\b", lowered)
    mentions_verb = re.search(r"\b(update|change|switch|set)\b", lowered)
    if mentions_field and mentions_verb:
        return True
    return bool(re.search(r"\b(update|change)\b", lowered) and "account" in lowered)


def _phone(text: str) -> str | None:
    match = re.search(
        r"(?:\+\d{1,3}[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}",
        text,
    )
    if match:
        return match.group(0)
    if re.search(r"\bphone\b", text, re.I):
        local = re.search(r"\b(\d{3}[\s.-]\d{4})\b", text)
        if local:
            return local.group(0)
    return None


def _address(text: str) -> str | None:
    # "email address to a@b.com" names the email field, not a street.
    cleaned = re.sub(r"\bemail\s+address\b", "email", text, flags=re.I)
    labeled = re.search(r"\baddress\s*:\s*(.+)$", cleaned, re.I)
    if labeled:
        return labeled.group(1).strip()
    stated = re.search(r"\baddress\s+(?:to|is)\s+(.+)$", cleaned, re.I)
    if not stated:
        return None
    value = stated.group(1).strip()
    email = _email(value)
    if email and email == value:
        return None
    return value


def propose_action(state: SupportState) -> Dict[str, Any]:
    """Node 2: Propose a concrete action based on intent."""
    intent = state.get("intent")
    customer_id = state.get("customer_id", "CUST-DEMO-001")
    last_message = str(state["messages"][-1].content if state["messages"] else "")
    ledger = state.get("ledger") or {}

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
        if order_id in (ledger.get("refunded") or []):
            return {
                "current_step": "completed",
                "needs_approval": False,
                "proposed_action": None,
                "messages": [AIMessage(content=(
                    f"{order_id} is already refunded. I will not open another gate for it."
                ))],
            }
        known = ORDERS.get(order_id)
        if not known:
            return {
                "current_step": "completed",
                "needs_approval": False,
                "proposed_action": None,
                "messages": [AIMessage(content=(
                    f"No order {order_id} belongs to this account. I will not open a refund gate."
                ))],
            }
        stated = _amount(last_message, order_id)
        amount = known["amount"] if stated is None else stated
        if abs(amount - known["amount"]) > 0.009 or amount > 5000:
            return {
                "current_step": "needs_detail",
                "needs_approval": False,
                "proposed_action": None,
                "messages": [AIMessage(content=(
                    f"${amount:.2f} does not match the {order_id} total of ${known['amount']:.2f}. "
                    "I will not open a gate for a different amount."
                ))],
            }
        return {
            "proposed_action": {
                "tool": "process_refund",
                "args": {
                    "order_id": order_id,
                    "amount": known["amount"],
                    "reason": "Customer requested refund",
                    "customer_id": customer_id,
                },
            },
            "needs_approval": True,
            "current_step": "proposed",
        }

    if intent == "cancel":
        if ledger.get("cancelled"):
            return {
                "current_step": "completed",
                "needs_approval": False,
                "proposed_action": None,
                "messages": [AIMessage(content="Northline Plus is already cancelled.")],
            }
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
        phone = _phone(last_message)
        address = _address(last_message)
        # A phone pattern can swallow digits that are not a phone request.
        if phone and not re.search(r"\bphone\b", last_message, re.I):
            phone = None
        if not email and not phone and not address:
            return {
                "current_step": "needs_detail",
                "needs_approval": False,
                "proposed_action": None,
                "messages": [AIMessage(content=(
                    "What should I change? Send a new email, a phone number, "
                    "or a line that starts with \"address:\"."
                ))],
            }
        args: Dict[str, Any] = {"customer_id": customer_id}
        if email:
            args["email"] = email
        if phone:
            args["phone"] = phone
        if address:
            args["address"] = address
        return {
            "proposed_action": {"tool": "update_account", "args": args},
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
        tool = action.get("tool")
        args = action.get("args") or {}
        if tool == "process_refund":
            content = (
                f"I will not move money yet. Proposed process_refund for {args.get('order_id')} "
                f"at ${float(args.get('amount') or 0):.2f}. Approve to execute, or reject to leave the ledger alone."
            )
        elif tool == "cancel_subscription":
            content = (
                f"Proposed cancel_subscription for Northline Plus ({args.get('subscription_id')}). "
                "This does not run until you approve."
            )
        else:
            content = f"Approval required before {tool} runs."
        return {
            "current_step": "awaiting_approval",
            "messages": [AIMessage(content=content)],
        }
    return {"current_step": "ready_to_execute"}


def execute_tool(state: SupportState) -> Dict[str, Any]:
    """Node 4: Actually execute the validated tool. Pure deterministic code."""
    proposed = state.get("proposed_action") or {}
    tool_name = proposed.get("tool")
    args = proposed.get("args") or {}
    ledger = state.get("ledger") or {}

    try:
        if tool_name == "process_refund":
            order_id = str(args.get("order_id") or "")
            if order_id in (ledger.get("refunded") or []):
                return {
                    "tool_result": None,
                    "current_step": "error",
                    "error": f"{order_id} is already refunded.",
                }
            known = ORDERS.get(order_id)
            amount = float(args.get("amount") or 0)
            if not known or abs(amount - known["amount"]) > 0.009 or amount > 5000:
                return {
                    "tool_result": None,
                    "current_step": "error",
                    "error": f"Refund for {order_id} does not match the order on this account.",
                }
            req = RefundRequest(**args)
            result = process_refund(req)
        elif tool_name == "cancel_subscription":
            if ledger.get("cancelled"):
                return {
                    "tool_result": None,
                    "current_step": "error",
                    "error": "Subscription is already cancelled.",
                }
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
    elif state.get("intent") == "order_status":
        content = _status_reply(state)
    elif state.get("intent") == "escalate":
        content = (
            "Opened a human queue ticket HQ-221 for this customer. "
            "No refund, cancel, or account tool was called."
        )
    else:
        content = (
            "I didn't take an action. Ask for a refund, a cancellation, "
            "or an account email change."
        )

    return {
        "messages": [AIMessage(content=content)],
        "current_step": "completed",
    }


def _last_user_text(state: SupportState) -> str:
    for message in reversed(state.get("messages") or []):
        if isinstance(message, AIMessage):
            continue
        return str(getattr(message, "content", "") or "")
    return ""


def _shown_status(order_id: str, info: Dict[str, Any], refunded: set) -> str:
    """Catalog status, unless this case already refunded the order.

    Collapsing every non-refund to "on file" made "Where is order 44002?"
    look unanswered. 44002 is shipped; 12345 is delivered.
    """
    if order_id in refunded or info.get("status") == "refunded":
        return "refunded"
    return str(info.get("status") or "on file")


def _status_reply(state: SupportState) -> str:
    order_id = _order_id(_last_user_text(state))
    ledger = state.get("ledger") or {}
    refunded = set(ledger.get("refunded") or [])
    if not order_id:
        lines = []
        for oid, info in ORDERS.items():
            status = _shown_status(oid, info, refunded)
            lines.append(f"{oid} · {info['item']} · ${info['amount']:.2f} · {status}")
        return "Which order?\n" + "\n".join(lines)
    known = ORDERS.get(order_id)
    if not known:
        return f"No order {order_id} belongs to this account."
    status = _shown_status(order_id, known, refunded)
    return (
        f"{order_id} · {known['item']} · ${known['amount']:.2f} · {status}. "
        "No tool was required."
    )
