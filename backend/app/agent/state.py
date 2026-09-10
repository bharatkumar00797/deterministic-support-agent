from typing import Annotated, List, Optional, Literal, Dict, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class SupportState(TypedDict):
    """State for the deterministic support agent."""
    messages: Annotated[List[BaseMessage], add_messages]
    customer_id: Optional[str]
    intent: Optional[str]  # refund, cancel, update_account, order_status, escalate, other
    current_step: str
    proposed_action: Optional[Dict[str, Any]]
    needs_approval: bool
    approved: Optional[bool]
    tool_result: Optional[Dict[str, Any]]
    error: Optional[str]
