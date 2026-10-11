"""
Deterministic action tools.
These are pure functions with strict input validation.
The LLM never invents the final action — it only proposes; code executes.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime

class RefundRequest(BaseModel):
    order_id: str
    amount: float = Field(gt=0, le=10000)
    reason: str
    customer_id: str

    @field_validator("amount")
    @classmethod
    def amount_must_be_reasonable(cls, v):
        if v > 5000:
            raise ValueError("Refunds over $5000 require manual approval")
        return v

def process_refund(req: RefundRequest) -> dict:
    """Simulate a real refund. In production this calls Stripe / billing API."""
    # TODO: real integration
    return {
        "status": "success",
        "refund_id": f"ref_{req.order_id}_{int(datetime.utcnow().timestamp())}",
        "amount": req.amount,
        "message": f"Refund of ${req.amount:.2f} processed for order {req.order_id}"
    }

class CancelSubscriptionRequest(BaseModel):
    customer_id: str
    subscription_id: str
    reason: Optional[str] = None

def cancel_subscription(req: CancelSubscriptionRequest) -> dict:
    """Simulate subscription cancellation."""
    return {
        "status": "success",
        "subscription_id": req.subscription_id,
        "cancelled_at": datetime.utcnow().isoformat(),
        "message": f"Subscription {req.subscription_id} cancelled"
    }

class UpdateAccountRequest(BaseModel):
    customer_id: str
    email: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None

def update_account(req: UpdateAccountRequest) -> dict:
    """Simulate account update. Name every field so an email change cannot look like an address change."""
    updated = {k: v for k, v in req.model_dump().items() if v is not None and k != "customer_id"}
    changed = [f"{key} to {value}" for key, value in updated.items()]
    left = [key for key in ("email", "phone", "address") if key not in updated]
    left_text = ", ".join(left) if left else "nothing"
    message = f"Updated {' and '.join(changed)}. Left unchanged: {left_text}."
    return {
        "status": "success",
        "customer_id": req.customer_id,
        "updated_fields": list(updated.keys()),
        "message": message,
    }
