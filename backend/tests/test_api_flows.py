"""End-to-end flows through POST /chat. The client carries the case between turns."""

import pytest
from fastapi.testclient import TestClient

from support_api import app

client = TestClient(app)


class Case:
    def __init__(self):
        self.snapshot = None

    def say(self, message="", approve=None):
        body = {"message": message}
        if approve is not None:
            body["approve"] = approve
        if self.snapshot:
            body["snapshot"] = self.snapshot
        res = client.post("/chat", json=body)
        assert res.status_code == 200, res.text
        data = res.json()
        self.snapshot = data["snapshot"]
        return data

    @property
    def ledger(self):
        return self.snapshot["ledger"]


def text(data):
    return data["messages"][-1]["content"]


@pytest.mark.parametrize(
    "order,status",
    [("12345", "delivered"), ("44002", "shipped"), ("77821", "refunded")],
)
def test_order_status(order, status):
    data = Case().say(f"Where is order {order}?")
    assert status in text(data)
    assert data["tool_result"] is None


def test_unknown_order_status_and_refund():
    assert "No order ORD-99999" in text(Case().say("Where is order 99999?"))
    data = Case().say("Refund order 99999")
    assert not data["needs_approval"]
    assert "No order ORD-99999" in text(data)


def test_health():
    assert client.get("/health").json() == {"status": "healthy"}


def test_refund_waits_for_approval_and_then_runs():
    case = Case()
    gate = case.say("Refund order 12345")
    assert gate["needs_approval"] and gate["current_step"] == "awaiting_approval"
    assert "ORD-12345" not in case.ledger["refunded"]
    done = case.say(approve=True)
    assert done["tool_result"]["status"] == "success"
    assert "ORD-12345" in case.ledger["refunded"]
    assert "$49.99" in text(done)


def test_refund_reject_leaves_ledger_alone():
    case = Case()
    case.say("Refund order 44002")
    data = case.say(approve=False)
    assert data["current_step"] == "rejected"
    assert data["tool_result"] is None
    assert "ORD-44002" not in case.ledger["refunded"]


def test_typed_approve_and_reject_words():
    case = Case()
    case.say("refund order 12345")
    assert case.say("approve")["tool_result"]["status"] == "success"
    case = Case()
    case.say("refund order 12345")
    assert case.say("no")["current_step"] == "rejected"


@pytest.mark.parametrize(
    "message",
    [
        "Refund order 12345 for $10",
        "refund 10 dollars on order 12345",
        "refund 10 on order 12345",
        "Refund order 12345 for $5000",
    ],
)
def test_refund_amount_must_match_order_total(message):
    data = Case().say(message)
    assert not data["needs_approval"]
    assert data["proposed_action"] is None
    assert "does not match" in text(data)


@pytest.mark.parametrize(
    "message",
    ["Refund order 12345 for $49.99", "refund 12345 please", "refund ORD-12345", "money back for order #12345"],
)
def test_refund_phrasings_open_one_gate(message):
    data = Case().say(message)
    assert data["needs_approval"]
    assert data["proposed_action"]["args"]["order_id"] == "ORD-12345"
    assert data["proposed_action"]["args"]["amount"] == 49.99


def test_repeated_refund_is_blocked():
    case = Case()
    case.say("Refund order 12345")
    case.say(approve=True)
    again = case.say("Refund order 12345")
    assert not again["needs_approval"]
    assert "already refunded" in text(again)
    assert case.ledger["refunded"].count("ORD-12345") == 1


def test_seeded_refund_is_blocked():
    data = Case().say("Refund order 77821")
    assert not data["needs_approval"]
    assert "already refunded" in text(data)


def test_forged_snapshot_cannot_refund_twice():
    case = Case()
    case.say("Refund order 12345")
    case.say(approve=True)
    case.say("Refund order 44002")
    # A parked proposal for an order already in the ledger must not execute.
    case.snapshot["current_step"] = "awaiting_approval"
    case.snapshot["needs_approval"] = True
    case.snapshot["proposed_action"] = {
        "tool": "process_refund",
        "args": {"order_id": "ORD-12345", "amount": 49.99, "reason": "x", "customer_id": "CUST-DEMO-001"},
    }
    data = case.say(approve=True)
    assert data["tool_result"] is None
    assert case.ledger["refunded"].count("ORD-12345") == 1


def test_forged_amount_is_refused_on_execute():
    case = Case()
    case.snapshot = {
        "current_step": "awaiting_approval",
        "needs_approval": True,
        "proposed_action": {
            "tool": "process_refund",
            "args": {"order_id": "ORD-12345", "amount": 4000, "reason": "x", "customer_id": "CUST-DEMO-001"},
        },
    }
    data = case.say(approve=True)
    assert data["tool_result"] is None
    assert "ORD-12345" not in case.ledger["refunded"]


def test_cancel_approve_then_repeat():
    case = Case()
    assert case.say("Please cancel my subscription")["needs_approval"]
    assert case.say(approve=True)["tool_result"]["status"] == "success"
    assert case.ledger["cancelled"] is True
    again = case.say("cancel subscription")
    assert not again["needs_approval"]
    assert "already cancelled" in text(again)


def test_cancel_reject_keeps_subscription():
    case = Case()
    case.say("cancel my subscription")
    case.say(approve=False)
    assert case.ledger["cancelled"] is False


def test_account_updates_change_only_the_named_field():
    case = Case()
    case.say("Update my email address to x@y.com")
    assert case.ledger["email"] == "x@y.com"
    assert case.ledger["address"] == "18 Harbor Lane, Oakland"
    case.say("Change my phone to 555-0199")
    assert case.ledger["phone"] == "555-0199"
    case.say("change my address to 5 Elm St, Reno")
    assert case.ledger["address"] == "5 Elm St, Reno"
    assert case.ledger["email"] == "x@y.com"
    case.say("address: 9 Market Street, Oakland")
    assert case.ledger["address"] == "9 Market Street, Oakland"


def test_account_update_without_detail_asks():
    data = Case().say("update my account")
    assert data["current_step"] == "needs_detail"
    assert data["proposed_action"] is None


def test_other_message_while_gate_is_open_keeps_the_gate():
    case = Case()
    case.say("refund order 12345")
    data = case.say("Where is order 44002?")
    assert data["needs_approval"] and data["current_step"] == "awaiting_approval"
    assert "still waiting" in text(data)
    done = case.say(approve=True)
    assert done["tool_result"]["status"] == "success"
    assert "ORD-12345" in case.ledger["refunded"]


def test_approve_with_nothing_pending_does_nothing():
    case = Case()
    case.say("hello")
    data = case.say(approve=True)
    assert data["tool_result"] is None
    assert case.ledger["refunded"] == ["ORD-77821"]


def test_refund_and_cancel_in_one_message_asks_for_one():
    data = Case().say("refund 12345 and cancel my subscription")
    assert not data["needs_approval"]
    assert "one at a time" in text(data)


def test_order_status_after_refund_shows_refunded():
    case = Case()
    case.say("refund order 44002")
    case.say(approve=True)
    assert "refunded" in text(case.say("Where is order 44002?"))


def test_human_handoff_runs_no_tool():
    data = Case().say("talk to a human")
    assert data["tool_result"] is None and not data["needs_approval"]
    assert "HQ-221" in text(data)
