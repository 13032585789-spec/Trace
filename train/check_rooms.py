"""Which SVG signal reproduces the room-type answers?  python check_rooms.py room_gold.json
Compares, per category, counts of Space classes and counts of text labels in model.svg with the Junction answers."""
import os, sys, re, json, glob, collections
import xml.etree.ElementTree as ET
gold = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "room_gold.json"))
dirs = {f"{d.split(os.sep)[-2]}-{d.split(os.sep)[-1]}.png": d for d in
        (os.path.dirname(p) for p in glob.glob("data/cubicasa5k/*/*/model.svg"))}
def signals(svg):
    root = ET.parse(svg).getroot(); sp = collections.Counter(); tx = collections.Counter(); floors = 0
    for el in root.iter():
        cls = el.get("class") or ""
        if cls.startswith("Space "): sp[" ".join(cls.split()[:2])] += 1; sp[cls] += 1
        if cls.startswith("Floor"): floors += 1
        tag = el.tag.split("}")[-1]
        if tag in ("text", "tspan") and (el.text or "").strip():
            tx[re.sub(r"[^A-ZÄÖ/]", "", el.text.strip().upper())] += 1
        nm = el.get("name") or el.get("id") or ""
    return sp, tx, floors
rows = []
for n, g in list(gold.items()):
    if n in dirs: rows.append((g, *signals(os.path.join(dirs[n], "model.svg"))))
print("plans checked:", len(rows))
alltx = collections.Counter(); [alltx.update(t) for _, _, t, _ in rows]
print("most common text labels:", alltx.most_common(30))
cands = {
 "bedroom": [("Space Bedroom",), ("txt:MH",)], "bathroom": [("Space Bath",), ("txt:KH", "txt:PH", "txt:KPH", "txt:PESUH", "txt:SH")],
 "sauna": [("Space Sauna",), ("txt:S", "txt:SAUNA")], "wc_room": [("Space Toilet",), ("txt:WC",)],
 "balcony": [("Space Outdoor Balcony", "Space Outdoor Balcony Glazed"), ("Space Outdoor",), ("txt:PARV", "txt:PARVEKE", "txt:LASPARV")],
 "kitchen": [("Space Kitchen",), ("txt:K", "txt:KK", "txt:KT", "txt:TK")], "floors": [("floors",)]}
for cat, rules in cands.items():
    res = []
    for rule in rules:
        ok = n = 0
        for g, sp, tx, fl in rows:
            if cat not in g: continue
            v = fl if rule == ("floors",) else sum(tx.get(r[4:], 0) if r.startswith("txt:") else sp.get(r, 0) for r in rule)
            n += 1; ok += v == g[cat]
        res.append(f"{'+'.join(rule)}: {100 * ok / max(n, 1):.1f}%")
    print(f"{cat:9s}", " | ".join(res))
