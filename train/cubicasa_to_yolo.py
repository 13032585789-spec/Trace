"""Convert CubiCasa5k SVG annotations to a YOLO detection dataset.
Classes: door, window, toilet, sink, shower, bathtub.
Split: every image that is in the Junction held-out test split (md5(path) % 5 == 0, same rule as eval/run.py)
is excluded from train/val and listed in split.json["junction_test"] for evaluation only."""
import os, re, sys, json, glob, math, hashlib, argparse, collections
import xml.etree.ElementTree as ET

CLASSES = ["door", "window", "toilet", "sink", "shower", "bathtub"]
# Room task: rules found by search_rules.py against the Junction answers (100% except sauna 98.9%)
#   bedroom=Space Bedroom, kitchen=Space Kitchen*, balcony=Space Outdoor Balcony*, floors=Floor,
#   wc_room=text "WC", sauna=text "SS" + Space Sauna
ROOM_CLASSES = ["bedroom", "kitchen", "balcony", "sauna", "label_wc", "label_ss", "floor"]
TASK = os.environ.get("TASK", "fixtures")

def classify_room(cls):
    t = cls.split()
    if not t: return None
    if t[0] == "Floor" and len(t) == 1: return "floor"
    if t[0] != "Space" or len(t) < 2: return None
    if t[1] == "Bedroom": return "bedroom"
    if t[1] == "Kitchen": return "kitchen"
    if t[1] == "Sauna": return "sauna"
    if t[1] == "Outdoor" and len(t) > 2 and t[2] == "Balcony": return "balcony"
    return None

def _font_size(el):
    fs = el.get("font-size") or ""
    m = re.search(r"font-size\s*:\s*([\d.]+)", el.get("style") or "")
    v = re.findall(r"[\d.]+", fs) or ([m.group(1)] if m else [])
    return float(v[0]) if v else 12.0

def classify(cls):
    t = cls.split()
    if not t: return None
    if t[0] == "Door":
        return None if len(t) > 1 and t[1] == "None" else "door"   # "Door None" = doorway without a leaf: not a door
    if t[0] == "Window": return "window"
    if t[0] in ("FixedFurniture", "Furniture") and len(t) > 1:
        k = t[1].lower()
        if "toilet" in k or k == "wc": return "toilet"
        if "sink" in k or "basin" in k or "washbasin" in k: return "sink"
        if "shower" in k and "screen" not in k: return "shower"   # ShowerScreen = glass panel, not a shower
        if "bath" in k: return "bathtub"
    return None

# ---------- affine transforms ----------
def mul(A, B):
    a, b, c, d, e, f = A; g, h, i, j, k, l = B
    return (a*g + c*h, b*g + d*h, a*i + c*j, b*i + d*j, a*k + c*l + e, b*k + d*l + f)
I = (1, 0, 0, 1, 0, 0)
def parse_transform(s):
    M = I
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", s or ""):
        v = [float(x) for x in re.findall(r"-?[\d.]+(?:e-?\d+)?", args)]
        if name == "matrix" and len(v) == 6: T = tuple(v)
        elif name == "translate": T = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale": T = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate":
            r = math.radians(v[0]); c, s_ = math.cos(r), math.sin(r); T = (c, s_, -s_, c, 0, 0)
            if len(v) == 3: T = mul(mul((1, 0, 0, 1, v[1], v[2]), T), (1, 0, 0, 1, -v[1], -v[2]))
        else: continue
        M = mul(M, T)
    return M
def apply(M, x, y): a, b, c, d, e, f = M; return a*x + c*y + e, b*x + d*y + f

_ARGS = {"M": 2, "L": 2, "T": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "A": 7, "Z": 0}
def path_points(d):
    """End points of every segment (absolute + relative commands; arcs/curves contribute their end point)."""
    toks = re.findall(r"[MLHVCSQTAZmlhvcsqtaz]|-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?", d)
    pts, x, y, sx, sy, cmd, i = [], 0.0, 0.0, 0.0, 0.0, "M", 0
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t; i += 1
            if cmd in "Zz": x, y = sx, sy; pts.append((x, y))
            continue
        n = _ARGS[cmd.upper()]
        if n == 0 or i + n > len(toks): break
        v = [float(z) for z in toks[i:i + n]]; i += n; rel = cmd.islower(); C = cmd.upper()
        if C == "H": x = x + v[0] if rel else v[0]
        elif C == "V": y = y + v[0] if rel else v[0]
        else:
            nx, ny = v[-2], v[-1]
            x, y = (x + nx, y + ny) if rel else (nx, ny)
        if C == "M": sx, sy = x, y; cmd = "l" if rel else "L"
        pts.append((x, y))
    return pts

