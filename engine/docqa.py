"""Questions about schedules and text on vector drawing sheets (PDFs with a text layer), e.g. door / window /
finish schedules: "how many doors are type A1", "total area of rooms named OFFICE", "width of door 121.A".

The model never does the arithmetic. It only picks the schedule rows that satisfy the question and names the
operation; this module recomputes the answer from those rows (count / sum of a column / max / lookup), so every
number comes with the rows it was computed from (evidence). If the model's own answer disagrees with the
recomputed one, the recomputed one is returned and a warning is added.

extract(pdf) needs pdfplumber; the extraction is cached as JSON next to the cache dir so the model step can run
on a machine without pdfplumber (see tools/docqa_run.py)."""
import os, re, json, hashlib

CACHE = os.path.join(os.environ.get("JUNCTION_CACHE", os.path.expanduser("~/.cache/junction-engine")), "docqa")

def _clean(c):
    return re.sub(r"\s+", " ", str(c or "")).strip()

def extract(pdf_path, max_pages=4):
    """-> {"file", "pages": [{"page", "size", "text", "tables": [{"id", "bbox", "rows": [[str]]}]}]} (cached)."""
    st = os.stat(pdf_path)
    key = hashlib.md5(f"{os.path.abspath(pdf_path)}|{st.st_size}|{st.st_mtime}".encode()).hexdigest()
    cp = os.path.join(CACHE, key + ".json")
    if os.path.exists(cp): return json.load(open(cp))
    import pdfplumber
    out = {"file": os.path.basename(pdf_path), "pages": []}
    with pdfplumber.open(pdf_path) as pdf:
        for pi, pg in enumerate(pdf.pages[:max_pages]):
            tabs = []
            for ti, t in enumerate(pg.find_tables()):
                rows = [[_clean(c) for c in r] for r in t.extract()]
                rows = [r for r in rows if any(r)]
                if len(rows) < 2 or max(len(r) for r in rows) < 2: continue
                if any(len(c) > 600 for r in rows for c in r): continue        # a whole sheet merged into one cell
                tabs.append({"id": f"p{pi}t{ti}", "bbox": [round(v, 1) for v in t.bbox], "rows": rows})
            text = pg.extract_text(layout=True) or ""
            out["pages"].append({"page": pi, "size": [pg.width, pg.height], "text": text, "tables": tabs})
    os.makedirs(CACHE, exist_ok=True); json.dump(out, open(cp, "w"))
    return out

def _words(s): return set(re.findall(r"[a-z0-9]{2,}", (s or "").lower()))

def context(doc, question, max_chars=60000):
    """Serialise the tables most related to the question (all of them if they fit), each row numbered."""
    q = _words(question); parts = []
    tabs = [(p["page"], t) for p in doc["pages"] for t in p["tables"]]
    tabs.sort(key=lambda pt: -len(q & _words(" ".join(" ".join(r) for r in pt[1]["rows"][:3]))))
    used = 0
    for page, t in tabs:
        body = "\n".join(f"  r{i}: " + " | ".join(r) for i, r in enumerate(t["rows"]))
        block = f"TABLE {t['id']} (page {page}, {len(t['rows'])} rows)\n{body}\n"
        if used + len(block) > max_chars: continue
        parts.append(block); used += len(block)
    text = "\n".join(p["text"] for p in doc["pages"])[: max(0, max_chars - used)]
    return "\n".join(parts) + ("\nPAGE TEXT (layout):\n" + text if text.strip() else "")

PROMPT = """You answer a question about one architectural drawing sheet, using ONLY the tables and text below.
Tables are numbered TABLE <id> with rows r0, r1, ... (header rows included; some headers span two rows).
Do not count or add numbers yourself in your head: select the rows that satisfy the question and say what to compute.
Return JSON only:
{"op": "count" | "sum" | "max" | "min" | "lookup" | "none",
 "table": "<table id>",
 "rows": [<row numbers of DATA rows that satisfy the question; never header rows>],
 "column": "<for sum/max/min: the column header whose numbers to use; for count of a quantity column (e.g. 'Count') use op sum>",
 "column_index": <0-based index of that column in the rows>,
 "answer": "<your final answer as the question expects it>",
 "reason": "<one sentence>"}
Use op "lookup" for a value read from a cell (answer = that cell text, rows = [that row]). Use op "none" with answer
"not found" if the sheet does not contain the information.

QUESTION: {q}

{ctx}"""

def _num(s):
    s = str(s).replace(",", "")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None

def compute(doc, resp):
    """Recompute the model's selection. -> (value, evidence rows, warnings)."""
    warn = []
    tabs = {t["id"]: t for p in doc["pages"] for t in p["tables"]}
    t = tabs.get(resp.get("table")); rows = [r for r in resp.get("rows") or [] if isinstance(r, int)]
    if t is None: return resp.get("answer"), [], ["model did not cite a table; answer not recomputed"]
    sel = [(i, t["rows"][i]) for i in rows if 0 <= i < len(t["rows"])]
    if len(sel) != len(rows): warn.append("some cited rows do not exist")
    ev = [{"table": t["id"], "row": i, "cells": r} for i, r in sel]
    op = resp.get("op"); ci = resp.get("column_index")
    if op == "count": return len(sel), ev, warn
    if op in ("sum", "max", "min"):
        if not isinstance(ci, int): return resp.get("answer"), ev, warn + ["no column index; answer not recomputed"]
        vals = [_num(r[ci]) for _, r in sel if ci < len(r)]
        if any(v is None for v in vals): warn.append("non-numeric cells skipped")
        vals = [v for v in vals if v is not None]
        if not vals: return resp.get("answer"), ev, warn + ["no numbers in the cited cells"]
        v = sum(vals) if op == "sum" else max(vals) if op == "max" else min(vals)
        return (int(v) if float(v).is_integer() else round(v, 2)), ev, warn
    return resp.get("answer"), ev, warn

def answer(pdf_path, question, call_model):
    """call_model(prompt) -> JSON dict. Returns the engine evidence dict."""
    doc = extract(pdf_path)
    if not any(p["tables"] or p["text"].strip() for p in doc["pages"]):
        return {"value": None, "unit": None, "items": [], "sources": [{"file": pdf_path}], "method": "docqa:no_text_layer",
                "warnings": ["this sheet has no text layer (scan); use the vision path"]}
    resp = call_model(PROMPT.replace("{q}", question).replace("{ctx}", context(doc, question)))
    v, ev, warn = compute(doc, resp)
    model_ans = resp.get("answer")
    if resp.get("op") in ("count", "sum", "max", "min") and _num(model_ans) is not None and v is not None and _num(v) is not None \
            and abs(_num(model_ans) - _num(v)) > 1e-6:
        warn.append(f"model said {model_ans}, recomputed from the cited rows: {v}")
    return {"value": v, "unit": None, "items": ev, "sources": [{"file": pdf_path}],
            "method": f"docqa:{resp.get('op')}", "warnings": warn,
            "evidence": {"rule": resp.get("reason"), "table": resp.get("table"), "column": resp.get("column"),
                         "rows": ev, "model_answer": model_ans}}
