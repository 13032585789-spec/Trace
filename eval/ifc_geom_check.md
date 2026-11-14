# IFC geometry self-check (engine/ifc_geom.py)

Frame: web-ifc world (X, Y up, Z = -y_ifc), metres. Polygon = [X, Z] on the floor plane.

## kit-fzk-haus_ac20-fzk-haus.ifc

- storeys: Erdgeschoss @ 0.0 m (h 2.7, 6 rooms), Dachgeschoss @ 2.7 m (h None, 1 rooms)
- spaces: 7; outline {'convex hull of the body': 7}
- label_point inside polygon: 7/7

## bsc-duplex_duplex-a-20110907.ifc

- storeys: T/FDN @ -1.25 m (h 1.25, 0 rooms), Level 1 @ 0.0 m (h 3.1, 10 rooms), Level 2 @ 3.1 m (h 2.9, 10 rooms), Roof @ 6.0 m (h None, 1 rooms)
- spaces: 21; outline {'profile': 17, 'convex hull of the body': 2, 'convex hull of the body (profile unusable)': 2}
- label_point inside polygon: 21/21

## bimspeed-warmond_ar.ifc

- storeys: Basement @ -2.4 m (h 0.8, 0 rooms), Entrance @ -1.6 m (h 1.6, 0 rooms), 1. Level @ 0.0 m (h 2.8, 59 rooms), Intermediate level 1 @ 1.4 m (h 1.4, 0 rooms), 2. Level @ 2.8 m (h 2.8, 56 rooms), Intermediate level 2 @ 4.2 m (h 1.4, 0 rooms), 3. Level @ 5.6 m (h 2.8, 56 rooms), Attic @ 8.4 m (h None, 8 rooms)
- spaces: 179; outline {'profile': 179}
- label_point inside polygon: 179/179

## bsc-duplex_duplex-plumbing-20121113.ifc

- storeys: Level 1 @ 0.0 m (h 3.1, 0 rooms), Level 2 @ 3.1 m (h 2.9, 0 rooms), Roof @ 6.0 m (h None, 1 rooms)
- spaces: 1; outline {'profile': 1}
- label_point inside polygon: 1/1

fixtures (16, first 16; rooms from bsc-duplex_duplex-a-20110907.ifc):

| fixture | room | method | exact | nearest walls (m) |
|---|---|---|---|---|
| M_Shower Stall - Rectangular:865 mmx815  | Bathroom 1 | point-in-polygon | True | left 0.0, left 0.0, right 0.591, back 1.356 |
| M_Water Closet - Flush Tank:Private - 6. | Bathroom 1 | point-in-polygon | True | left 0.0, back 0.221, right 0.713, front 1.493 |
| M_Shower Stall - Rectangular:865 mmx815  | Bathroom 1 | point-in-polygon | True | left 0.0, left 0.0, right 0.591, back 1.356 |
| M_Water Closet - Flush Tank:Private - 6. | Bathroom 1 | point-in-polygon | True | left 0.0, back 0.222, right 0.713, front 1.493 |
| M_Lavatory - Oval:535 mmx485 mm - Privat | Bathroom 1 | point-in-polygon | True | left 0.0, right 0.815, left 0.821, left 0.971 |
| M_Sink - Island - Single:455 mmx455 mm - | Kitchen | point-in-polygon | True | front 0.061, right 1.577, left 2.321, right 3.031 |
| M_Sink - Island - Single:455 mmx455 mm - | Kitchen | point-in-polygon | True | front 0.061, right 1.577, left 2.32, right 3.032 |
| M_Bath Tub:1525 mmx760 mm - Private:1525 | Bathroom 2 | point-in-polygon | True | right 0.0, right 0.0, right 0.001, front 2.361 |
| M_Water Closet - Flush Tank:Private - 6. | Bathroom 2 | point-in-polygon | True | right 0.001, right 0.783, back 1.056, front 1.592 |
| M_Lavatory - Oval:650 mmx485 mm - Privat | Bathroom 2 | point-in-polygon | True | left 0.0, right 0.65, left 1.039, left 1.805 |
| M_Lavatory - Oval:650 mmx485 mm - Privat | Bathroom 2 | point-in-polygon | True | left 0.0, left 0.0, left 1.039, left 2.455 |
| M_Lavatory - Oval:650 mmx485 mm - Privat | Bathroom 2 | point-in-polygon | True | left 0.0, left 0.0, left 1.039, left 2.47 |
| M_Lavatory - Oval:650 mmx485 mm - Privat | Bathroom 2 | point-in-polygon | True | left 0.0, right 0.65, left 1.039, left 1.82 |
| M_Water Closet - Flush Tank:Private - 6. | Bathroom 2 | point-in-polygon | True | left 0.0, right 0.781, back 1.072, front 1.592 |
| M_Bath Tub:1525 mmx760 mm - Private:1525 | Bathroom 2 | point-in-polygon | True | left 0.0, left 0.0, left 0.0, front 2.36 |
| M_Lavatory - Oval:535 mmx485 mm - Privat | Bathroom 1 | point-in-polygon | True | left 0.0, right 0.815, left 0.821, left 0.971 |

## Notes
- Distance 0.0 = the fixture's mesh touches the wall face (WC tank, shower tray, tub in an alcove). Cross-checked against
  the room outline: footprint-to-outline distance equals the minimum wall distance on every duplex fixture tested.
- front/back/left/right are the element's own local axes (+Y = front). Revit families usually put the user side at +Y;
  this is not guaranteed, so the direction is a label, the distance is the fact.
- Outlines are convex hulls in plan; an L-shaped wall body could read too close. `exact=False` whenever any geometry
  item was unsupported.
- Not checked here: Tallinn, Hitos (files not available to us). web-ifc COORDINATE_TO_ORIGIN shift is not applied.
