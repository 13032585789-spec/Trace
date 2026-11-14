"""Greedy search: which sum of SVG signals (text labels and annotation classes) reproduces each room answer?
python search_rules.py room_gold.json"""
import os, sys, re, json, glob, collections
import xml.etree.ElementTree as ET
gold = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "room_gold.json"))
dirs = {f"{d.split(os.sep)[-2]}-{d.split(os.sep)[-1]}.png": d for d in
        (os.path.dirname(p) for p in glob.glob("data/cubicasa5k/*/*/model.svg"))}
def signals(d):
    root = ET.parse(os.path.join(d, "model.svg")).getroot(); c = collections.Counter()
    for el in root.iter():
        cls = el.get("class") or ""
        if cls:
            t = cls.split()
            for k in range(1, min(4, len(t)) + 1): c["cls:" + " ".join(t[:k])] += 1
        if el.tag.split("}")[-1] in ("text", "tspan") and (el.text or "").strip():
            raw = el.text.strip().upper(); c["txt:" + re.sub(r"[^A-ZÄÖ/]", "", raw)] += 1
            for part in re.split(r"[/+ ,]", raw):
                p = re.sub(r"[^A-ZÄÖ]", "", part)
                if p: c["part:" + p] += 1
    c["files:F_scaled"] = len(glob.glob(os.path.join(d, "F*_scaled.png")))
    return c
rows = [(g, signals(dirs[n])) for n, g in gold.items() if n in dirs]
print("plans:", len(rows))
for cat in ["sauna", "bathroom", "kitchen", "floors", "bedroom", "wc_room", "balcony"]:
    R = [(g[cat], s) for g, s in rows if cat in g]
    pool = collections.Counter()
    for _, s in R: pool.update(s.keys())
    keys = [k for k, n in pool.items() if n >= 20]
    chosen = []; best = sum(y == 0 for y, _ in R) / len(R)
    for _ in range(6):
        cand = None
        for k in keys:
            if k in chosen: continue
            acc = sum(sum(s.get(x, 0) for x in chosen + [k]) == y for y, s in R) / len(R)
            if acc > best + 1e-9: best, cand = acc, k
        if not cand: break
        chosen.append(cand)
    print(f"{cat:9s} n={len(R):5d}  {100 * best:5.1f}%  rule = sum of {chosen}")
