"""Vercel FastAPI entry. The compiled graph is imported on the first request."""

import sys
from pathlib import Path

_BACKEND_DIR = str(Path(__file__).resolve().parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import traceback
import uuid

app = FastAPI(
    title="Deterministic Support Agent API",
    description="Reliable multi-step customer support agent powered by LangGraph",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_agent = None
_import_error = None


def get_agent():
    global _agent, _import_error
    if _agent is not None:
        return _agent
    if _import_error is not None:
        raise RuntimeError(_import_error)
    try:
        from app.agent.graph import support_agent as compiled
        _agent = compiled
        return _agent
    except Exception:
        _import_error = traceback.format_exc()
        raise


DEFAULT_LEDGER = {
    "refunded": ["ORD-77821"],
    "cancelled": False,
    "email": "mira.sen@northline.test",
    "phone": "+1 415 555 0142",
    "address": "18 Harbor Lane, Oakland",
}


class ChatRequest(BaseModel):
    message: str = ""
    thread_id: Optional[str] = None
    customer_id: Optional[str] = None
    approve: Optional[bool] = None
    snapshot: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    thread_id: str
    messages: List[Dict[str, str]]
    current_step: str
    needs_approval: bool
    proposed_action: Optional[Dict[str, Any]] = None
    tool_result: Optional[Dict[str, Any]] = None
    snapshot: Optional[Dict[str, Any]] = None
    engine: str = "langgraph"


def _ledger(snapshot: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw = (snapshot or {}).get("ledger") or {}
    refunded = raw.get("refunded")
    return {
        "refunded": list(refunded) if isinstance(refunded, list) else list(DEFAULT_LEDGER["refunded"]),
        "cancelled": bool(raw.get("cancelled", False)),
        "email": raw.get("email") or DEFAULT_LEDGER["email"],
        "phone": raw.get("phone") or DEFAULT_LEDGER["phone"],
        "address": raw.get("address") or DEFAULT_LEDGER["address"],
    }


def _decision(req: ChatRequest, snapshot: Optional[Dict[str, Any]]) -> Optional[bool]:
    if req.approve is not None:
        return req.approve
    if (snapshot or {}).get("current_step") != "awaiting_approval":
        return None
    text = (req.message or "").strip().lower()
    if text in {"approve", "approved", "yes"}:
        return True
    if text in {"reject", "rejected", "no"}:
        return False
    return None


def _apply_ledger(ledger: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    tool_result = result.get("tool_result") or {}
    if tool_result.get("status") != "success":
        return ledger
    proposed = result.get("proposed_action") or {}
    tool = proposed.get("tool")
    args = proposed.get("args") or {}
    if tool == "process_refund":
        order_id = str(args.get("order_id") or "")
        if order_id and order_id not in ledger["refunded"]:
            ledger["refunded"].append(order_id)
    elif tool == "cancel_subscription":
        ledger["cancelled"] = True
    elif tool == "update_account":
        for key in ("email", "phone", "address"):
            if args.get(key):
                ledger[key] = args[key]
    return ledger


def _audit(snapshot: Optional[Dict[str, Any]], result: Dict[str, Any]) -> List[Dict[str, str]]:
    audit = list((snapshot or {}).get("audit") or [{"step": "Open", "detail": "Case opened"}])
    step = result.get("current_step")
    proposed = result.get("proposed_action") or {}
    if step == "awaiting_approval":
        audit.append({"step": "Propose", "detail": str(proposed.get("tool") or "proposal")})
        audit.append({"step": "Gate", "detail": "Waiting on approve or reject"})
    elif step == "rejected":
        audit.append({"step": "Gate", "detail": "Human rejected the proposal"})
    elif step == "needs_detail":
        audit.append({"step": "Propose", "detail": "Blocked: missing detail"})
    elif result.get("tool_result"):
        message = (result.get("tool_result") or {}).get("message") or "executed"
        audit.append({"step": "Execute", "detail": str(message)})
    elif step == "error":
        audit.append({"step": "Execute", "detail": str(result.get("error") or "error")})
    elif step == "completed":
        audit.append({"step": "Reply", "detail": "Turn closed"})
    return audit


@app.get("/")
def root():
    return {
        "message": "Deterministic Support Agent API is running",
        "version": "0.2.0",
        "framework": "LangGraph",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    if _import_error:
        return {"status": "import_error", "detail": _import_error}
    try:
        get_agent()
    except Exception:
        return {"status": "import_error", "detail": _import_error or traceback.format_exc()}
    return {"status": "healthy"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Main entry point. Each call carries its own case snapshot."""
    from langchain_core.messages import HumanMessage, AIMessage

    try:
        agent = get_agent()
    except Exception as e:
        raise HTTPException(status_code=500, detail=_import_error or str(e))

    snapshot = req.snapshot or None
    public_thread = req.thread_id or (snapshot or {}).get("thread_id") or "THR-1042"
    ledger = _ledger(snapshot)
    approved = _decision(req, snapshot)
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    input_state: Dict[str, Any] = {
        "messages": [HumanMessage(content=req.message or "")],
        "customer_id": req.customer_id or (snapshot or {}).get("customer_id") or "CUST-DEMO-001",
        "intent": (snapshot or {}).get("intent"),
        "current_step": (snapshot or {}).get("current_step") or "ready",
        "proposed_action": (snapshot or {}).get("proposed_action"),
        "needs_approval": bool((snapshot or {}).get("needs_approval")),
        "approved": approved,
        "tool_result": None,
        "error": None,
        "ledger": ledger,
    }

    try:
        result = agent.invoke(input_state, config=config)
    except Exception:
        raise HTTPException(status_code=500, detail=traceback.format_exc())

    messages_out = []
    for m in result.get("messages") or []:
        if not isinstance(m, AIMessage):
            continue
        content = m.content if isinstance(m.content, str) else str(m.content)
        messages_out.append({"role": "assistant", "content": content})
    if messages_out:
        messages_out = messages_out[-1:]

    ledger = _apply_ledger(ledger, result)
    audit = _audit(snapshot, result)
    current_step = result.get("current_step", "unknown")
    needs_approval = bool(result.get("needs_approval")) and current_step == "awaiting_approval"
    case_snapshot = {
        "thread_id": public_thread,
        "customer_id": result.get("customer_id") or input_state["customer_id"],
        "intent": result.get("intent"),
        "current_step": current_step,
        "needs_approval": needs_approval,
        "proposed_action": result.get("proposed_action"),
        "approved": result.get("approved"),
        "ledger": ledger,
        "audit": audit,
    }

    return ChatResponse(
        thread_id=public_thread,
        messages=messages_out,
        current_step=current_step,
        needs_approval=needs_approval,
        proposed_action=result.get("proposed_action"),
        tool_result=result.get("tool_result"),
        snapshot=case_snapshot,
        engine="langgraph",
    )
