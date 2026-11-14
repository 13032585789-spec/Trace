# Trace engine: methods and measured results (submission, 15 Nov 2026)

Stoa challenge "Make Blueprints Talk". This page says how each kind of drawing is answered, how well it works on
held-out data, and where it stops. Numbers come from files in this repo; the command that reproduces each is given.

## 1. Principle: read what the file states, never guess

- A drawing is answered from the most exact source it has: IFC geometry and quantities, then vector PDF geometry and
  text, then printed dimensions, then image analysis, then the vision model.
- Every answer carries `value`, `unit`, `items` (boxes or elements with ids), `sources`, `method`, `warnings`,
  `confidence` (high / medium / low / none) and `confidence_reason`.
- When a number is not on the drawing (e.g. a room area on a scan with no printed areas or scale), the answer is
  `value: null` plus what to do ("calibrate the scale and measure"). The review panel lets a person calibrate, measure,
  remove or add boxes; reviewed answers become `+reviewed`, confidence high, and are logged to `corrections.jsonl`.

## 2. Inputs and methods

| input | method | engine module |
|---|---|---|
| IFC model | own STEP parser (no IfcOpenShell): counts, areas, volumes from quantities or geometry; rooms, storeys, room of an element, clearances to walls from real geometry | `ifc.py`, `ifc_answer.py`, `ifc_geom.py` |
| Swiss DXF plans | room polygons and labels from the DXF | `swiss.py`, `dxf.py` |
| Vector PDF sheet | pdfplumber facts: words (incl. rotated), scale, tags, filled marks, door swing arcs (circle fit), window symbols (parallel lines, panes from mullions), rooms traced, schedules; LLM only chooses the operation, code computes | `sheet.py`, `docqa.py` |
| Scan / photo | image analysis proposes candidates (filled marks, window gaps, door hinge + swing arc); Gemini counts tile by tile and confirms; an independent door check flags disagreement; area from two printed dimension strings | `scanqa.py` |
| Raster floor plan (CubiCasa style) | YOLO + RT-DETR ensemble trained on Verda (doors, windows, toilets, sinks, showers/tubs), room detector, Gemini for room types; rules chosen on validation plans | `detector.py`, `cubicasa.py` |
| Sheet set (one building, many sheets) | title block classification (sheet no., discipline, level), rules or LLM pick the sheets, code combines | `sheetset.py`, `project.py` |

Counting rules agreed with the domain lead: windows are counted per pane separated by a mullion (purchase view) and
per opening (installation view) and both are returned; doors count only where a swing arc is drawn.

## 3. Results on held-out data

| set | questions | correct | command |
|---|---|---|---|
| Swiss dwellings, test split | 7,724 | **99.97 %** | `python eval/run.py --source swiss_dwellings --split test` |
| IFC models, all | 3,062 | **99.31 %** (test split 98.41 %) | `python eval/run.py --source ifc_models` |
| CubiCasa5k, test split | 16,694 | **85.98 %** (was 85.02 % before nested-box suppression) | `python eval/run.py --source cubicasa5k --split test` |
| CubiCasa5k, zero-API (no data leaves the machine) | | 80.84 % (last measured before suppression) | same, without GEMINI_API_KEY |
| Stoa vector sheets (3 PDFs) | 24 | 24/24 | `python tools/sheet_run.py` |
| Stoa example sheets (4 low-res scans, not used for tuning) | 15 with a known answer | 13 exact; doors +7 %, windows -6 %, pipe supports +4 % | `python tools/stoa_samples_run.py`, `eval/stoa_samples_result.md` |

CubiCasa per category (test): toilet 94.0, door 73.1, window 57.2, sink 82.7, shower/tub 82.5, storeys 97.9,
WC rooms 96.5, bathrooms 93.0, bedrooms 95.3, kitchens 97.6, saunas 94.0, balconies 88.9 %.

### Confidence is calibrated

On the CubiCasa test split: answers marked **high are correct 95.7 %** of the time (8,980 answers), **medium 81.1 %**
(5,684), **low 56.7 %** (2,030). Swiss and IFC answers are all high (100 % / 99.3 %). The level comes from the method
and, where a method is measured, from its held-out accuracy (`engine/confidence.py`), so a user knows which answers to
check first.

### Box quality (eval/scan_boxes_iou.md)

Matched boxes are tight (mean IoU: doors 0.93, windows 0.86, toilets 0.86, showers/tubs 0.78). The main window error
is adjacent windows merged into one box, not loose boxes. Suppressing a box that lies 70 % inside a bigger box of the
same class raised window answers 53.8 -> 57.2 % and shower/tub 76.6 -> 82.1 % on the test plans (fair subset of
plans no model trained on: windows 56.9 -> 55.4 %, shower/tub 78.8 -> 82.2 %; reported, not hidden).

### Distances (renovation)

`ifc_geom.clearances` measures from a fixture's own mesh to each wall of its room: distance, the two closest points,
the wall id, and a common direction (N/E/S/W from the model's TrueNorth, else model +Y flagged as project north;
the element's own front/back/left/right is kept as a reference only). Checked on the Duplex plumbing model against the
architectural rooms: 16/16 fixtures placed in the right room, footprint-to-outline distance equals the minimum wall
distance on every fixture (`eval/ifc_geom_check.md`). On PDFs and scans a distance is given only where it is printed
or after the user calibrates the scale.

## 4. Limits we know

- Scans: door counts can overshoot when swing arcs are faint (flagged `uncertain` with alternatives); slab area by
  type on the sample slab plan reads one bay (30.84 m2) where a hand reading gives 61.7 m2.
- Windows on raster plans: thin strips and joined windows remain the weakest category (57 %).
- IFC: outlines are convex hulls in plan; L-shaped walls can read too close (`exact=false` when geometry is partly
  unsupported). Tallinn and Hitos models were not available to us for checking.
- Coordinates follow web-ifc (Y up, Z = -y); a viewer that moves the model to the origin must add that offset.

## 5. Sponsor tech

- **Gemini API**: vision counting and confirmation on scans, room types on raster plans, choosing sheet operations.
- **Verda**: all detector training (A100); see `docs/08-verda-compute.md` for models, before/after and cost.
- Data: the Stoa sample images were never used for training or tuning; ground-truth annotations are used only to measure.
