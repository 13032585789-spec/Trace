"""Compare door/window counting models on the images users actually send (F1_original = Junction PNGs).

Models: r1 (current, 1280), r2std, r2runs (this round, 1536), rtdetr (public RT-DETR-L weights, 1024),
plus box-level ensembles of the standard-label models. Thresholds are tuned on the val split (never on test) for
exact-count accuracy; test = Junction held-out plans. GT counts come from the SVG annotations (= Junction answers).

RT-DETR was trained on the official CubiCasa train split, which contains most Junction test plans, so its numbers
are also reported on the fair subset (Junction test plans in the official val/test lists) - only trust those.

usage (in train/, after r2 training):  python3 r2_eval.py      -> r2_report.txt, r2_dets.zip
"""
import os, sys, json, glob, collections, zipfile, statistics
from ultralytics import YOLO, RTDETR

here = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(here, "data")
GT = json.load(open(os.path.join(D, "r2_gt.json"))); SPLIT = json.load(open(os.path.join(D, "r2_split.json")))
name_of = lambda s: f"{os.path.normpath(s).split(os.sep)[-2]}-{os.path.normpath(s).split(os.sep)[-1]}.png"
def official(fn):
    p = os.path.join(D, "cubicasa5k", fn)
    return {os.path.normpath(l.strip().strip("/")).replace("/", "-").replace("\\", "-") + ".png" for l in open(p) if l.strip()} if os.path.exists(p) else set()
FAIR = official("val.txt") | official("test.txt")

def newest(run):
    c = [p for p in glob.glob(os.path.join(os.path.expanduser("~"), "**", run, "weights", "best.pt"), recursive=True) if ".venv" not in p]
    return max(c, key=os.path.getmtime) if c else None
MODELS = [("r1", os.path.join(here, "..", "models", "cubicasa_yolo11m_1280.pt"), 1280, YOLO),
          ("r2std", newest("r2std"), 1536, YOLO), ("r2runs", newest("r2runs"), 1536, YOLO),
          ("rtdetr", os.path.join(here, "..", "models", "rtdetr_l_cubi.pt"), 1024, RTDETR)]
MODELS = [m for m in MODELS if m[1] and os.path.exists(m[1])]

def predict(spec, samples):
    tag, w, imgsz, cls = spec; m = cls(w); names = m.names; out = {}
    for i in range(0, len(samples), 16):
        b = samples[i:i + 16]
        for s, r in zip(b, m.predict([os.path.join(s, "F1_original.png") for s in b], imgsz=imgsz, conf=0.05, verbose=False)):
            H, W = r.orig_shape
            out[name_of(s)] = [[names[int(c)].lower(), round(float(p), 3), round(float(x[0]) * 1000 / W, 1), round(float(x[1]) * 1000 / H, 1),
                                round(float(x[2]) * 1000 / W, 1), round(float(x[3]) * 1000 / H, 1)] for c, p, x in zip(r.boxes.cls, r.boxes.conf, r.boxes.xyxy)]
    return out

def iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]); i = max(0, x1 - x0) * max(0, y1 - y0)
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i; return i / u if u > 0 else 0

def gt_count(n, cat): return sum(1 for x in GT[n]["boxes"] if x[0] == cat)
TH = [x / 100 for x in range(10, 96, 5)]

def count(dets, cat, t, runs=False):
    if cat == "window" and runs:
        t1, t2 = t
        return sum(1 for d in dets if d[0] == "window_run" and d[1] >= t1) + sum(1 for d in dets if d[0] == "window_joint" and d[1] >= t2)
    return sum(1 for d in dets if d[0] == cat and d[1] >= t)

def fuse(parts, cat, iou_thr=0.5):
    """Box-level ensemble: cluster boxes of one class across models; score = mean over models of their best score."""
    boxes = sorted([(d[1], k, d[2:]) for k, dets in enumerate(parts) for d in dets if d[0] == cat], reverse=True)
    clusters = []
    for p, k, b in boxes:
        for c in clusters:
            if iou(c["box"], b) >= iou_thr: c["s"][k] = max(c["s"].get(k, 0), p); break
        else: clusters.append({"box": b, "s": {k: p}})
    return [[cat, round(sum(c["s"].values()) / len(parts), 3)] + c["box"] for c in clusters]

def evaluate(tag, val, test, runs=False):
    res = {}
    for cat in ("door", "window"):
        grid = [(a, b) for a in TH for b in TH] if (runs and cat == "window") else TH
        acc = lambda P, t: sum(count(P[n], cat, t, runs) == gt_count(n, cat) for n in P) / max(1, len(P))
        best = max(grid, key=lambda t: acc(val, t))
        fair = {n: v for n, v in test.items() if n in FAIR}
        by = collections.defaultdict(list)
        for n in test: by[n.rsplit("-", 1)[0]].append(count(test[n], cat, best, runs) == gt_count(n, cat))
        res[cat] = {"thr": best, "val": round(100 * acc(val, best), 1), "test": round(100 * acc(test, best), 1),
                    "test_fair_subset": round(100 * acc(fair, best), 1), "n_fair": len(fair),
                    "by_style": {k: round(100 * sum(v) / len(v), 1) for k, v in by.items()}}
    return res

def main():
    val_s, test_s = SPLIT["val"], SPLIT["junction_test"]
    if os.environ.get("SMOKE"):           # quick end-to-end check before the long training
        val_s, test_s = val_s[:24], test_s[:24]
    print("val", len(val_s), "test", len(test_s), "fair subset", sum(name_of(s) in FAIR for s in test_s), "models", [m[0] for m in MODELS])
    P = {}
    for spec in MODELS:
        print("predicting", spec[0]); P[spec[0]] = (predict(spec, val_s), predict(spec, test_s))
    report = {}
    for tag, (v, t) in P.items(): report[tag] = evaluate(tag, v, t, runs=(tag == "r2runs"))
    std = [k for k in P if k != "r2runs"]
    for i in range(len(std)):
        for j in range(i + 1, len(std)):
            a, b = std[i], std[j]; tag = f"{a}+{b}"
            fv = {n: fuse([P[a][0][n], P[b][0][n]], "door") + fuse([P[a][0][n], P[b][0][n]], "window") for n in P[a][0]}
            ft = {n: fuse([P[a][1][n], P[b][1][n]], "door") + fuse([P[a][1][n], P[b][1][n]], "window") for n in P[a][1]}
            report[tag] = evaluate(tag, fv, ft)
    lines = [f"{'model':16s} {'door test':>9s} {'door fair':>9s} {'win test':>9s} {'win fair':>9s}   thresholds"]
    for k, r in report.items():
        lines.append(f"{k:16s} {r['door']['test']:9.1f} {r['door']['test_fair_subset']:9.1f} {r['window']['test']:9.1f} "
                     f"{r['window']['test_fair_subset']:9.1f}   door {r['door']['thr']} window {r['window']['thr']}")
    txt = "\n".join(lines) + "\n\n" + json.dumps(report, indent=1)
    sfx = "_smoke" if os.environ.get("SMOKE") else ""
    open(os.path.join(here, f"r2_report{sfx}.txt"), "w").write(txt); print(txt[:3000])
    if sfx: return
    with zipfile.ZipFile(os.path.join(here, "r2_dets.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("dets.json", json.dumps({k: {"val": v, "test": t} for k, (v, t) in P.items()}))
        z.writestr("report.json", json.dumps(report)); z.writestr("fair.json", json.dumps(sorted(FAIR)))
    print("wrote r2_report.txt and r2_dets.zip")

if __name__ == "__main__":
    main()
