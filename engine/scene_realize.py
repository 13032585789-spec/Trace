"""Turn a drawing scene (vector PDF or scan) into a buildable 2.5D model: a minimal, realistic building, not a copy
of every stroke.

Rules (the real-world constraints a building must satisfy):
  1. the outside of the building is a closed ring of solid wall;
  2. every edge between two rooms, or between a room and the outside, is a wall;
  3. all walls of a storey have the same height;
  4. every door and window sits in a wall (snapped onto its centreline, rotated with it);
  5. wall ends meet: close-by ends are joined, short gaps to a crossing wall are closed (T-joints);
  6. fixtures stand inside a room; missing footprints get a typical size (toilet, sink, bath ...).
Walls read from the drawing are kept as they are; everything added is marked assumed=True with its method, so
the viewer can draw it lighter and nobody mistakes it for drawing data. IFC scenes are real geometry and are only
measured, never changed.

realize(scene) -> the same scene, edited in place, plus scene["realism"] = coverage metrics:
  room_edge_coverage   share of room boundary length that lies on a wall (before -> after)
  envelope_coverage    share of the building outline that lies on a wall (before -> after)
  openings_hosted      share of doors / windows sitting in a wall
  fixtures_in_rooms    share of fixtures inside a room polygon
  from_drawing_share   share of wall length that comes straight from the drawing (not assumed)
Target for the MVP: every coverage >= 0.95."""
import math
import numpy as np

WALL_H = 2.8          # m, one height for every wall of a storey (MVP)
STOREY_H = 3.0
DOOR_H, WIN_H, WIN_SILL = 2.1, 1.2, 0.9
FIXTURE_SIZE = {"toilet": (0.40, 0.70), "sink": (0.60, 0.45), "vanity": (0.80, 0.50), "bathtub": (1.70, 0.75),
                "shower": (0.90, 0.90), "stove": (0.60, 0.60), "urinal": (0.40, 0.35)}


def _seg_dist(P, A, B):
    """distances (N, M) from points P (N,2) to segments A-B (M,2); also the projection parameter t (N, M)."""
    AB = B - A
    L2 = np.maximum((AB ** 2).sum(1), 1e-12)
    AP = P[:, None, :] - A[None, :, :]
    t = np.clip((AP * AB[None]).sum(2) / L2[None], 0, 1)
    proj = A[None] + t[..., None] * AB[None]
    return np.sqrt(((P[:, None, :] - proj) ** 2).sum(2)), t


def _dp(pts, eps):
    """Douglas-Peucker simplification of a closed or open polyline."""
    pts = np.asarray(pts, float)
    if len(pts) < 3: return pts
    a, b = pts[0], pts[-1]
    if math.hypot(*(b - a)) < 1e-12 and len(pts) > 3:     # closed ring: split at the farthest point
        i = int(np.argmax(np.hypot(*(pts - a).T)))
        return np.vstack([_dp(pts[:i + 1], eps)[:-1], _dp(pts[i:], eps)])
    ab = b - a; n = math.hypot(*ab)
    if n < 1e-12: d = np.hypot(*(pts - a).T)
    else: v = pts - a; d = np.abs(ab[0] * v[:, 1] - ab[1] * v[:, 0]) / n
    i = int(np.argmax(d))
    if d[i] > eps: return np.vstack([_dp(pts[:i + 1], eps)[:-1], _dp(pts[i:], eps)])
    return np.vstack([a, b])


def _ring(poly, eps):
    p = np.asarray(poly, float)
    if len(p) < 3: return p
    p = np.vstack([p, p[:1]])
    s = _dp(p, eps)
    return s[:-1] if len(s) > 3 else np.asarray(poly, float)


def _samples(ring, step):
    """points along the closed ring every ~step, with the index of the edge they lie on."""
    out, edge = [], []
    for k in range(len(ring)):
        a, b = ring[k], ring[(k + 1) % len(ring)]
        n = max(1, int(math.hypot(*(b - a)) / step))
        for j in range(n):
            out.append(a + (b - a) * (j + 0.5) / n); edge.append(k)
    return np.asarray(out), np.asarray(edge)


def _covered(points, A, B, tol):
    if len(A) == 0 or len(points) == 0: return np.zeros(len(points), bool)
    d, _ = _seg_dist(points, A, B)
    return d.min(1) <= tol


