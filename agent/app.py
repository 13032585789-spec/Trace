"""HTTP API for the web app.

POST /ask      {question, path?, role?} -> {answer_text, evidence, tool_calls}
GET  /drawing  ?path=...&page=1         -> PNG of that drawing page (bbox pixel space)
GET  /questions?source=...&limit=...    -> sample questions from questions.jsonl, for the demo picker
"""
from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import agent, config, drawings

app = FastAPI(title="Trace API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class AskIn(BaseModel):
    question: str
    path: str | None = None
    role: str | None = None


@app.get("/health")
def health():
    return {"ok": True, "data_dir": str(config.DATA_DIR), "data_found": config.DATA_DIR.exists(),
            "gemini_key": bool(config.GEMINI_API_KEY), "nemotron": bool(config.NVIDIA_API_KEY and config.NEMOTRON_MODEL)}


@app.post("/ask")
def ask(body: AskIn):
    if body.path:
        try:
            drawings.resolve(body.path)
        except drawings.DrawingError as e:
            raise HTTPException(404, str(e))
    return agent.ask(body.question, body.path, body.role)


@app.get("/drawing")
def drawing(path: str, page: int = 1):
    try:
        return FileResponse(drawings.page_png(path, page), media_type="image/png")
    except drawings.DrawingError as e:
        raise HTTPException(404, str(e))


@app.get("/questions")
def questions(source: str | None = None, limit: int = 50):
    f = config.DATA_DIR / "questions.jsonl"
    if not f.exists():
        raise HTTPException(404, "questions.jsonl not found in DATA_DIR")
    out = []
    with f.open(encoding="utf-8") as fh:
        for line in fh:
            q = json.loads(line)
            if source and f"/{source}/" not in q["path"]:
                continue
            out.append(q)
            if len(out) >= limit:
                break
    return out
