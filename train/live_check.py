"""F2: run the engine's live detector (engine/detector.py + models/detector.json) on held-out plans and compare the
door/window counts with the answers. Checks the code path users hit, end to end, before Verda is shut down.
usage (in train/):  cp <r2std best.pt> ../models/cubicasa_r2std_1536.pt && python3 live_check.py [N]"""
import os, sys, json, time
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(here, ".."))
from engine import detector
D = os.path.join(here, "data"); GT = json.load(open(os.path.join(D, "r2_gt.json")))
test = json.load(open(os.path.join(D, "r2_split.json")))["junction_test"][: int(sys.argv[1]) if len(sys.argv) > 1 else 200]
name_of = lambda s: f"{os.path.normpath(s).split(os.sep)[-2]}-{os.path.normpath(s).split(os.sep)[-1]}.png"
ok = {"door": 0, "window": 0}; t0 = time.time(); used = None
for s in test:
    d = detector.detect(os.path.join(s, "F1_original.png")); used = d["models_used"]
    for c in ok: ok[c] += len(d["boxes"].get(c, [])) == sum(1 for x in GT[name_of(s)]["boxes"] if x[0] == c)
print("models used:", used)
print(f"{len(test)} plans, {1000 * (time.time() - t0) / len(test):.0f} ms/plan")
for c, v in ok.items(): print(f"{c}: {100 * v / len(test):.1f}%")
