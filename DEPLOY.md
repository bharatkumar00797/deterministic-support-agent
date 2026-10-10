# Deployment

## What was actually broken

`deterministic-support-api` is a FastAPI project. Its `pyproject.toml` set `[tool.vercel] entrypoint` but listed no `[project] dependencies`.

Vercel installs Python with `uv sync` from `pyproject.toml`. A native `pyproject.toml` **replaces** `requirements.txt`. The function was built with zero third-party packages, so `import fastapi` killed the process before any route ran. Every path, including `/health`, returned `FUNCTION_INVOCATION_FAILED`. Editing the graph, lazy-loading it, or pointing the browser at `/api/chat` did not change that.

Dependencies now live in both `pyproject.toml` files. `requires-python` is pinned to 3.12 so `uv` can resolve them.

## Frontend

Root directory: `frontend`. Chat is same-origin `/api/chat`. Do not set `NEXT_PUBLIC_API_URL` to `http://localhost:8001` or to the Python host unless that host's `/health` returns JSON.

## Backend

Root directory may be the repository or `backend/`. Entrypoint: `index:app`. `OPENAI_API_KEY` is optional.

Local API: `uvicorn app.main:app --reload --port 8001` from `backend/`.
