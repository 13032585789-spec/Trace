"""2.5D scene from a vector PDF sheet (handoff 42, part B): rooms / walls / openings, in metres from the printed scale.

Frame (same as engine.scene_ifc): X right, Y up, Z = down the page (plan-up = -Z). Origin = the page's top-left corner,
rotation 0 (the sheet as drawn). Plan points are [X, Z] metres; with no printed scale the scene is "illustrative" and
coordinates stay in PDF points ("unit": "pt").
Every element keeps its evidence: source.page (1-based), bbox_pt (PDF points) and bbox_norm1000 (0-1000 of the page,
the same for any render size of the page).
What is not read from the sheet is left out and said in warnings (fixtures such as WCs need symbol recognition).

python -m engine.scene_pdf sheet.pdf [--page 1] > scene.json"""
import os, math, json, argparse
from . import sheet as SH

BLACK = SH.BLACK

def _norm(b, size): return [round(b[0] * 1000 / size[0], 1), round(b[1] * 1000 / size[1], 1),
                            round(b[2] * 1000 / size[0], 1), round(b[3] * 1000 / size[1], 1)]

def _wall_fills(pdf_path, page):
    """Solid black fills = cut walls (poche). -> [(x0, top, x1, bottom, pts or None)] in PDF points."""
    import pdfplumber
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        pg = pdf.pages[page]
        for o in list(pg.rects) + list(pg.curves):
            if o.get("fill") and str(o.get("non_stroking_color")) in BLACK:
                out.append((o["x0"], o["top"], o["x1"], o["bottom"], o.get("pts")))
    return out

