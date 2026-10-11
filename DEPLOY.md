# Deployment

Two Vercel projects deploy from `main` of this repo.

| Project | Root directory | Serves |
|---|---|---|
| `deterministic-support-agent` | `frontend` | the chat page |
| `deterministic-support-api` | repo root (or `backend/`) | FastAPI, entrypoint `index:app` |

## Why edits sometimes did not show up

Until now there were two copies of the agent: the Python graph and a TypeScript port in the frontend. The page called the Python API and silently switched to the TypeScript copy when that call failed, so a fix to one could look like it had no effect. The TypeScript copy and its `/api/chat` route are removed. Python is the only agent.

## Settings

- Frontend: `NEXT_PUBLIC_API_URL` is optional. It is read at build time and must be the API origin with no `/chat` and no trailing path. Unset, the page uses the public API above (or `http://localhost:8001` when opened on localhost). Changing it needs a redeploy.
- API: no variables are required. `OPENAI_API_KEY` is optional and unused by the rule-based path.
- Vercel installs Python packages from `pyproject.toml` (it takes priority over `requirements.txt`). Keep the dependency lists in `pyproject.toml`, `backend/pyproject.toml`, `requirements.txt` and `backend/requirements.txt` identical.

## Checking a deploy

```bash
curl https://deterministic-support-api.vercel.app/health
curl -X POST https://deterministic-support-api.vercel.app/chat \
  -H 'content-type: application/json' -d '{"message":"Where is order 44002?"}'
```