def shape_points(el):
    tag = el.tag.split("}")[-1]; g = el.get
    nums = lambda s: [float(x) for x in re.findall(r"-?[\d.]+(?:e-?\d+)?", s or "")]
    if tag in ("polygon", "polyline"):
        v = nums(g("points")); return list(zip(v[0::2], v[1::2]))
    if tag == "rect":
        x, y, w, h = (float(g(k) or 0) for k in ("x", "y", "width", "height")); return [(x, y), (x + w, y + h)]
    if tag == "line":
        return [(float(g("x1") or 0), float(g("y1") or 0)), (float(g("x2") or 0), float(g("y2") or 0))]
    if tag in ("circle", "ellipse"):
        cx, cy = float(g("cx") or 0), float(g("cy") or 0); rx = float(g("r") or g("rx") or 0); ry = float(g("r") or g("ry") or 0)
        return [(cx - rx, cy - ry), (cx + rx, cy + ry)]
    if tag == "path":
        return path_points(g("d") or "")
    return []

def objects(svg_path):
    root = ET.parse(svg_path).getroot()
    out = []; seen_cls = collections.Counter()
    def grow(b, X, Y): b[0], b[1], b[2], b[3] = min(b[0], X), min(b[1], Y), max(b[2], X), max(b[3], Y)
    def walk(el, M, owners):
        M = mul(M, parse_transform(el.get("transform")))
        cls = el.get("class")
        if cls:
            seen_cls[" ".join(cls.split()[:2])] += 1
            if TASK == "rooms":
                c = classify_room(cls)
                if c: owners = owners + [(c, [math.inf, math.inf, -math.inf, -math.inf])]; out.append(owners[-1])
            else:
                c = classify(cls)
                if c and not owners:          # outermost annotated group owns all its geometry
                    owners = [(c, [math.inf, math.inf, -math.inf, -math.inf])]; out.append(owners[0])
        tag = el.tag.split("}")[-1]
        if TASK == "rooms" and tag == "text":
            word = re.sub(r"[^A-ZÄÖ/]", "", "".join(el.itertext()).strip().upper())
            lab = {"WC": "label_wc", "SS": "label_ss"}.get(word)
            if lab:
                xs = re.findall(r"-?[\d.]+", el.get("x") or "0"); ys = re.findall(r"-?[\d.]+", el.get("y") or "0")
                x, y = float(xs[0]) if xs else 0.0, float(ys[0]) if ys else 0.0; fs = _font_size(el)
                anchor = el.get("text-anchor") or ""
                w = 0.65 * fs * len(word); x0 = x - w / 2 if anchor == "middle" else (x - w if anchor == "end" else x)
                b = [math.inf, math.inf, -math.inf, -math.inf]
                for px, py in ((x0, y - fs), (x0 + w, y - fs), (x0, y + 0.2 * fs), (x0 + w, y + 0.2 * fs)):
                    grow(b, *apply(M, px, py))
                out.append((lab, b))
        if owners:
            for x, y in shape_points(el):
                X, Y = apply(M, x, y)
                for _, b in owners: grow(b, X, Y)
        for ch in el: walk(ch, M, owners)
    walk(root, I, [])
    w, h = root.get("width"), root.get("height")
    size = (float(re.sub(r"[^\d.]", "", w)), float(re.sub(r"[^\d.]", "", h))) if w and h else None
    return [(c, b) for c, b in out if b[0] < math.inf], seen_cls, size

def junction_name(sample_dir):     # data/cubicasa5k/<style>/<id>/  ->  <style>-<id>.png
    p = os.path.normpath(sample_dir).split(os.sep); return f"{p[-2]}-{p[-1]}.png"