def _new_wall(sid, k, a, b, t, method, storey):
    a, b = [round(float(v), 4) for v in a], [round(float(v), 4) for v in b]
    dx, dz = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dz) or 1.0
    nx, nz = -dz / L * t / 2, dx / L * t / 2
    return {"id": f"{sid}-rw-{k}", "storey_id": storey, "points": [a, b], "thickness_m": round(t, 3), "base_y_m": 0.0,
            "height_m": WALL_H, "footprint": [[a[0] + nx, a[1] + nz], [b[0] + nx, b[1] + nz], [b[0] - nx, b[1] - nz], [a[0] - nx, a[1] - nz]],
            "length_m": round(L, 3), "method": method, "confidence": 0.5, "assumed": True}


def _runs(mask, edge):
    """consecutive uncovered samples on the same edge -> (edge, i0, i1) index runs."""
    runs, i = [], 0
    while i < len(mask):
        if mask[i]:
            j = i
            while j + 1 < len(mask) and mask[j + 1] and edge[j + 1] == edge[i]: j += 1
            runs.append((i, j)); i = j + 1
        else: i += 1
    return runs


def _add_missing(ring, A, B, tol, step, min_len, t, sid, start, method, storey, doors=None):
    pts, edge = _samples(ring, step)
    cov = _covered(pts, A, B, tol) | _doorway(pts, doors)
    added = []
    for i0, i1 in _runs(~cov, edge):
        if (i1 - i0 + 1) * step < min_len: continue
        a = pts[i0] - (pts[min(i0 + 1, i1)] - pts[i0]) / 2 if i1 > i0 else pts[i0]
        b = pts[i1] + (pts[i1] - pts[max(i1 - 1, i0)]) / 2 if i1 > i0 else pts[i1]
        added.append(_new_wall(sid, start + len(added), a, b, t, method, storey))
    return added, float(cov.mean()) if len(cov) else 1.0, pts


def _doorway(pts, doors):
    """samples that lie in a door's swing zone: a doorway, not a missing wall (the door leaf / arc closed the room outline)."""
    if doors is None or not len(doors) or not len(pts): return np.zeros(len(pts), bool)
    c, rad = doors
    d = np.hypot(pts[:, None, 0] - c[None, :, 0], pts[:, None, 1] - c[None, :, 1])
    return (d <= rad[None, :]).any(1)


def _envelope(rooms, walls, cell):
    """outer outline of rooms + walls (rasterised, closed), as a ring in scene units, or None."""
    import cv2
    polys = [np.asarray(r["polygon"], float) for r in rooms if len(r.get("polygon") or []) >= 3]
    polys += [np.asarray(w["footprint"], float) for w in walls if len(w.get("footprint") or []) >= 3]
    if not polys: return None
    allp = np.vstack(polys); lo = allp.min(0) - 4 * cell; hi = allp.max(0) + 4 * cell
    W, H = (np.ceil((hi - lo) / cell).astype(int) + 1)
    if W * H > 9_000_000: cell *= math.sqrt(W * H / 9_000_000); W, H = (np.ceil((hi - lo) / cell).astype(int) + 1)
    img = np.zeros((H, W), np.uint8)
    for p in polys: cv2.fillPoly(img, [np.round((p - lo) / cell).astype(np.int32)], 255)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, k, iterations=2)
    cs, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cs: return None
    c = max(cs, key=cv2.contourArea)[:, 0, :].astype(float) * cell + lo
    return c


def _box(w, h, d, x=0.0, y=None, z=0.0, mat="ceramic"):
    return {"shape": "box", "size": [round(w, 3), round(h, 3), round(d, 3)], "at": [round(x, 3), round(h / 2 if y is None else y, 3), round(z, 3)], "material": mat}


def _cyl(r, h, x=0.0, y=None, z=0.0, scale_z=1.0, mat="ceramic"):
    return {"shape": "cylinder", "radius": round(r, 3), "height": round(h, 3), "scale_z": scale_z,
            "at": [round(x, 3), round(h / 2 if y is None else y, 3), round(z, 3)], "material": mat}


