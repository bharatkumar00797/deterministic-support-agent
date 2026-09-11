# Deployment Guide

## Backend → Railway

1. Create a new project on Railway from the GitHub repo `deterministic-support-agent`.
2. Set root directory to `backend` (or use the included Dockerfile).
3. Add environment variable `OPENAI_API_KEY` (optional but recommended).
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Deploy and copy the public URL.

## Frontend → Vercel

1. Import the same repo on Vercel.
2. Set **Root Directory** = `frontend`.
3. Environment variable:
   - `NEXT_PUBLIC_API_URL` = your Railway backend URL
4. Deploy.

## Local

```bash
# Backend on 8001
cd backend && uvicorn app.main:app --reload --port 8001

# Frontend
cd frontend && npm install && npm run dev
```
