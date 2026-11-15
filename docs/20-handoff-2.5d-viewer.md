# Handoff: draw the buildable 2.5D in the viewer (for Diletta)

From Xinran, 15 Nov 07:15. Engine repo `13032585789-spec/Trace` (`main`).
Detail on the rules: `docs/19-realized-2.5d.md`. Real samples: `eval/integration/scene_*.json`.

## 1. What `/api/geometry/scene` returns now
The same format as handoff 42, plus a few new fields. Every scene from a vector PDF or a scan is turned into a building that could stand. IFC geometry is never changed; it only gets the new fields.

| Field | Where | What to do with it |
|---|---|---|
| `scene.realism` | top level | completeness check (your plan, item 1). Show "Geometry incomplete" only if `room_edge_coverage.after < 0.95`. |
| `wall.assumed` | walls | `true` = the engine added this wall (closed outer ring / room edge). Draw it in Betongrau `#A9AFB0`; drawn walls in the wall colour. |
| `wall.pieces[]` | walls with doors / windows | **Draw these instead of the whole wall.** Each piece is a box from `from` to `to` (plan x, z), height `y0`…`y1`, thickness `wall.thickness_m`. This gives real door and window holes, with a lintel above doors and a sill wall below windows. No boolean geometry needed. A wall without `pieces` is drawn whole. |
| `opening.leaf` | doors | The open door leaf: a box from `hinge` to `tip`, thickness 0.04 m, height `height_m`, 90° open. `from` says whether the swing comes from the drawing (`swing arc on the drawing`) or is assumed. |
| windows | openings | Glass pane in the hole: `sill_y_m` (0.9) to `sill_y_m + height_m` (1.2), colour `#7FA7C9` at about 50 % opacity. |
| `object.model.primitives[]` | fixtures + furniture | Build each primitive (see §2). |
| `object.model.rotation_deg` | fixtures | The rotation for the model (about y, three.js). **Use this, not `object.rotation_deg`**, which stays as read from the source. |
| `object.room_id` | fixtures | Room view (your plan, item 7): show only objects with this room id. |
| `object.orientation_from`, `footprint_assumed`, `model.note` | fixtures | Show in the detail panel: "typical shape and size, not measured". |

## 2. Fixture models – three.js
Local frame: origin on the floor at the fixture centre; x = width, y = up, z = depth, **front = +z**.

```ts
const MAT = { ceramic: 0xffffff, plastic: 0xf1efe9, metal: 0xc9cccd, wood: 0xe6d7b8, glass: 0xcfe0ea, water: 0xbfd6e4 }
function fixtureGroup(obj) {
  const g = new THREE.Group()
  for (const p of obj.model.primitives) {
    const m = new THREE.MeshStandardMaterial({ color: MAT[p.material] ?? 0xffffff,
      transparent: p.material === 'glass', opacity: p.material === 'glass' ? 0.35 : 1 })
    let mesh
    if (p.shape === 'box') mesh = new THREE.Mesh(new THREE.BoxGeometry(...p.size), m)
    else { mesh = new THREE.Mesh(new THREE.CylinderGeometry(p.radius, p.radius, p.height, 24), m); mesh.scale.z = p.scale_z ?? 1 }
    mesh.position.set(...p.at); g.add(mesh)
  }
  g.position.set(obj.position[0], obj.position[1] ?? 0, obj.position[2])
  g.rotation.y = THREE.MathUtils.degToRad(obj.model.rotation_deg ?? 0)
  return g
}
```

Walls, pieces and leaves are all "a box between two plan points":

```ts
function slab(a, b, thickness, y0, y1, color) {
  const dx = b[0] - a[0], dz = b[1] - a[1], len = Math.hypot(dx, dz)
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(len, y1 - y0, thickness), new THREE.MeshStandardMaterial({ color }))
  mesh.position.set((a[0] + b[0]) / 2, (y0 + y1) / 2, (a[1] + b[1]) / 2)
  mesh.rotation.y = -Math.atan2(dz, dx)
  return mesh
}
// wall:   (w.pieces ?? [{ from: w.points[0], to: w.points.at(-1), y0: 0, y1: w.height_m }]).forEach(p => slab(p.from, p.to, w.thickness_m, p.y0, p.y1, w.assumed ? 0xA9AFB0 : 0xD9D4C7))
// door:   slab(o.leaf.hinge, o.leaf.tip, 0.04, 0, o.leaf.height_m, 0xE9B949)
```

**Room view:** cut walls at 1.2 m (`y1 = Math.min(y1, 1.2)`), as in your plan, item 7.

## 3. Scan fixtures – install the detector
Without the detector, scans have walls, rooms, doors and windows, but no toilets or sinks.

1. `python -m pip install ultralytics`, on the server and on any laptop that serves the API.
2. Copy the `models/` folder from Xinran's laptop (`junction-stoa-engine\models\`):
   - `detector.json`, `rooms.json`
   - `cubicasa_yolo11m_1280.pt`, `cubicasa_r2std_1536.pt`, `rtdetr_l_cubi.pt`, `cubicasa_rooms_yolo11m.pt`

   Put it next to `engine/`. **Do not put the `.pt` weights in Git or anywhere public** – hand them over directly.
3. Check: `python -c "from engine import detector; print(detector.available())"` → `True`.

   Then scan scenes include fixtures with models. The detector was trained on CubiCasa (Finnish flats); on other drawing styles check the result before showing it.

## 4. Applying it in your app – keep your local work safe
1. Commit your open work first; stay on `claude/night`. No `git pull` / `reset` / `checkout origin/...`.
2. **Backend:** take only `engine/scene_realize.py` from the engine repo, plus the 3-line call in `agent/docs_api.py` (search for `scene_realize.realize`). To apply the same rules to your Swiss scene, call `engine.scene_realize.realize(scene)` before returning it.
3. **Frontend:** in your 3D / 2.5D component, draw walls from `pieces`, doors from `leaf`, fixtures from `model`, as in §2.
4. Check before recording:
   - Duplex Bathroom 1: door hole visible, leaf opens into the bathroom, shower glass on the room side.
   - School PDF: toilets face away from the back wall, classroom desks inside the classroom.
5. Commit as one change; push with `git push org claude/night` when ready.

## 5. Previews (static, from the same data)
- `eval/integration/preview_3d_duplex_bathroom.png` – IFC: door leaf open into the room, shower / toilet / sink.
- `eval/integration/preview_3d_school_toilets.png` – vector PDF: classroom with desks, toilet cubicles, open doors, windows.
- Make your own: `python tools/scene_preview.py`.