def scene(pdf_path, page=1, rel_path=None):
    rel = rel_path or pdf_path; p0 = int(page) - 1
    f = SH.load(pdf_path, p0)
    size = f["size"]; mpp = f["scale"]["m_per_pt"]; warn = []
    quality = "measured" if mpp else "illustrative"
    k = mpp or 1.0
    if not mpp: warn.append("no printed scale found: coordinates are PDF points, not metres (calibrate to measure)")
    M = lambda x, y: [round(x * k, 4), round(y * k, 4)]
    src = lambda b, **kw: {"file": rel, "page": p0 + 1, "bbox_pt": [round(v, 1) for v in b], "bbox_norm1000": _norm(b, size), **kw}
    # rooms (polygons traced around each label; recomputed when the cached facts predate polygons)
    rooms = f.get("rooms") or []
    if rooms and "polygon" not in rooms[0]:
        try: rooms = SH.rooms(pdf_path, p0, f)
        except Exception as e: warn.append(f"room outlines unavailable: {e!r}"[:160])
    out_rooms = []
    for i, r in enumerate(rooms):
        poly = r.get("polygon")
        if not poly: continue
        lb = r.get("label_box") or r["box"]
        out_rooms.append({"id": f"p{p0+1}-room-{i}", "name": r["name"], "number": None, "storey_id": f"p{p0+1}",
                          "polygon": [M(x, y) for x, y in poly], "floor_y_m": 0.0, "height_m": None,
                          "area_m2": r.get("area_m2") if mpp else None, "baseboard_m": r.get("baseboard_m") if mpp else None,
                          "label_point": [M((lb[0] + lb[2]) / 2, 0)[0], 0.0, M(0, (lb[1] + lb[3]) / 2)[1]],
                          "confidence": 0.8 if " + " not in r["name"] else 0.5,
                          "source": src(r["box"], label=r["name"]),
                          **({"warnings": ["two labels in one traced region: the wall between them was not found"]} if " + " in r["name"] else {})})
    # walls from solid fills
    walls = []
    try: fills = _wall_fills(pdf_path, p0)
    except Exception as e: fills = []; warn.append(f"walls unavailable (pdfplumber): {e!r}"[:160])
    for i, (x0, t, x1, b, pts) in enumerate(fills):
        w, h = x1 - x0, b - t
        if max(w, h) * k < 0.3 or min(w, h) * k > 0.8: continue          # specks and big solid areas are not walls
        rect = not pts or len(pts) <= 5
        if w >= h: a, c, th = (x0, (t + b) / 2), (x1, (t + b) / 2), h
        else: a, c, th = ((x0 + x1) / 2, t), ((x0 + x1) / 2, b), w
        walls.append({"id": f"p{p0+1}-wall-{i}", "storey_id": f"p{p0+1}", "points": [M(*a), M(*c)],
                      "thickness_m": round(th * k, 3), "base_y_m": 0.0, "height_m": None,
                      "footprint": [M(x0, t), M(x1, t), M(x1, b), M(x0, b)],
                      "confidence": 0.8 if rect else 0.5, "source": src([x0, t, x1, b]),
                      **({} if rect else {"warnings": ["non-rectangular fill: centre line is its bounding box axis"]})})
    if not walls: warn.append("no solid wall fills on this sheet: walls not exported (outline-only walls are not traced yet)")
    else: warn.append("walls = solid black fills (cut walls); outline-drawn walls are not included; wall height is not on a plan")
    solid = lambda x, y, e=1.2: any(F[0] - e <= x <= F[2] + e and F[1] - e <= y <= F[3] + e for F in fills)
    # openings
    openings = []
    for i, L in enumerate(f.get("door_leaves") or []):
        hx, hy = L["hinge"]; r_pt = (L["radius_m"] / mpp) if mpp else None
        best, how = None, "ambiguous"
        for e in L["ends"]:
            d = math.dist((hx, hy), e) or 1; ux, uy = (e[0] - hx) / d, (e[1] - hy) / d
            beyond = (e[0] + ux * 0.12 / k, e[1] + uy * 0.12 / k)     # the closed leaf ends at the far jamb (wall)
            if solid(*beyond) and best is None: best, how = (e, ux, uy), "closed leaf ends on a wall"
        if best is None:
            e = L["ends"][0]; d = math.dist((hx, hy), e) or 1; best = (e, (e[0] - hx) / d, (e[1] - hy) / d)
        e, ux, uy = best
        cx, cy = (hx + e[0]) / 2, (hy + e[1]) / 2
        openings.append({"id": f"p{p0+1}-door-{i}", "kind": "door", "wall_id": None, "storey_id": f"p{p0+1}",
                         "position": [M(cx, 0)[0], 0.0, M(0, cy)[1]],
                         "rotation_deg": round(math.degrees(math.atan2(-uy, ux)) % 360, 2),
                         "width_m": L["radius_m"] if mpp else None, "height_m": None,
                         "hinge": [M(hx, 0)[0], 0.0, M(0, hy)[1]], "swing_ends": [M(*x) for x in L["ends"]],
                         "confidence": 0.85 if how != "ambiguous" else 0.6, "placement": how,
                         "source": src(L["box"])})
    for i, w in enumerate(f.get("windows") or []):
        b = w["box"]; horiz = (b[2] - b[0]) >= (b[3] - b[1])
        openings.append({"id": f"p{p0+1}-window-{i}", "kind": "window", "wall_id": None, "storey_id": f"p{p0+1}",
                         "position": [M((b[0] + b[2]) / 2, 0)[0], 0.0, M(0, (b[1] + b[3]) / 2)[1]],
                         "rotation_deg": 0.0 if horiz else 90.0, "width_m": w["width_m"] if mpp else None,
                         "height_m": None, "panes": w.get("panes", 1), "confidence": 0.8, "source": src(b)})
    # attach openings to the nearest wall piece (wall_id) when one touches the opening
    for o in openings:
        x, z = o["position"][0], o["position"][2]
        near = [(min(math.dist((x, z), p) for p in wl["points"]), wl["id"]) for wl in walls]
        o["wall_id"] = min(near)[1] if near and min(near)[0] <= (o["width_m"] or 1) else None
    warn.append("fixtures (WC, sinks) are drawn as symbols: not exported from vector sheets yet; ask questions for counts")
    warn.append("door/window heights and storey height are not on a plan: null")
    return {"project_id": os.path.splitext(os.path.basename(pdf_path))[0], "source_kind": "pdf_vector",
            "unit": "m" if mpp else "pt", "scale": f["scale"],
            "coordinate_system": "sheet: origin page top-left, X right, Y up, Z down the page (plan-up = -Z), rotation 0",
            "plan_up_vector": [0, -1], "north_vector": None, "north_basis": "page (north arrow not read)",
            "rotation_convention": "rotation_deg about +Y, three.js: local +X -> (cos r, 0, -sin r)",
            "quality": quality, "warnings": warn, "sources": [{"file": rel, "page": p0 + 1}],
            "storeys": [{"id": f"p{p0+1}", "name": f"sheet page {p0+1}", "elevation_m": 0.0, "height_m": None,
                         "outline": [M(0, 0), M(size[0], 0), M(*size), M(0, size[1])], "outline_from": "page border",
                         "source": src([0, 0, *size])}],
            "rooms": out_rooms, "walls": walls, "openings": openings, "objects": [], "systems": []}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("pdf"); ap.add_argument("--page", type=int, default=1); a = ap.parse_args()
    print(json.dumps(scene(a.pdf, a.page), ensure_ascii=False, indent=1))
