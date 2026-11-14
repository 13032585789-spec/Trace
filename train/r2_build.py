"""Round-2 training data for the fixture detector (doors / windows / sanitary).

Two label variants from the same CubiCasa SVG annotations, written side by side:
  std  : door, window, toilet, sink, shower, bathtub, door_none
  runs : door, window_run, window_joint, toilet, sink, shower, bathtub, door_none
         Windows that touch end-to-end on the same wall are merged into one 'window_run'; every place where two
         annotated windows meet becomes a small 'window_joint' box. Count of windows = runs + joints, exactly
         (checked below for every image). The detector then decides locally "is this a split between two windows",
         instead of deciding how to cut a long box.
'door_none' (a doorway without a leaf, annotated 'Door None') is a separate class so the model learns it is not a door.

Images: IMGS (default F1_original,F1_scaled). Junction PNGs are F1_original, pixel-identical; labels are normalised,
so the same label file fits both resolutions. Junction held-out test plans (md5 % 5 == 0) are never trained on.

usage (in train/):  python3 r2_build.py --root data          -> data/yolo_r2std, data/yolo_r2runs, data/r2*.yaml, data/r2_gt.json
"""
import os, sys, json, glob, hashlib, argparse, collections
os.environ.setdefault("TASK", "fixtures")
import cubicasa_to_yolo as C

STD = ["door", "window", "toilet", "sink", "shower", "bathtub", "door_none"]
RUNS = ["door", "window_run", "window_joint", "toilet", "sink", "shower", "bathtub", "door_none"]

_base_classify = C.classify
def classify(cls):
    t = cls.split()
    if t and t[0] == "Door" and len(t) > 1 and t[1] == "None": return "door_none"
    return _base_classify(cls)
C.classify = classify

