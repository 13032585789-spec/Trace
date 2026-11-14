"""Architect modules 3 & 4: per-room construction status and a shared room message board.

Stored in one small JSON file (CACHE_DIR/collab.json, not in git). Enough for the demo;
a real deployment would use a database.
"""
from __future__ import annotations

import json
import threading
import time

from . import config

STATUSES = ["built", "missing_wall", "pending"]
_lock = threading.Lock()


def _file():
    return config.CACHE_DIR / "collab.json"


def load() -> dict:
    f = _file()
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return {"status": {}, "messages": []}


def _save(data: dict) -> None:
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def set_status(space_id: str, status: str, author: str = "") -> dict:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    with _lock:
        data = load()
        data["status"][space_id] = {"status": status, "author": author, "ts": time.time()}
        data["messages"].append({"space_id": space_id, "author": author, "role": "system", "ts": time.time(),
                                 "text": f"Status changed to {status}", "changed": True})
        _save(data)
    return data


def post_message(space_id: str, text: str, author: str = "", role: str = "", notify: list[str] | None = None) -> dict:
    if not text.strip():
        raise ValueError("empty message")
    with _lock:
        data = load()
        data["messages"].append({"space_id": space_id, "author": author, "role": role, "text": text.strip(),
                                 "notify": notify or [], "ts": time.time(), "changed": True})
        _save(data)
    return data


def for_space(space_id: str | None) -> dict:
    data = load()
    if not space_id:
        return data
    return {"status": {k: v for k, v in data["status"].items() if k == space_id},
            "messages": [m for m in data["messages"] if m["space_id"] == space_id]}
