"""The tools Gemini can call, and how each call is dispatched.

Tools from the data engine (developer A, package `engine.tools`) are used when they exist;
until then each returns the mock in mock/<tool>.json, marked with a warning so it can never
be mistaken for a real answer.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Callable

from . import vision

MOCK_DIR = Path(__file__).resolve().parent.parent / "mock"

CATEGORIES = ["toilet", "sink", "shower", "bathtub", "sauna", "door", "window", "light",
              "room", "balcony", "stair", "apartment", "kitchen", "bedroom", "other"]

_S = {"type": "string"}
_I = {"type": "integer"}


def _decl(name: str, description: str, props: dict, required: list[str]) -> dict:
    return {"name": name, "description": description,
            "parameters": {"type": "object", "properties": props, "required": required}}


DECLARATIONS = [
    _decl("list_spaces", "List rooms/spaces in an IFC model, optionally filtered by storey or by a name fragment "
          "(e.g. 'WC', 'KPH', 'Bad'). Use first to find which rooms a question means.",
          {"path": _S, "storey": _S, "name_contains": _S}, ["path"]),
    _decl("count_elements", "Count building elements of one category in an IFC model, optionally within a storey or space.",
          {"path": _S, "category": {"type": "string", "enum": CATEGORIES}, "storey": _S, "space_id": _S},
          ["path", "category"]),
    _decl("elements_in_space", "List every element inside one space of an IFC model.",
          {"path": _S, "space_id": _S}, ["path", "space_id"]),
    _decl("space_area", "Net floor area of one space in an IFC model, in m2.",
          {"path": _S, "space_id": _S}, ["path", "space_id"]),
    _decl("locate_elements", "Where elements of a category are (storey, space, coordinates, drawing tag).",
          {"path": _S, "category": {"type": "string", "enum": CATEGORIES}, "storey": _S, "space_id": _S},
          ["path", "category"]),
    _decl("element_status", "Construction status (new / existing / demolish) if the model records it.",
          {"path": _S, "category": _S, "space_id": _S}, ["path"]),
    _decl("search_drawings", "Search the text written on a PDF/vector drawing (room names, tags, schedules).",
          {"path": _S, "text": _S}, ["path", "text"]),
    _decl("count_in_drawing", "Count objects drawn on a raster drawing (PNG/JPG scan or a PDF page) using vision. "
          "Use for image and scanned drawings, where there is no model to query. "
          "`target` is a short English description, e.g. 'toilet bowls (WC seats)'.",
          {"path": _S, "target": _S, "page": _I}, ["path", "target"]),
]

ENGINE_TOOLS = {"list_spaces", "count_elements", "elements_in_space", "space_area",
                "locate_elements", "element_status", "search_drawings"}


def _engine_fn(name: str) -> Callable[..., dict] | None:
    try:
        mod = importlib.import_module("engine.tools")
    except ImportError:
        return None
    return getattr(mod, name, None)


def _mock(name: str) -> dict:
    f = MOCK_DIR / f"{name}.json"
    data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {
        "value": None, "unit": None, "items": [], "sources": [], "method": "none", "warnings": []}
    data = dict(data)
    data["warnings"] = list(data.get("warnings", [])) + ["MOCK DATA: engine tool not implemented yet"]
    return data


def call(name: str, args: dict[str, Any]) -> dict:
    """Run one tool call and always return the shared result format (never raise to the model)."""
    try:
        if name == "count_in_drawing":
            return vision.count_in_drawing(**args)
        if name in ENGINE_TOOLS:
            fn = _engine_fn(name)
            return fn(**args) if fn else _mock(name)
        return {"value": None, "items": [], "sources": [], "method": "none",
                "warnings": [f"unknown tool {name}"]}
    except Exception as e:  # report to the model instead of crashing the request
        return {"value": None, "items": [], "sources": [], "method": "error",
                "warnings": [f"{type(e).__name__}: {e}"]}