def is_junction_test(name):
    return int(hashlib.md5(f"data/cubicasa5k/{name}".encode()).hexdigest(), 16) % 5 == 0

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default="data"); ap.add_argument("--inspect", action="store_true")
    a = ap.parse_args()
    samples = sorted(os.path.dirname(p) for p in glob.glob(os.path.join(a.root, "cubicasa5k", "*", "*", "model.svg")))
    print("samples:", len(samples))
    if a.inspect:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        tot = collections.Counter(); per = collections.Counter()
        for s in samples[:300]:
            objs, seen, size = objects(os.path.join(s, "model.svg")); tot.update(seen); per.update(c for c, _ in objs)
        print("annotation classes (first 2 tokens), 300 samples:"); [print(f"  {n:6d}  {k}") for k, n in tot.most_common(60)]
        print("mapped objects:", dict(per))
        for s in samples[:5]:
            sz = objects(os.path.join(s, "model.svg"))[2]
            ims = {f: Image.open(os.path.join(s, f)).size for f in os.listdir(s) if f.endswith(".png")}
            print(" ", junction_name(s), "svg", sz, ims)
        return
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    NAMES = ROOM_CLASSES if TASK == "rooms" else CLASSES
    out = os.path.join(a.root, "yolo_rooms" if TASK == "rooms" else "yolo"); inside_n = outside_n = 0; split = {"train": [], "val": [], "junction_test": []}; counts = {}
    for sub in ("images/train", "images/val", "labels/train", "labels/val"): os.makedirs(os.path.join(out, sub), exist_ok=True)
    for s in samples:
        name = junction_name(s); img = os.path.join(s, "F1_scaled.png")
        if not os.path.exists(img): continue
        objs, _, svg_size = objects(os.path.join(s, "model.svg"))
        W, H = Image.open(img).size
        sx = sy = 1.0   # SVG coordinates are already F1_scaled.png pixels (width/height attrs are only the content extent)
        counts[name] = dict(collections.Counter(c for c, _ in objs))
        if is_junction_test(name): split["junction_test"].append(s); continue
        part = "val" if int(hashlib.md5(name.encode()).hexdigest(), 16) % 10 == 0 else "train"
        split[part].append(s)
        stem = name[:-4]; dst = os.path.join(out, "images", part, stem + ".png")
        if not os.path.exists(dst): os.symlink(os.path.abspath(img), dst)
        with open(os.path.join(out, "labels", part, stem + ".txt"), "w") as f:
            for c, (x0, y0, x1, y1) in objs:
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                if 0 <= cx <= W and 0 <= cy <= H: inside_n += 1
                else: outside_n += 1
                x0, x1 = max(0, x0 * sx), min(W, x1 * sx); y0, y1 = max(0, y0 * sy), min(H, y1 * sy)
                if x1 - x0 < 2 or y1 - y0 < 2: continue
                f.write(f"{NAMES.index(c)} {(x0+x1)/2/W:.6f} {(y0+y1)/2/H:.6f} {(x1-x0)/W:.6f} {(y1-y0)/H:.6f}\n")
    sfx = "_rooms" if TASK == "rooms" else ""
    json.dump(split, open(os.path.join(a.root, "split.json"), "w")); json.dump(counts, open(os.path.join(a.root, f"annotation_counts{sfx}.json"), "w"))
    open(os.path.join(a.root, f"cubi{sfx}.yaml"), "w").write(f"path: {os.path.abspath(out)}\ntrain: images/train\nval: images/val\nnames: {json.dumps(dict(enumerate(NAMES)))}\n")
    if TASK == "rooms" and os.path.exists("room_gold.json"):   # self-check: do our boxes reproduce the answers?
        gold = json.load(open("room_gold.json")); rule = {"bedroom": ["bedroom"], "kitchen": ["kitchen"], "balcony": ["balcony"],
               "floors": ["floor"], "wc_room": ["label_wc"], "sauna": ["label_ss", "sauna"]}
        for cat, ks in rule.items():
            ns = [n for n in gold if cat in gold[n] and n in counts]
            ok = sum(sum(counts[n].get(k, 0) for k in ks) == gold[n][cat] for n in ns)
            print(f"  {cat:8s} box counts == answers: {100 * ok / max(1, len(ns)):.1f}%  (n={len(ns)})")
    print({k: len(v) for k, v in split.items()}, "->", out)
    print(f"coordinate check: {inside_n} box centres inside the image, {outside_n} outside "
          f"({100 * outside_n / max(1, inside_n + outside_n):.2f}% outside; should be close to 0)")
    tot = collections.Counter()
    for n in counts: tot.update(counts[n])
    print("objects per image (all 5000):", {k: round(v / len(counts), 2) for k, v in tot.items()})

if __name__ == "__main__":
    main()
