"""Cut each image that already has a whole-image result into 2x2 overlapping tiles for the door/window pass."""
import os, sys, json, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.answer import DATA
here = os.path.dirname(os.path.abspath(__file__)); out = os.path.join(here, "vlm_tiles"); os.makedirs(out, exist_ok=True)
n = 0
for f in sorted(os.listdir(os.path.join(here, "vlm_cache"))):
    name = f[:-5]; meta_p = os.path.join(out, name + ".tiles.json")
    if os.path.exists(meta_p): continue
    im = cv2.imread(os.path.join(DATA, "data", "cubicasa5k", name))
    if im is None: continue
    H, W = im.shape[:2]; ov = 0.12; tiles = []
    for r in range(2):
        for c in range(2):
            x0 = int(max(0, (c * 0.5 - ov / 2) * W)); x1 = int(min(W, ((c + 1) * 0.5 + ov / 2) * W))
            y0 = int(max(0, (r * 0.5 - ov / 2) * H)); y1 = int(min(H, ((r + 1) * 0.5 + ov / 2) * H))
            tf = f"{name}__r{r}c{c}.jpg"
            cv2.imwrite(os.path.join(out, tf), im[y0:y1, x0:x1], [cv2.IMWRITE_JPEG_QUALITY, 92])
            tiles.append({"file": tf, "xyxy": [x0, y0, x1, y1]})
    json.dump({"size": [W, H], "tiles": tiles}, open(meta_p, "w")); n += 1
print("tiled", n, "images ->", out)
