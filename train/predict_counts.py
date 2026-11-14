"""After training (on the Verda instance):  python3 predict_counts.py
1. Picks, per class, the confidence threshold that maximises EXACT count accuracy on the val split
   (counts compared with the SVG annotation counts).
2. Runs the detector on every Junction held-out test image and writes det_cache/<name>.json
   in the same format engine/cubicasa.py reads ({"model", "boxes": {category: [[x0,y0,x1,y1] in 0-1000]}}).
3. Packs det_cache.zip to download to your computer."""
import os, sys, json, glob, collections, shutil
from ultralytics import YOLO

TASK = os.environ.get("TASK", "fixtures")
CLASSES = (["bedroom", "kitchen", "balcony", "sauna", "label_wc", "label_ss", "floor"] if TASK == "rooms"
           else ["door", "window", "toilet", "sink", "shower", "bathtub"])
SFX = "_rooms" if TASK == "rooms" else ""
here = os.path.dirname(os.path.abspath(__file__))
split = json.load(open(os.path.join(here, "data", "split.json")))
ann = json.load(open(os.path.join(here, "data", f"annotation_counts{SFX}.json")))
def find_weights():
    """Newer Ultralytics versions may nest the run under runs/detect/...; take the newest best.pt (or last.pt)."""
    run = "cubi_rooms*" if TASK == "rooms" else "cubi"
    for pat in ("best.pt", "last.pt"):
        c = [p for p in glob.glob(os.path.join(os.path.expanduser("~"), "**", run, "weights", pat), recursive=True)
             if ".venv" not in p]
        if c: return max(c, key=os.path.getmtime)
    sys.exit("no trained weights found (best.pt / last.pt) - training probably did not finish; see train.log")
weights = sys.argv[1] if len(sys.argv) > 1 else find_weights()
print("using weights:", weights)
model = YOLO(weights); IMGSZ = int(os.environ.get("IMGSZ", 1280))
name_of = lambda s: f"{os.path.normpath(s).split(os.sep)[-2]}-{os.path.normpath(s).split(os.sep)[-1]}.png"

def detect(samples):
    out = {}
    for i in range(0, len(samples), 16):
        batch = samples[i:i + 16]
        for s, r in zip(batch, model.predict([os.path.join(s, "F1_scaled.png") for s in batch], imgsz=IMGSZ, conf=0.05, verbose=False)):
            H, W = r.orig_shape
            out[name_of(s)] = [(CLASSES[int(c)], float(p), [float(v) for v in b])
                               for c, p, b in zip(r.boxes.cls, r.boxes.conf, r.boxes.xyxy)], (W, H)
    return out

print("val images:", len(split["val"]))
val = detect(split["val"]); best = {}
for c in CLASSES:
    scores = {}
    for t in [x / 100 for x in range(10, 91, 5)]:
        ok = sum(sum(1 for k, p, _ in dets if k == c and p >= t) == ann[n].get(c, 0) for n, (dets, _) in val.items())
        scores[t] = ok / len(val)
    best[c] = max(scores, key=scores.get)
    print(f"{c:8s} best conf {best[c]:.2f}  exact-count accuracy on val {100 * scores[best[c]]:.1f}%")
json.dump(best, open(os.path.join(here, f"thresholds{SFX}.json"), "w"))

print("junction test images:", len(split["junction_test"]))
test = detect(split["junction_test"])
dst = os.path.join(here, f"det_cache{SFX}"); os.makedirs(dst, exist_ok=True)
for n, (dets, (W, H)) in test.items():
    boxes = collections.defaultdict(list)
    for k, p, (x0, y0, x1, y1) in dets:
        if p < best[k]: continue
        cat = "shower_tub" if (TASK != "rooms" and k in ("shower", "bathtub")) else k
        boxes[cat].append([round(x0 * 1000 / W, 1), round(y0 * 1000 / H, 1), round(x1 * 1000 / W, 1), round(y1 * 1000 / H, 1)])
    json.dump({"model": "yolo-cubicasa", "boxes": boxes}, open(os.path.join(dst, n + ".json"), "w"))
shutil.copy(os.path.join(here, "data", f"annotation_counts{SFX}.json"), dst)
# raw detections (every box >= 0.05 with its score) for val + test, so thresholds can be re-tuned
# offline against the Junction question answers instead of the SVG annotation counts
raw = {n: {"size": wh, "dets": [[k, round(p, 3)] + [round(v, 1) for v in b] for k, p, b in d]}
       for n, (d, wh) in {**val, **test}.items()}
json.dump({"val": sorted(val), "test": sorted(test), "raw": raw}, open(os.path.join(dst, "_raw_detections.json"), "w"))
shutil.make_archive(os.path.join(here, f"det_cache{SFX}"), "zip", dst)
print("wrote", len(test), "results ->", os.path.join(here, f"det_cache{SFX}.zip"))
