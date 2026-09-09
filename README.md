# Deterministic Support Agent

An AI customer support agent that **actually completes multi-step tasks** (process refunds, cancel subscriptions, update account details) instead of only answering questions.

## Key Design Principle: Deterministic
- LLM reasons about intent and next step
- Explicit LangGraph state machine + Pydantic validation controls the actual execution path
- Code-governed edges, not free-form generation, decide what happens
- Human-in-the-loop approval gates for high-risk actions
- Full audit trail of every decision and tool call

## Tech Stack
- **Agent Orchestration**: LangGraph
- **Backend**: FastAPI
- **Frontend**: Next.js 15 + TypeScript + Tailwind
- **Database**: PostgreSQL (for conversation state / checkpoints)
- **LLM**: OpenAI / Anthropic (pluggable)
- **Hosting**: Vercel (frontend) + Railway (backend)

## Project Structure
```
deterministic-support-agent/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── agent/          # LangGraph graphs & nodes
│   │   ├── tools/          # Deterministic action tools
│   │   ├── models/
│   │   └── routers/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
├── docker-compose.yml
└── README.md
```

## Supported Actions (MVP)
- Process refund (with amount validation)
- Cancel subscription
- Update account details (email, address, etc.)
- Order status lookup
- Escalate to human

## Quick Start

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install && npm run dev
```

## Status
Day 1 scaffold complete. Weekly roadmap tracked in GitHub Issues.

Built with Grok.
