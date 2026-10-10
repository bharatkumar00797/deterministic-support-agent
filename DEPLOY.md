# Deployment

## What is actually broken

The page at https://deterministic-support-agent.vercel.app is a Next.js app whose root directory is `frontend`. Chat runs at same-origin `/api/chat`.

`NEXT_PUBLIC_API_URL` is inlined into the browser bundle. Production currently inlines `https://deterministic-support-api.vercel.app`. That host answers every path, including `/health`, with `FUNCTION_INVOCATION_FAILED`. The browser never reaches the working `/api/chat` route. Hitting `/api/chat` directly succeeds, which is why earlier checks said the app was fine.

Do not set `NEXT_PUBLIC_API_URL` on the frontend project. Leave it unset. A localhost value is also ignored once the page is not on localhost.

The Python project only boots if its Vercel root directory is `backend` (requirements live there) or the repository root (root `requirements.txt` + `index.py`). It is not required for the live demo.

## Frontend

Root directory: `frontend`. No environment variables.

## Backend (optional)

Root directory: `backend`. Entrypoint: `index:app` (`backend/index.py`). `OPENAI_API_KEY` is optional.

Local API: `uvicorn app.main:app --reload --port 8001` from `backend/`.
Local UI, only if you want the Python API: copy `frontend/.env.example` to `frontend/.env.local`.
