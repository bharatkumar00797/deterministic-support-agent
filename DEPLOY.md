# Deployment Guide

## What was actually broken

The Vercel project only builds `frontend`. Production had **no environment variables**, so the chat bundle called `http://localhost:8001`. The FastAPI backend was never deployed. Even after a boot, Approve restarted the graph at classify, so the word "approve" was treated as a new intent and the refund never ran.

Railway cannot be connected from Grok. The Python API is a second Vercel project with root directory `backend`. Each `/chat` call sends the case snapshot back, so approval still works when a new instance handles the next click.

## Frontend

1. Root directory stays `frontend`.
2. `NEXT_PUBLIC_API_URL` is the Python API origin, with no `/chat` suffix. The browser posts to `{NEXT_PUBLIC_API_URL}/chat`.
3. If that variable is unset, or still points at localhost, the page uses same-origin `/api/chat`.

## Backend

1. Root directory `backend`. Framework FastAPI. Entrypoint `app.main:app`.
2. `OPENAI_API_KEY` is optional. With no key, intent is classified by rules.
3. Local: `uvicorn app.main:app --reload --port 8001`

## Local frontend

```bash
cd frontend && npm install && npm run dev
```

Copy `frontend/.env.example` to `frontend/.env.local` only when you want the Next app to call the Python API.
