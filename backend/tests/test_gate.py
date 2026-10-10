"""Refund gate, phone, and address must behave the same with no process memory."""

from langchain_core.messages import HumanMessage

from app.agent.graph import build_support_graph

LEDGER = {
    "refunded": ["ORD-77821"],
    "cancelled": False,
    "email": "mira.sen@northline.test",
    "phone": "+1 415 555 0142",
    "address": "18 Harbor Lane, Oakland",
}


def turn(agent, message, snapshot=None, approve=None):
    state = {
        "messages": [HumanMessage(content=message)],
        "customer_id": "CUST-DEMO-001",
        "intent": (snapshot or {}).get("intent"),
        "current_step": (snapshot or {}).get("current_step") or "ready",
        "proposed_action": (snapshot or {}).get("proposed_action"),
        "needs_approval": bool((snapshot or {}).get("needs_approval")),
        "approved": approve,
        "tool_result": None,
        "error": None,
        "ledger": (snapshot or {}).get("ledger") or dict(LEDGER),
    }
    return agent.invoke(state, config={"configurable": {"thread_id": "test"}})


def test_refund_gate_blocks_wrong_amount_and_runs_after_approve():
    agent = build_support_graph()
    blocked = turn(agent, "Refund order 12345 for $10")
    assert blocked["current_step"] == "needs_detail"
    assert not blocked["needs_approval"]
    assert blocked["proposed_action"] is None

    proposed = turn(agent, "Refund order 12345")
    assert proposed["current_step"] == "awaiting_approval"
    assert proposed["proposed_action"]["args"]["amount"] == 49.99

    done = turn(
        agent,
        "",
        snapshot={
            "current_step": "awaiting_approval",
            "needs_approval": True,
            "proposed_action": proposed["proposed_action"],
            "intent": "refund",
            "ledger": dict(LEDGER),
        },
        approve=True,
    )
    assert done["tool_result"]["status"] == "success"
    assert done["current_step"] == "completed"


def test_phone_and_address_update_without_asking_for_email():
    agent = build_support_graph()
    phone = turn(agent, "Change my phone to +1 415 555 0199")
    assert phone["current_step"] == "completed"
    assert phone["proposed_action"]["args"]["phone"] == "+1 415 555 0199"
    assert "email" not in phone["proposed_action"]["args"]

    address = turn(agent, "address: 9 Market Street, Oakland")
    assert address["current_step"] == "completed"
    assert address["proposed_action"]["args"]["address"] == "9 Market Street, Oakland"
