# Deterministic Support Agent

An AI customer support agent that **actually completes multi-step tasks** (refunds, cancellations, account updates) using reliable LangGraph workflows.

## Key Design
- LLM reasons about intent
- **Code-governed edges** decide the execution path
- Pydantic validation on every tool call
- Human-in-the-loop approval for high-risk actions (refunds, cancellations)
- Full audit trail via state + checkpoints

## Tech Stack
- **Agent**: LangGraph + LangChain
- **Backend**: FastAPI
- **Frontend**: Next.js 15 + TypeScript + Tailwind
- **Tools**: Deterministic Python functions with validation

## Quick Start

### Backend (port 8001)
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Optional: export OPENAI_API_KEY=sk-...
uvicorn app.main:app --reload --port 8001
```

### Frontend (port 3000)
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

## Example Flows
1. User: “I want a refund for my last order”
2. Agent classifies → proposes `process_refund`
3. UI shows **Approve / Reject** buttons
4. On approve → tool executes → confirmation message

Works without an OpenAI key (heuristic fallback for local demos).

## Status
- Core LangGraph agent ✅
- Deterministic tools ✅
- HITL approval path ✅
- Chat UI ✅
- Deployment ⏳

Built with Grok.
