# Trace

Ask a construction drawing anything. Every answer shows where it came from.

Team **Montree** · Junction 2026 · Stoa challenge "Make Blueprints Talk"

## Layout

| Folder | Owner | What |
| --- | --- | --- |
| `engine/` | A (Xinran) | Data index + exact query tools (`engine.tools`), DXF / IFC solvers, eval |
| `agent/` | B (Diletta) | FastAPI `/ask`, Gemini agent with function calling, vision counting (Gemini + Nemotron), drawing renderer |
| `web/` | B | React app: question box, answer + evidence list, drawing viewer with boxes (3D IFC viewer next) |
| `mock/` | both | Example tool results in the shared format; the agent falls back to them until `engine.tools` exists |
| `tests/` | both | Run without data or API keys |

Data never goes into git. Point `DATA_DIR` at the unzipped dataset folder (the one that contains `data/` and `questions.jsonl`).

## Run

Backend:

```bash
cp .env.example .env            # fill in GEMINI_API_KEY, NVIDIA_API_KEY, NEMOTRON_MODEL, DATA_DIR
pip install -r agent/requirements.txt
python -m agent.list_models     # check which Gemini model name to put in GEMINI_MODEL
uvicorn agent.app:app --reload --port 8000
```

Frontend (in `web/`): `npm install`, then start the Vite dev server with the `dev` script and open http://localhost:5173. It forwards `/api` to port 8000.

Tests: `python -m pytest -q`

## Shared tool-result format

Every tool (engine or vision) returns:

```json
{"value": 2, "unit": "count",
 "items": [{"id": "...", "guid": "...", "category": "toilet", "name": "WC 1", "storey": "2. krs", "space_id": "B204"}],
 "sources": [{"file": "data/.../plan.pdf", "page": 1, "bbox": [410, 220, 470, 260], "label": "WC 1"}],
 "method": "how it was computed", "warnings": []}
```

`bbox` is `[x0, y0, x1, y1]` in pixels of the PNG served by `GET /drawing?path=&page=` (PDF pages rendered at 150 dpi, images as-is). Fields are only ever added, never renamed.

## API

- `POST /ask {question, path?, role?}` → `{answer_text, evidence, tool_calls}`
- `GET /drawing?path=&page=` → PNG
- `GET /questions?source=&limit=` → sample questions from `questions.jsonl`

## Rules the agent follows

- Numbers come from tools, never from the model; an answer with a number no tool returned is regenerated once, then flagged.
- Gemini temperature 0, at most 5 tool steps.
- On raster drawings, Gemini draws a box around every instance it counts; Nemotron 3.5 Super VL counts independently and a mismatch is shown as a warning.

## Tech challenges

| Challenge | Where |
| --- | --- |
| Gemini API | `agent/agent.py` (function calling), `agent/vision.py` (box detection) |
| Nemotron | `agent/vision.py` `_nemotron_count`: independent second count on every vision answer |
| Verda Compute Track | batch preprocessing of the dataset; process log in `docs/verda-log.md` |
| Codex | used during development (see commit messages) |
| Gemma | to do, after the core is 100% |
| CRACI | `.github/workflows/ci.yml` runs on `runs-on: craci` |

Dataset licences: each `data/<source>/LICENSE.md`; keep the credit when showing a drawing.
