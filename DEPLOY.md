# Deployment

## What was actually broken

`deterministic-support-api` is a FastAPI project. Its `pyproject.toml` set `[tool.vercel] entrypoint` but listed no `[project] dependencies`.

Vercel installs Python with `uv sync` from `pyproject.toml`. A native `pyproject.toml` **replaces** `requirements.txt`. The function was built with zero third-party packages, so `import fastapi` killed the process before any route ran. Every path, including `/health`, returned `FUNCTION_INVOCATION_FAILED`. Editing the graph, lazy-loading it, or pointing the browser at `/api/chat` did not change that.

Dependencies now live in both `pyproject.toml` files. `requires-python` is pinned to 3.12 so `uv` can resolve them.

## Frontend

Root directory: `frontend`.

`NEXT_PUBLIC_API_URL` must be the public Python host (`https://deterministic-support-api.vercel.app`), never `http://localhost:8001`. The page posts to `{API_URL}/chat` and includes the case snapshot. If that request fails, it falls back to same-origin `/api/chat`.

A loopback value is ignored unless the page itself is on localhost. That was the failure that kept coming back: the production bundle called a laptop, or called this API while the function was crashing on boot.

## Backend

Root directory may be the repository or `backend/`. Entrypoint: `index:app`. `OPENAI_API_KEY` is optional.

Local API: `uvicorn app.main:app --reload --port 8001` from `backend/`.
