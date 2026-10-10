# Deployment Guide

## What was actually broken

The Vercel project only builds `frontend`. Production had **no environment variables**, so the chat bundle called `http://localhost:8001`. The FastAPI backend was never deployed (see issue #5), and it also could not boot: `Literal` was used in `nodes.py` without being imported. Even after a boot, Approve restarted the graph at classify, so the word "approve" was treated as a new intent and the refund never ran.

## Frontend → Vercel (works without a second host)

1. Root directory stays `frontend`.
2. Leave `NEXT_PUBLIC_API_URL` unset. The app then posts to `/api/chat` on the same deployment. That route is stateless: the browser sends the case snapshot back, so approval survives a new serverless instance.
3. Optional: set `NEXT_PUBLIC_API_URL` to a long-running backend if you want the Python graph instead.

## Backend → Railway (optional)

1. Root directory `backend`, or the included Dockerfile.
2. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. `OPENAI_API_KEY` is optional. With no key, intent is classified by rules.
4. Point the frontend's `NEXT_PUBLIC_API_URL` at that public URL and redeploy the frontend so the value is baked in.

## Local

```bash
# Backend on 8001
cd backend && uvicorn app.main:app --reload --port 8001

# Frontend (uses /api/chat unless NEXT_PUBLIC_API_URL is set)
cd frontend && npm install && npm run dev
```

Copy `frontend/.env.example` to `frontend/.env.local` only when you want the Next app to call the Python API.