def runs_and_joints(wins):
    """wins: [[x0,y0,x1,y1]] in pixels. Returns (runs, joints). Two windows are adjacent when they lie on the same
    wall band (short sides overlap >= 70%) and their ends touch (gap <= max(2 px, 0.35 * thickness))."""
    n = len(wins); parent = list(range(n)); joints = []
    def find(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for i in range(n):
        for j in range(i + 1, n):
            a, b = wins[i], wins[j]
            for ax in (0, 1):                                  # 0: horizontal wall (long axis x), 1: vertical
                lo, hi = (1, 3) if ax == 0 else (0, 2)          # short-axis coordinates
                L0, L1 = (0, 2) if ax == 0 else (1, 3)          # long-axis coordinates
                ta, tb = a[hi] - a[lo], b[hi] - b[lo]
                if ta <= 0 or tb <= 0: continue
                if (a[L1] - a[L0]) < ta or (b[L1] - b[L0]) < tb: continue      # both must be elongated along ax
                ov = min(a[hi], b[hi]) - max(a[lo], b[lo])
                if ov < 0.7 * min(ta, tb): continue
                t = max(ta, tb); gap = max(a[L0], b[L0]) - min(a[L1], b[L1])
                if gap > max(2.0, 0.35 * t): continue
                if gap < -0.5 * t: continue                    # overlapping a lot = duplicate, not end-to-end
                if find(i) != find(j):                         # one joint per merge -> joints = windows - runs, exactly
                    m = (min(a[L1], b[L1]) + max(a[L0], b[L0])) / 2; c = (max(a[lo], b[lo]) + min(a[hi], b[hi])) / 2
                    h = max(2.0, 0.75 * t)
                    joints.append([m - h, c - h, m + h, c + h] if ax == 0 else [c - h, m - h, c + h, m + h])
                    parent[find(i)] = find(j)
                break
    groups = collections.defaultdict(list)
    for i in range(n): groups[find(i)].append(wins[i])
    runs = [[min(w[0] for w in g), min(w[1] for w in g), max(w[2] for w in g), max(w[3] for w in g)] for g in groups.values()]
    return runs, joints

def fit(b, W, H, mn=2.0):
    """Clip to the image; widen boxes thinner than mn px around their centre. None if fully outside."""
    x0, y0, x1, y1 = max(0, b[0]), max(0, b[1]), min(W, b[2]), min(H, b[3])
    if x1 < x0 or y1 < y0: return None
    if x1 - x0 < mn: c = (x0 + x1) / 2; x0, x1 = max(0, c - mn / 2), min(W, c + mn / 2)
    if y1 - y0 < mn: c = (y0 + y1) / 2; y0, y1 = max(0, c - mn / 2), min(H, c + mn / 2)
    return [x0, y0, x1, y1]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default="data"); a = ap.parse_args()
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    IMGS = [x for x in os.environ.get("IMGS", "F1_original,F1_scaled").split(",") if x]
    samples = sorted(os.path.dirname(p) for p in glob.glob(os.path.join(a.root, "cubicasa5k", "*", "*", "model.svg")))
    outs = {v: os.path.join(a.root, f"yolo_r2{v}") for v in ("std", "runs")}
    for o in outs.values():
        for sub in ("images/train", "images/val", "labels/train", "labels/val"): os.makedirs(os.path.join(o, sub), exist_ok=True)
    gt, split, bad = {}, {"train": [], "val": [], "junction_test": []}, 0
    stats = collections.Counter()
    for s in samples:
        name = C.junction_name(s); scaled = os.path.join(s, "F1_scaled.png")
        if not os.path.exists(scaled): continue
        W, H = Image.open(scaled).size                       # SVG coordinates are F1_scaled pixels
        objs, _, _ = C.objects(os.path.join(s, "model.svg"))
        objs = [(c, fit(b, W, H)) for c, b in objs]
        objs = [(c, b) for c, b in objs if b is not None]     # keep even 1-px-thin windows: they are the hard ones
        wins = [b for c, b in objs if c == "window"]
        runs, joints = runs_and_joints(wins)
        if len(runs) + len(joints) != len(wins): bad += 1
        stats["windows"] += len(wins); stats["runs"] += len(runs); stats["joints"] += len(joints)
        norm = lambda b: [round(b[0] * 1000 / W, 1), round(b[1] * 1000 / H, 1), round(b[2] * 1000 / W, 1), round(b[3] * 1000 / H, 1)]
        gt[name] = {"boxes": [[c] + norm(b) for c, b in objs], "runs": [norm(b) for b in runs], "joints": [norm(b) for b in joints]}
        if C.is_junction_test(name): split["junction_test"].append(s); continue
        part = "val" if int(hashlib.md5(name.encode()).hexdigest(), 16) % 10 == 0 else "train"; split[part].append(s)
        def yl(cls_names, items):
            out = []
            for c, (x0, y0, x1, y1) in items:
                x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
                if x1 - x0 < 1 or y1 - y0 < 1: continue
                out.append(f"{cls_names.index(c)} {(x0+x1)/2/W:.6f} {(y0+y1)/2/H:.6f} {(x1-x0)/W:.6f} {(y1-y0)/H:.6f}\n")
            return out
        lab = {"std": yl(STD, objs),
               "runs": yl(RUNS, [(c, b) for c, b in objs if c != "window"] + [("window_run", b) for b in runs] +
                             [("window_joint", b) for b in joints])}
        for v, o in outs.items():
            for img in IMGS:
                src = os.path.join(s, img + ".png")
                if not os.path.exists(src): continue
                stem = name[:-4] + "__" + img; dst = os.path.join(o, "images", part, stem + ".png")
                if not os.path.exists(dst): os.symlink(os.path.abspath(src), dst)
                with open(os.path.join(o, "labels", part, stem + ".txt"), "w") as f: f.writelines(lab[v])
    for v, names in (("std", STD), ("runs", RUNS)):
        open(os.path.join(a.root, f"r2{v}.yaml"), "w").write(
            f"path: {os.path.abspath(outs[v])}\ntrain: images/train\nval: images/val\nnames: {json.dumps(dict(enumerate(names)))}\n")
    json.dump(gt, open(os.path.join(a.root, "r2_gt.json"), "w")); json.dump(split, open(os.path.join(a.root, "r2_split.json"), "w"))
    print({k: len(v) for k, v in split.items()}, dict(stats), f"runs+joints != windows in {bad} images (must be 0)")
    if bad: sys.exit("window run/joint decomposition is not exact")

if __name__ == "__main__":
    main()
