from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage
import uuid

from app.agent.graph import support_agent

app = FastAPI(
    title="Deterministic Support Agent API",
    description="Reliable multi-step customer support agent powered by LangGraph",
    version="0.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None
    customer_id: Optional[str] = None
    approve: Optional[bool] = None  # for human-in-the-loop

class ChatResponse(BaseModel):
    thread_id: str
    messages: List[Dict[str, str]]
    current_step: str
    needs_approval: bool
    proposed_action: Optional[Dict[str, Any]] = None
    tool_result: Optional[Dict[str, Any]] = None

@app.get("/")
def root():
    return {
        "message": "Deterministic Support Agent API is running",
        "version": "0.2.0",
        "framework": "LangGraph",
        "docs": "/docs"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Main entry point for the support agent."""
    thread_id = req.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    # Build input state
    input_state: Dict[str, Any] = {
        "messages": [HumanMessage(content=req.message)],
    }
    if req.customer_id:
        input_state["customer_id"] = req.customer_id
    if req.approve is not None:
        input_state["approved"] = req.approve

    try:
        result = support_agent.invoke(input_state, config=config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Normalize messages for response
    messages_out = []
    for m in result.get("messages", []):
        role = "assistant" if isinstance(m, AIMessage) else "user"
        messages_out.append({"role": role, "content": m.content})

    return ChatResponse(
        thread_id=thread_id,
        messages=messages_out,
        current_step=result.get("current_step", "unknown"),
        needs_approval=result.get("needs_approval", False),
        proposed_action=result.get("proposed_action"),
        tool_result=result.get("tool_result"),
    )
