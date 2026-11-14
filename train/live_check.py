"""F2: run the engine's live detector (engine/detector.py + models/detector.json) on held-out plans and compare the
door/window counts with the answers. Checks the code path users hit, end to end, before Verda is shut down.
usage (in train/):  cp <r2std best.pt> ../models/cubicasa_r2std_1536.pt && python3 live_check.py [N]"""
import os, sys, json, time
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(here, ".."))
from engine import detector
D = os.path.join(here, "data"); GT = json.load(open(os.path.join(D, "r2_gt.json")))
test = json.load(open(os.path.join(D, "r2_split.json")))["junction_test"][: int(sys.argv[1]) if len(sys.argv) > 1 else 10**6]
name_of = lambda s: f"{os.path.normpath(s).split(os.sep)[-2]}-{os.path.normpath(s).split(os.sep)[-1]}.png"
import collections
def official(fn):
    p = os.path.join(D, "cubicasa5k", fn)
    return {os.path.normpath(l.strip().strip("/")).replace("/", "-").replace("\\", "-") + ".png" for l in open(p) if l.strip()} if os.path.exists(p) else set()
FAIR = official("val.txt") | official("test.txt")
ok = collections.defaultdict(lambda: [0, 0]); t0 = time.time(); used = None
for s in test:
    n = name_of(s); d = detector.detect(os.path.join(s, "F1_original.png")); used = d["models_used"]
    for c in ("door", "window"):
        hit = len(d["boxes"].get(c, [])) == sum(1 for x in GT[n]["boxes"] if x[0] == c)
        for g in ("all", "fair" if n in FAIR else "seen-by-rtdetr?", n.rsplit("-", 1)[0]):
            ok[(c, g)][0] += hit; ok[(c, g)][1] += 1
print("models used:", used)
print(f"{len(test)} plans, {1000 * (time.time() - t0) / len(test):.0f} ms/plan")
for (c, g), (h, n) in sorted(ok.items()): print(f"{c:7s}{g:28s}{100 * h / n:5.1f}%  (n={n})")
