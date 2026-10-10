# Deterministic Support Agent

An AI customer support agent that **actually completes multi-step tasks** (refunds, cancellations, account updates). Risky tools stop at a human gate. The ledger only changes after Approve.

**Live:** https://deterministic-support-agent.vercel.app

The chat on that URL does not call `localhost`. Vercel only builds the Next.js app, so `/api/chat` runs the same gate in the deployment and the browser sends the case snapshot back. A separate Railway process is optional. Do not set `NEXT_PUBLIC_API_URL` to `http://localhost:8001` on Vercel — that is what made every message fail in the browser.

## Why “Deterministic”?
Most support bots only chat. This one:
- Uses an LLM only for intent understanding and proposals
- Lets **code-controlled edges** decide the real execution path
- Validates every tool call with Pydantic
- Requires human approval for high-risk actions (refunds, cancellations)
- Keeps full state + checkpoints for auditability

## Tech Stack
- **Orchestration**: LangGraph
- **Backend**: FastAPI
- **Frontend**: Next.js 15 + TypeScript + Tailwind
- **Tools**: Pure Python functions with strict validation

## Quick Start

### Backend (port 8001)
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Optional but recommended:
# export OPENAI_API_KEY=sk-...
uvicorn app.main:app --reload --port 8001
```

### Frontend
```bash
cd frontend
npm install && npm run dev
```
Open → http://localhost:3000

### Try these prompts
- “I want a refund for order 12345”
- “Please cancel my subscription”
- “Update my email address”

You will see an **Approve / Reject** card for risky actions.

## Deploy
See [DEPLOY.md](./DEPLOY.md).

## Project Status
| Area                    | Status      |
|-------------------------|-------------|
| LangGraph workflow      | ✅ Complete |
| Deterministic tools     | ✅ Complete |
| Human-in-the-loop       | ✅ Complete |
| Chat UI + approvals     | ✅ Complete |
| Deployment ready        | ✅ Yes      |
