"""2.5D scene from a scan / photo / raster plan (handoff 42, part C).

Only what image analysis finds without a model: door swings, window symbols, (and toilets / sinks / showers when the
CubiCasa detector is installed). Metric only after the user calibrated this file in the review panel (/calibrate):
then quality "measured" and coordinates in metres; otherwise quality "illustrative" and coordinates in 0-1000 image
units ("unit": "norm1000"), never fake metres.

Frame: origin image top-left, X right, Y up, Z down the image (plan-up = -Z). Evidence: source.bbox_norm1000.
python -m engine.scene_scan plan.jpg [--page 1] > scene.json"""
import os, json, argparse
from . import scanqa, review

def _image(path, page):
    if path.lower().endswith(".pdf"):
        from . import docqa
        return docqa.render_page(path, page - 1)
    return open(path, "rb").read()

def scene(path, page=1, rel_path=None):
    rel = rel_path or path; warn = []
    img = _image(path, page)
    if img is None: return {"error": "cannot read the image"}
    import cv2, numpy as np
    im = cv2.imdecode(np.frombuffer(img, np.uint8), cv2.IMREAD_GRAYSCALE); H, W = im.shape
    cal, how = review._scale(path, page - 1)
    if cal and how == "user calibration":
        iw, ih = cal.get("image_size") or (W, H)
        k = cal["m_per_unit"]; fx, fz = iw / 1000 * k, ih / 1000 * k
        unit, quality = "m", "measured"
        warn.append(f"scale from the user's calibration ({cal.get('length_m')} m between two clicked points)")
    else:
        fx = fz = 1.0; unit, quality = "norm1000", "illustrative"
        warn.append("no calibration for this image: positions are 0-1000 image units, not metres; calibrate in the review panel to measure")
    P = lambda x, z: [round(float(x) * fx, 4), 0.0, round(float(z) * fz, 4)]
    src = lambda b: {"file": rel, "page": page, "bbox_norm1000": [round(float(v), 1) for v in b]}
    openings, objects = [], []
    for i, d in enumerate(scanqa.raster_doors(img)):
        b = [float(v) for v in d["box_norm1000"]]
        openings.append({"id": f"s{page}-door-{i}", "kind": "door", "wall_id": None, "position": P((b[0] + b[2]) / 2, (b[1] + b[3]) / 2),
                         "rotation_deg": None, "width_m": round(max((b[2] - b[0]) * fx, (b[3] - b[1]) * fz), 3) if unit == "m" else None,
                         "height_m": None, "confidence": 0.6, "source": src(b),
                         "warnings": ["swing box centre, not the opening centre; orientation not read"]})
    for i, w in enumerate(scanqa.raster_windows(img)):
        b = [float(v) for v in w["box_norm1000"]]; horiz = (b[2] - b[0]) * W >= (b[3] - b[1]) * H
        openings.append({"id": f"s{page}-window-{i}", "kind": "window", "wall_id": None, "position": P((b[0] + b[2]) / 2, (b[1] + b[3]) / 2),
                         "rotation_deg": 0.0 if horiz else 90.0, "panes": w.get("panes", 1),
                         "width_m": round(((b[2] - b[0]) * fx if horiz else (b[3] - b[1]) * fz), 3) if unit == "m" else None,
                         "height_m": None, "confidence": 0.65, "source": src(b)})
    if not path.lower().endswith(".pdf"):
        try:
            from . import detector
            d = detector.detect(path)
        except Exception: d = None
        if d:
            for cat, bxs in d["boxes"].items():
                if cat not in ("toilet", "sink", "shower_tub"): continue
                for i, b in enumerate(bxs):
                    b = [float(v) for v in b]
                    objects.append({"id": f"s{page}-{cat}-{i}", "category": cat, "position": P((b[0] + b[2]) / 2, (b[1] + b[3]) / 2),
                                    "rotation_deg": None, "footprint": {"width_m": round((b[2] - b[0]) * fx, 3), "depth_m": round((b[3] - b[1]) * fz, 3)} if unit == "m" else None,
                                    "confidence": round(d["scores"][cat][i], 3), "source": src(b)})
        else: warn.append("fixture detector not installed here (ultralytics): WC / sink not exported; ask the counting questions instead")
    warn.append("rooms and walls are not traced from scans yet: use the 2D image as the base layer")
    return {"project_id": os.path.splitext(os.path.basename(path))[0], "source_kind": "scan", "unit": unit,
            "coordinate_system": "image: origin top-left, X right, Y up, Z down the image (plan-up = -Z)",
            "plan_up_vector": [0, -1], "north_vector": None, "north_basis": "page (north arrow not read)",
            "quality": quality, "warnings": warn, "sources": [{"file": rel, "page": page}], "image_size_px": [W, H],
            "storeys": [{"id": f"s{page}", "name": f"page {page}", "elevation_m": 0.0, "height_m": None,
                         "outline": [P(0, 0)[::2], P(1000, 0)[::2], P(1000, 1000)[::2], P(0, 1000)[::2]], "outline_from": "image border"}],
            "rooms": [], "walls": [], "openings": openings, "objects": objects, "systems": []}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("image"); ap.add_argument("--page", type=int, default=1); a = ap.parse_args()
    print(json.dumps(scene(a.image, a.page), ensure_ascii=False, indent=1))
