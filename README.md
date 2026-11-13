# junction-stoa-engine

Developer A layer for *Make Blueprints Talk*: raw drawing data -> exact answer + evidence.
Pure Python 3 standard library (numpy + opencv only for PNG box calibration). No ezdxf / ifcopenshell needed.

## Run
```
export JUNCTION_DATA=/path/to/junction-dataset        # folder with questions.jsonl and data/
python ask.py data/swiss_dwellings/site3387_bldg5238_floor23498.pdf "How many toilets (WC) are drawn on this floor plan?"
python eval/run.py --source swiss_dwellings          # or ifc_models; --split dev|test
```
Swiss needs the `.dxf` (and `.png` for boxes) next to each other; IFC questions on a `<model>_<level>.pdf` are answered from `<model>.ifc`.
First IFC load builds a cache in `~/.cache/junction-engine` (about 1 min for all models).

## Interface (agreed with developer B)
`engine.answer.answer(path, question)` returns
`{value, unit, items:[{category, guid? | bbox_m, png_bbox, pdf_bbox_pt, name?, storey?, area_m2?}], sources:[...], method, warnings}`.
`guid` -> highlight in the IFC viewer; `png_bbox` (pixels) / `pdf_bbox_pt` (PDF points, page 1) -> draw a box on the drawing.

## Scores (README rules: counts exact, areas/lengths/volumes within 2%)
| source | questions | correct |
|---|---|---|
| swiss_dwellings | 37,584 | 98.6% (held-out test split 99.0%) |
| ifc_models | 3,062 | 98.0% |
| cubicasa5k | 85,514 | not started: raster only, needs a vision model |
| opening_design | 48 numeric | not started |
| ifc_bench | 820 text | not scored automatically |

## How it works
* `engine/dxf.py` reads ASCII DXF. `engine/swiss.py`: rooms = ROOM_OUTLINE polygon containing the room-number text, name = nearest label;
  apartments = UNIT_OUTLINE with a letter label; door = 5-vertex leaf polyline; window = closed rectangle on WINDOW;
  fixtures = rectangles on FIXTURE classified by what is inside (69-pt outline = bathtub, square+dot = shower,
  48-pt bowl: off-centre = WC, centred = washbasin). `engine/swiss_view.py` calibrates DXF metres -> PNG pixels per drawing.
* `engine/ifc.py` reads IFC STEP text: storeys, spaces, elements, quantity sets (unit-scaled), type objects, and space footprint
  area from geometry (extrusion profiles, B-rep bottom faces). `engine/ifc_answer.py` maps 9 languages of question templates to queries.
  Space area priority: geometry > Qto NetFloorArea > national area property.
* `engine/questions.py` multilingual (EN/DE/FR/IT) Swiss templates.

## Known gaps
* Swiss: unlabelled numbered rooms are sometimes counted in apartment/indoor totals and sometimes not (about 1% of Swiss questions).
* IFC: storey total area 77%, wall side area 88%, wall volume 91%.
* Failing questions per run: `eval/results/fails_*.jsonl`.

Licences: drawings keep the licence in `data/<source>/LICENSE.md` (cubicasa5k is CC BY-NC-SA).
