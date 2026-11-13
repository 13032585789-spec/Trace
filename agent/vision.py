"""Counting objects on raster drawings (PNG/JPG scans, rendered PDF pages).

Gemini finds every instance and returns a box for each one, so the answer can be checked on the drawing.
Nemotron 3.5 Super VL counts the same thing independently; if the two disagree, the answer carries a warning.
"""
from __future__ import annotations

import base64
import json
import re

from . import config, drawings

DETECT_PROMPT = """You are reading an architectural drawing (floor plan, section or sheet).
Find EVERY instance of: {target}.
Rules:
- Return one entry per physical instance, even if several look identical.
- Only include instances that are actually drawn; do not guess hidden ones.
- If there are none, return an empty list.
Return JSON: a list of objects {{"box_2d": [ymin, xmin, ymax, xmax], "label": short text}},
with coordinates normalised to 0-1000."""

VERIFY_PROMPT = """This is an architectural drawing. Count how many of the following are drawn on it: {target}.
Count each physical instance once. Reply with JSON only: {{"count": <integer>, "notes": "<one short sentence>"}}"""


def _gemini_detect(png_bytes: bytes, target: str) -> list[dict]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    resp = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
            DETECT_PROMPT.format(target=target),
        ],
        config=types.GenerateContentConfig(
            temperature=config.TEMPERATURE,
            response_mime_type="application/json",
        ),
    )
    data = json.loads(resp.text or "[]")
    return data if isinstance(data, list) else []


def _nemotron_count(png_bytes: bytes, target: str) -> int | None:
    """Independent second count. Returns None if Nemotron is not configured or the reply cannot be parsed."""
    if not (config.NVIDIA_API_KEY and config.NEMOTRON_MODEL):
        return None
    from openai import OpenAI

    client = OpenAI(base_url=config.NEMOTRON_BASE_URL, api_key=config.NVIDIA_API_KEY, max_retries=3)
    b64 = base64.b64encode(png_bytes).decode()
    resp = client.chat.completions.create(
        model=config.NEMOTRON_MODEL,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": VERIFY_PROMPT.format(target=target)},
                ],
            }
        ],
    )
    text = resp.choices[0].message.content or ""
    m = re.search(r'"count"\s*:\s*(\d+)', text)
    return int(m.group(1)) if m else None


def count_in_drawing(path: str, target: str, page: int = 1) -> dict:
    """Tool: count objects on a raster drawing. Returns the shared tool-result format."""
    png = drawings.page_png(path, page)
    w, h = drawings.image_size(png)
    png_bytes = png.read_bytes()

    detections = _gemini_detect(png_bytes, target)
    items, sources = [], []
    for i, d in enumerate(detections, start=1):
        box = d.get("box_2d")
        if not (isinstance(box, list) and len(box) == 4):
            continue
        ymin, xmin, ymax, xmax = box
        bbox = [round(xmin / 1000 * w), round(ymin / 1000 * h), round(xmax / 1000 * w), round(ymax / 1000 * h)]
        label = f"{target} {i}"
        items.append({"id": f"{path}#{page}#{i}", "category": target, "name": label, "detector_label": d.get("label")})
        sources.append({"file": path, "page": page, "bbox": bbox, "label": label})

    warnings = []
    second = _nemotron_count(png_bytes, target)
    if second is None:
        warnings.append("Second check (Nemotron) not run")
    elif second != len(items):
        warnings.append(
            f"Gemini found {len(items)} but Nemotron counted {second}: please check the highlighted boxes"
        )

    return {
        "value": len(items),
        "unit": "count",
        "items": items,
        "sources": sources,
        "method": "Gemini box detection on the drawing image; Nemotron 3.5 Super VL independent count",
        "warnings": warnings,
        "image_size": [w, h],
        "verified_by": {"nemotron_count": second},
    }
