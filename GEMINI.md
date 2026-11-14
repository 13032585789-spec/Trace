# Trace – rules for every AI agent working in this repo

This file is read automatically by Codex (`AGENTS.md`). The same text is saved as `CLAUDE.md` (Claude Code) and `GEMINI.md` (Antigravity / Gemini agents). Full project background: `docs/handoff/` (files 01–04).

## What Trace is

Junction 2026, Stoa challenge "Make Blueprints Talk". Team **Montree**, product **Trace**. Natural-language questions about construction drawings and BIM models; every answer must be correct and show where it came from (page + highlighted box, or IFC GUID highlighted in 3D). Final submission: **Sunday 2026-11-15 10:00 Helsinki time**.

## Ownership (do not cross these lines)

- **Answer accuracy is NOT ours.** Teammate Xinran owns the data engine (DXF/IFC solvers, evaluation). Do not write solvers that duplicate his work. We only call his functions through `engine.tools` with the shared result format below.
- **Ours:** `agent/` (FastAPI + Gemini agent + vision), `web/` (React viewer, 3D), the architect's features, tech-challenge integrations, deployment, docs.
- **One file, one agent at a time.** Before editing, claim the task in `TASKS.md` (status `in progress` + your agent name). Never edit a file another agent has claimed.

| Agent | Owns |
| --- | --- |
| Gemini orchestrator (Antigravity) | `TASKS.md`, `GEMINI.md` |
| Gemini workers | new components under `web/src/` |
| Claude (Claude Code) | `agent/` |
| Codex | `tests/`, `README.md`, `.github/`, `scripts/` |

## Hard rules

1. **No secrets in code, docs or commits.** Keys live only in `.env` (git-ignored). Check `git diff` for keys before every commit. A leaked key gets every key on the project revoked.
2. **Numbers come from tools or code, never from the model.** The agent already re-checks every number in an answer against tool results; keep that check.
3. **Mock data must say `MOCK DATA`** in `warnings`. Never present it as a real answer.
4. **Shared tool-result format** (fields may be added, never renamed):
   ```json
   {"value": 2, "unit": "count",
    "items": [{"id": "...", "guid": "...", "category": "toilet", "name": "WC 1", "storey": "...", "space_id": "...", "space_name": "..."}],
    "sources": [{"file": "data/.../plan.png", "page": 1, "bbox": [x0, y0, x1, y1], "label": "WC 1"}],
    "method": "how it was computed", "warnings": []}
   ```
   `bbox` is in pixels of the PNG served by `GET /drawing?path=&page=` (PDF pages rendered at 150 dpi).
5. **Quota:** the Gemini hackathon account forbids abuse (thousands of requests can disqualify us). Nemotron runs on a free tier (about 50 requests/day). Never batch-run the whole question set through APIs; sample a few dozen questions.
6. **Data never goes into git** (`/data/`, `*.zip`). Keep each dataset's credit (`data/<source>/LICENSE.md`) when a drawing is shown.
7. **Tests must pass before a task is marked done:** `python -m pytest -q` and `cd web && npm run build`.
8. **Leave evidence for tech challenges:** mention Codex in commit messages when Codex wrote the change; log Verda work in `docs/verda-log.md`.

## Run

Windows: double-click `start.bat` (backend :8000, frontend :5173). Manual: `pip install -r agent/requirements.txt`, `uvicorn agent.app:app --reload --port 8000`, then in `web/` run `npm install` and the Vite dev server. Health check: `GET /health`. Model list: `GET /models`.

## Task board protocol (`TASKS.md`)

One row per task: `id | task | agent | status (todo / in progress / review / done) | files | acceptance test | notes`. Claim → do → run tests → write a one-line result in notes → set `review`. A critic reviews; Diletta merges.