def fixture_model(cat):
    """Simple 3D model of a fixture as primitives, in metres. Local frame: origin on the floor at the fixture centre,
    x = width, y = up, z = depth with the FRONT at +z (the back stands against the wall). Typical sizes, not measured."""
    if cat == "toilet":
        return [_box(0.38, 0.40, 0.18, z=-0.25, y=0.60), _cyl(0.17, 0.40, z=0.04, scale_z=1.35),
                _box(0.36, 0.03, 0.42, z=0.06, y=0.415, mat="plastic")]
    if cat == "urinal":
        return [_box(0.36, 0.62, 0.30, z=-0.08, y=0.85)]
    if cat == "sink":
        return [_box(0.56, 0.16, 0.44, y=0.78), _cyl(0.08, 0.70, z=-0.08)]
    if cat == "vanity":
        return [_box(0.80, 0.82, 0.50, mat="wood"), _box(0.80, 0.04, 0.52, y=0.84), _cyl(0.18, 0.02, y=0.865, scale_z=0.8, mat="metal")]
    if cat == "bathtub":
        return [_box(1.70, 0.55, 0.75), _box(1.52, 0.02, 0.57, y=0.56, mat="water")]
    if cat == "shower":
        return [_box(0.90, 0.05, 0.90), _box(0.90, 2.00, 0.01, z=0.445, y=1.05, mat="glass"),
                _box(0.01, 2.00, 0.90, x=0.445, y=1.05, mat="glass")]
    if cat == "stove":
        return [_box(0.60, 0.90, 0.60, mat="metal")] + [_cyl(0.08, 0.01, x=dx, z=dz, y=0.905, mat="metal")
                                                         for dx in (-0.14, 0.14) for dz in (-0.14, 0.14)]
    if cat in ("table", "desk"):
        top = _box(1.20, 0.04, 0.70, y=0.73, mat="wood")
        return [top] + [_box(0.05, 0.71, 0.05, x=dx, z=dz, mat="metal") for dx in (-0.55, 0.55) for dz in (-0.3, 0.3)]
    if cat == "chair":
        return [_box(0.45, 0.05, 0.45, y=0.45, mat="wood"), _box(0.45, 0.42, 0.04, z=-0.205, y=0.69, mat="wood")] + \
               [_box(0.04, 0.43, 0.04, x=dx, z=dz, mat="metal") for dx in (-0.2, 0.2) for dz in (-0.2, 0.2)]
    return None


WALL_BACKED = {"toilet", "urinal", "sink", "vanity", "bathtub", "shower", "stove"}


def _snap_ends(walls, tol):
    """join wall ends closer than tol (average them); extend a free end onto a wall it nearly touches (T-joint)."""
    if not walls: return 0
    ends = np.array([w["points"][i] for w in walls for i in (0, 1)], float)
    moved = 0
    used = np.zeros(len(ends), bool)
    for i in range(len(ends)):
        if used[i]: continue
        d = np.hypot(*(ends - ends[i]).T); grp = np.where((d <= tol) & ~used)[0]
        if len(grp) > 1:
            m = ends[grp].mean(0); ends[grp] = m; used[grp] = True; moved += len(grp)
    A = np.array([w["points"][0] for w in walls], float); B = np.array([w["points"][1] for w in walls], float)
    for i in range(len(ends)):
        wi = i // 2
        d, tt = _seg_dist(ends[i:i + 1], A, B); d[0, wi] = np.inf
        j = int(np.argmin(d[0]))
        if tol * 0.3 < d[0, j] <= 2.5 * tol:
            proj = A[j] + tt[0, j] * (B[j] - A[j]); ends[i] = proj; moved += 1
    for k, w in enumerate(walls):
        new = [[round(float(x), 4) for x in ends[2 * k]], [round(float(x), 4) for x in ends[2 * k + 1]]]
        if new != [list(map(float, p)) for p in w["points"]]:
            w["points"] = new; w["adjusted"] = "ends joined to neighbouring walls"
            a, b = np.array(new); L = math.hypot(*(b - a)) or 1.0; t = w.get("thickness_m") or 0.2
            nx, nz = -(b[1] - a[1]) / L * t / 2, (b[0] - a[0]) / L * t / 2
            w["footprint"] = [[a[0] + nx, a[1] + nz], [b[0] + nx, b[1] + nz], [b[0] - nx, b[1] - nz], [a[0] - nx, a[1] - nz]]
    return moved


def _inside(pt, poly):
    x, y = pt; inside = False; n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1: inside = not inside
    return inside


