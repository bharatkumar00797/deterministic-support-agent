# Deterministic Support Agent

A demo of a customer support agent for a made-up customer (Mira Sen). It handles refunds, subscription cancellation, account updates (email, phone, address) and order status. Refunds and cancellations stop at a human Approve / Reject step. **All actions are simulated.** No money moves and no real account is touched.

- Frontend: https://deterministic-support-agent.vercel.app
- API: https://deterministic-support-api.vercel.app (`/health`, `POST /chat`)

## How it works

- There is one agent, the Python LangGraph graph in `backend/app/agent/`. The Next.js page in `frontend/` only shows the chat and calls `POST {API}/chat`. It has no agent logic of its own and no fallback. If the API is unreachable the page shows an error and nothing changes.
- Intent is picked with plain rules (an OpenAI key is optional and not needed). Code, not the model, decides what runs.
- Refund and cancel requests produce a proposal and stop at the gate. The tool runs only after Approve. Reject changes nothing. Any other message while a proposal is waiting leaves it waiting.
- A refund must match the order total, the order must exist, and an order already in the ledger is refused. The same checks run again when the tool executes.
- The API keeps no state. Every request carries the case snapshot (ledger, pending proposal, audit trail) and the response returns the updated one. The browser holds it between turns. The snapshot is not signed, so a client can edit its own ledger. That is acceptable for a demo and not for real money.
- Test data: orders ORD-12345 ($49.99, delivered), ORD-44002 ($18.50, shipped), ORD-77821 ($129.00, already refunded).

Layout: `backend/support_api.py` (FastAPI), `backend/app/agent/` (graph and nodes), `backend/app/tools/` (simulated tools), `backend/tests/`, `frontend/`, `index.py` (entry when the Vercel project root is the repo).

## Run locally

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn support_api:app --reload --port 8001
```

```bash
cd frontend
npm install && npm run dev
```

Open http://localhost:3000. On localhost the page calls `http://localhost:8001`. Elsewhere it calls the public API unless `NEXT_PUBLIC_API_URL` is set.

Things to try: "Refund order 12345", "Cancel my subscription", "Where is order 44002?", "Update my email address to mira@example.com", "address: 9 Market Street, Oakland".

## Run tests

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```

Python 3.12 is what Vercel and CI use. The tests cover order status, refunds (amount check, approve, reject, repeat), cancellation, each account field, a waiting gate, and tampered snapshots. CI (`.github/workflows/ci.yml`) runs them and builds the frontend on every push and pull request.

## Deploy

See [DEPLOY.md](./DEPLOY.md).
