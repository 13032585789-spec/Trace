"""Tiled inference for large plans (on the GPU machine):   python predict_tiled.py
Images whose longest side is > 1600 px are cut into 1280 px tiles (256 px overlap) at native resolution;
each tile keeps only boxes whose centre falls in its own core area, so nothing is counted twice.
Writes det_cache_tiled.zip with _raw_detections.json (same format as predict_counts.py) for val + test."""
import os, sys, json, glob, shutil
from PIL import Image
from ultralytics import YOLO
Image.MAX_IMAGE_PIXELS = None
CLASSES = ["door", "window", "toilet", "sink", "shower", "bathtub"]
here = os.path.dirname(os.path.abspath(__file__))
split = json.load(open(os.path.join(here, "data", "split.json")))
w = sorted((p for p in glob.glob(os.path.join(os.path.expanduser("~"), "**", "cubi*", "weights", "best.pt"), recursive=True)
            if ".venv" not in p), key=os.path.getmtime)
model = YOLO(sys.argv[1] if len(sys.argv) > 1 else w[-1]); print("weights:", sys.argv[1] if len(sys.argv) > 1 else w[-1])
TILE, OV, BIG = 1280, 256, 1600
name_of = lambda s: f"{os.path.normpath(s).split(os.sep)[-2]}-{os.path.normpath(s).split(os.sep)[-1]}.png"

def run(img):
    W, H = img.size
    if max(W, H) <= BIG:
        r = model.predict(img, imgsz=TILE, conf=0.05, verbose=False)[0]
        return [[CLASSES[int(c)], round(float(p), 3)] + [round(float(v), 1) for v in b] for c, p, b in zip(r.boxes.cls, r.boxes.conf, r.boxes.xyxy)]
    step = TILE - OV; out = []
    xs = list(range(0, max(1, W - OV), step)); ys = list(range(0, max(1, H - OV), step))
    for x0 in xs:
        for y0 in ys:
            x1, y1 = min(W, x0 + TILE), min(H, y0 + TILE)
            r = model.predict(img.crop((x0, y0, x1, y1)), imgsz=TILE, conf=0.05, verbose=False)[0]
            # core area owned by this tile: half of the overlap on each inner side
            cx0 = x0 + (OV // 2 if x0 > 0 else 0); cy0 = y0 + (OV // 2 if y0 > 0 else 0)
            cx1 = x1 - (OV // 2 if x1 < W else 0); cy1 = y1 - (OV // 2 if y1 < H else 0)
            for c, p, b in zip(r.boxes.cls, r.boxes.conf, r.boxes.xyxy):
                bx0, by0, bx1, by1 = (float(b[0]) + x0, float(b[1]) + y0, float(b[2]) + x0, float(b[3]) + y0)
                mx, my = (bx0 + bx1) / 2, (by0 + by1) / 2
                if cx0 <= mx < cx1 and cy0 <= my < cy1:
                    out.append([CLASSES[int(c)], round(float(p), 3), round(bx0, 1), round(by0, 1), round(bx1, 1), round(by1, 1)])
    return out

raw = {}; todo = split["val"] + split["junction_test"]
for i, s in enumerate(todo):
    img = Image.open(os.path.join(s, "F1_scaled.png")).convert("RGB")
    raw[name_of(s)] = {"size": list(img.size), "dets": run(img)}
    if i % 100 == 0: print(f"{i}/{len(todo)}", flush=True)
dst = os.path.join(here, "det_cache_tiled"); os.makedirs(dst, exist_ok=True)
json.dump({"val": sorted(name_of(s) for s in split["val"]), "test": sorted(name_of(s) for s in split["junction_test"]), "raw": raw},
          open(os.path.join(dst, "_raw_detections.json"), "w"))
shutil.make_archive(os.path.join(here, "det_cache_tiled"), "zip", dst)
print("done ->", os.path.join(here, "det_cache_tiled.zip"))