def realize(scene):
    kind = scene.get("source_kind")
    walls, rooms = scene.get("walls") or [], scene.get("rooms") or []
    openings, objects = scene.get("openings") or [], scene.get("objects") or []
    th = [w.get("thickness_m") for w in walls if w.get("thickness_m")]
    t = float(np.median(th)) if th else (0.2 if scene.get("unit") == "m" else 2.0)
    tol, step = 1.2 * t, max(t / 2, 1e-3)
    storey = (scene.get("storeys") or [{}])[0].get("id")
    sid = storey or "s"
    seg = lambda ws: (np.array([w["points"][0] for w in ws], float).reshape(-1, 2), np.array([w["points"][-1] for w in ws], float).reshape(-1, 2))

    if kind == "ifc":    # real geometry: measure only (plus a simple 3D model for fixtures that have none)
        for ob in objects:
            mdl = fixture_model(ob.get("category"))
            if mdl and not ob.get("model"):
                ob["model"] = {"primitives": mdl, "frame": "local: x width, y up, z depth (front = +z); rotate by rotation_deg about y (three.js)",
                               "note": "typical shape (MVP); position and rotation are from the IFC model"}
        A, B = seg(walls)
        cov = [float(_covered(_samples(_ring(r["polygon"], t / 4), step)[0], A, B, 2 * t).mean()) for r in rooms if len(r.get("polygon") or []) >= 3]
        scene["realism"] = {"changed": False, "note": "IFC geometry is real; measured only",
                            "room_edge_coverage": round(float(np.mean(cov)), 3) if cov else None}
        return scene

    drawn = [w for w in walls if not w.get("assumed")]
    unit = 1.0 if scene.get("unit") == "m" else 10.0
    dc, dr = [], []
    for o in openings:
        if o.get("kind") != "door": continue
        wdt = (o.get("width_m") or 0.9) * unit
        for q in [o.get("hinge"), o.get("position")] + list(o.get("swing_ends") or []):
            if q is None: continue
            dc.append([q[0], q[2]] if len(q) == 3 else list(q)); dr.append(1.05 * wdt)
    doors = (np.array(dc, float), np.array(dr, float)) if dc else None
    joined = _snap_ends(walls, tol)
    added = []
    # 2 + 1: every room edge is a wall, and the outside is a closed ring
    A, B = seg(walls)
    cov_rooms_before, cov_rooms_after = [], []
    main = _envelope(rooms, walls, max(t / 2, 1e-3))      # the building: rooms outside it (legend boxes, title block) are skipped
    def _in_main(r):
        if main is None: return True
        c = np.asarray(r["polygon"], float).mean(0); return _inside(c, main)
    rooms_b = [r for r in rooms if len(r.get("polygon") or []) >= 3 and _in_main(r)]
    for r in rooms_b:
        if len(r.get("polygon") or []) < 3: continue
        ring = _ring(r["polygon"], t)
        new, before, _ = _add_missing(ring, A, B, tol, step, 2 * t, t, sid, len(added), "realize:room-edge", storey, doors)
        cov_rooms_before.append(before); added += new
        if new: A, B = seg(walls + added)
    env = _envelope(rooms_b, walls + added, max(t / 2, 1e-3))
    env_before = env_after = None
    if env is not None:
        ring = _ring(env, t)
        t_ext = float(np.percentile(th, 75)) if th else t
        new, env_before, _ = _add_missing(ring, A, B, tol, step, 2 * t, t_ext, sid, len(added), "realize:envelope", storey, doors)
        added += new; A, B = seg(walls + added)
        sp = _samples(ring, step)[0]
        env_after = float((_covered(sp, A, B, tol) | _doorway(sp, doors)).mean())
    for r in rooms_b:
        if True:
            sp = _samples(_ring(r["polygon"], t), step)[0]
            cov_rooms_after.append(float((_covered(sp, A, B, tol) | _doorway(sp, doors)).mean()))
    walls.extend(added)

    # 3: one height for every wall
    for w in walls:
        if not w.get("height_m"): w["height_m"] = WALL_H; w.setdefault("height_from", "storey default (MVP)")
    for s in scene.get("storeys") or []:
        if not s.get("height_m"): s["height_m"] = STOREY_H; s["height_from"] = "default (MVP)"

    # 4: doors and windows sit in a wall
    hosted = 0
    if openings and walls:
        ids = [w["id"] for w in walls]
        for o in openings:
            p = np.array([[o["position"][0], o["position"][2]]], float)
            d, tt = _seg_dist(p, A, B); j = int(np.argmin(d[0]))
            reach = 3 * t + (o.get("width_m") or 0.9) / 2 * (1 if scene.get("unit") == "m" else 10)
            if d[0, j] <= reach:
                a, b = A[j], B[j]; q = a + tt[0, j] * (b - a)
                if d[0, j] > 1e-6: o["snapped_from"] = [round(float(p[0, 0]), 4), round(float(p[0, 1]), 4)]
                o["position"] = [round(float(q[0]), 4), o["position"][1], round(float(q[1]), 4)]
                o["wall_id"] = ids[j]
                o["rotation_deg"] = round((-math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))) % 360, 1)
                hosted += 1
            if not o.get("height_m"):
                o["height_m"] = DOOR_H if o.get("kind") == "door" else WIN_H; o["height_from"] = "typical (MVP)"
            if o.get("kind") == "window" and o.get("sill_y_m") is None: o["sill_y_m"] = WIN_SILL
            if o.get("kind") == "door" and o.get("sill_y_m") is None: o["sill_y_m"] = 0.0

    # 6: fixtures inside a room, with a footprint
    in_room = 0
    cents = [(r["id"], np.asarray(r["polygon"], float)) for r in rooms if len(r.get("polygon") or []) >= 3]
    for ob in objects:
        x, z = ob["position"][0], ob["position"][2]
        if not ob.get("room_id"):
            for rid, poly in cents:
                if _inside((x, z), poly):
                    ob["room_id"] = rid; ob["room_method"] = "point-in-polygon"; break
        if not ob.get("room_id") and cents:          # cubicles the drawing did not close: the nearest room within 2 m
            dist = [float(_seg_dist(np.array([[x, z]]), poly, np.roll(poly, -1, 0))[0].min()) for _, poly in cents]
            k = int(np.argmin(dist))
            if dist[k] <= 2.0 * unit: ob["room_id"] = cents[k][0]; ob["room_method"] = "nearest room (within 2 m)"
        if ob.get("room_id"): in_room += 1
        if ob.get("category") in WALL_BACKED and len(A):      # the back stands against the nearest wall
            d, tt = _seg_dist(np.array([[x, z]]), A, B); j = int(np.argmin(d[0]))
            q = A[j] + tt[0, j] * (B[j] - A[j]); f = np.array([x, z]) - q; n = float(np.hypot(*f))
            if n > 1e-6:
                fx, fz = f / n
                ob["front_vector"] = [round(float(fx), 3), round(float(fz), 3)]
                ob["rotation_deg"] = round(math.degrees(math.atan2(fx, fz)) % 360, 1)
                ob["orientation_from"] = "back against the nearest wall"
        mdl = fixture_model(ob.get("category"))
        if mdl:
            ob["model"] = {"primitives": mdl, "frame": "local: x width, y up, z depth (front = +z); rotate by rotation_deg about y (three.js)",
                           "note": "typical shape and size (MVP), not measured"}
        size = FIXTURE_SIZE.get(ob.get("category"))
        if size and not (ob.get("footprint") or {}).get("width_m"):
            ob["footprint"] = {"width_m": size[0], "depth_m": size[1], "note": "typical size (MVP), not measured"}
            ob["footprint_assumed"] = True

    L = lambda ws: sum(math.hypot(w["points"][-1][0] - w["points"][0][0], w["points"][-1][1] - w["points"][0][1]) for w in ws)
    total = L(walls) or 1.0
    m = lambda xs: round(float(np.mean(xs)), 3) if xs else None
    scene["realism"] = {
        "changed": True,
        "rules": ["closed outer wall ring", "every room edge is a wall", "one wall height per storey",
                  "doors and windows sit in a wall", "wall ends joined", "fixtures inside rooms"],
        "room_edge_coverage": {"before": m(cov_rooms_before), "after": m(cov_rooms_after)},
        "envelope_coverage": {"before": None if env_before is None else round(env_before, 3), "after": None if env_after is None else round(env_after, 3)},
        "openings_hosted": round(hosted / len(openings), 3) if openings else None,
        "fixtures_in_rooms": round(in_room / len(objects), 3) if objects else None,
        "from_drawing_share": round(L(drawn) / total, 3),
        "walls_added": len(added), "wall_ends_joined": joined, "rooms_outside_building_skipped": len([r for r in rooms if len(r.get("polygon") or []) >= 3]) - len(rooms_b),
        "wall_height_m": WALL_H, "target": 0.95,
    }
    scene.setdefault("warnings", []).append(
        f"2.5D realised as a buildable MVP: {len(added)} walls added (assumed=True: room edges and a closed outer ring), "
        f"one wall height {WALL_H} m, doors/windows snapped into walls, typical fixture sizes where none were drawn")
    return scene
