# Buildable 2.5D from any drawing – engine side (Xinran)

This replaces plan item 10 ("pure PDF: wait for Xinran"). `/api/geometry/scene` now returns a **buildable** building for vector PDFs and scans. It is not a stroke-by-stroke copy: it is a building that could stand.

## What the engine does (`engine/scene_realize.py`, on by default; `&realize=0` turns it off)
1. **Closed outer wall:** the building outline (rooms + walls, closed) becomes a solid ring. Gaps get a wall.
2. **Every room edge is a wall:** walls between rooms, and between a room and the outside, are added where the drawing has none. Doorways are kept open: a door's swing zone never gets a wall.
3. **One wall height per storey:** 2.8 m. Storey height is 3.0 m if the drawing gives none.
4. **Doors and windows sit in a wall:** each one is snapped onto the nearest wall centreline and gets `wall_id` and `rotation_deg` (same convention as IFC). The original point is kept in `snapped_from`. Missing heights use typical values: door 2.1 m, window 1.2 m with a 0.9 m sill.
5. **Wall ends meet:** close ends are joined; short gaps to a crossing wall are closed (T-joints).
6. **Fixtures stand in a room:** `room_id` by point-in-polygon. A missing footprint gets a typical size (toilet 0.40 × 0.70 m, sink, bath, shower, stove), with `footprint_assumed: true`.
7. **Boxes outside the building are ignored:** legend boxes and the title block are skipped (`rooms_outside_building_skipped`).

**IFC is real geometry:** it is only measured, never changed.

**Nothing is invented silently:** every added wall has `assumed: true` and `method: realize:room-edge | realize:envelope`, and drawn walls keep `assumed: false`.

**Viewer:** draw assumed walls in Betongrau `#A9AFB0`, drawn walls in Anthrazit `#202427`, at the same height.

## Measured on the two school samples (target ≥ 95 %)
| `scene.realism` | Vector PDF | Scan |
|---|---|---|
| room edges on a wall (before → after) | 88.6 % → **99.6 %** | 74.5 % → **97.8 %** |
| outer ring closed (before → after) | 77.3 % → **99.8 %** | 79.9 % → **97.1 %** |
| doors / windows sitting in a wall | **97.4 %** | **96.1 %** |
| fixtures inside a room | 94.2 % (chairs/tables in corridors) | – (no detector on this server) |
| wall length straight from the drawing | 82.9 % | 53.0 % |
| walls added | 114 | 308 |
| time | 0.7 s | 0.8 s |

Previews (top view: dark = drawn wall, grey = added wall, yellow = door, blue = window):
- `eval/integration/preview_realized_pdf_vector_school.png`
- `eval/integration/preview_realized_scan_school.png`

Updated samples: `eval/integration/scene_pdf_vector_school.json`, `scene_scan_school.json`.

## For the frontend (Diletta's plan, items 1–8 unchanged)
- Item 1 (completeness check): show `scene.realism` instead of building your own; "Geometry incomplete" only when `room_edge_coverage.after < 0.95`.
- Item 6 (Swiss walls): Swiss comes from your B-side scene, not this route. To get the same rules there, call `engine.scene_realize.realize(scene)` on your Swiss scene. The format is the same (handoff 42); no change needed.
- Item 7 (room view): fixtures now carry `room_id` – filter by it.
- Item 9 (Duplex): pass `space_model` as before. Plumbing file `data/ifc_models/bsc-duplex_duplex-plumbing-20121113.ifc` + architecture `bsc-duplex_duplex-a-20110907.ifc` (sample `scene_ifc_bathroom.json`: 1 shower, 1 toilet, 1 sink, 73 pipes).

## Honest limits
- Positions match the drawing. Wall height, door and window heights and fixture sizes are typical values (MVP), marked in the data.
- On scans without a scale the units are image units: the building shape is right, but sizes are not metres.
- A few short grey stubs can remain at door jambs; noisy scan rooms (e.g. a stair symbol) can produce a zig-zag wall. They are marked `assumed` and can be hidden.

## Fixtures as 3D models (added 06:55)
Every fixture now carries `model.primitives`. These are simple shapes in metres the viewer can build directly:
- `box`: `size [w, h, d]`, `at [x, y, z]`
- `cylinder`: `radius`, `height`, `scale_z` for an oval, `at`

Each primitive has a `material`: ceramic · plastic · metal · wood · glass · water.

**Local frame:** origin on the floor at the fixture centre; x = width, y = up, z = depth, with the **front at +z**. Rotate by `rotation_deg` about y (three.js), the same convention as walls and doors.

| Category | Model |
|---|---|
| toilet | tank + oval bowl + seat |
| urinal | wall unit |
| sink | basin + pedestal |
| vanity | cabinet + top + basin |
| bathtub | tub + water surface |
| shower | tray + two glass panels |
| stove | body + 4 burners |
| table / desk | top + 4 legs |
| chair | seat + back + 4 legs |

Sizes are typical, not measured (`model.note` says so).

**Orientation:** on drawings, front/back of a symbol is not readable. Toilets, sinks, baths, showers and stoves now stand **with their back against the nearest wall** (`front_vector`, `orientation_from`). IFC fixtures keep the model's own position and rotation; only the shape is added.

**Room:** cubicles that the drawing did not close are assigned to the nearest room within 2 m. Fixtures in a room went from 94.2 % to **99.6 %** on the school PDF.

Previews (walls cut at 1.0 m, like the planned room view):
- `eval/integration/preview_3d_school_toilets.png`
- `eval/integration/preview_3d_duplex_bathroom.png`
