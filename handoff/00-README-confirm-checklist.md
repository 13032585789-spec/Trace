# Handoff package — 2026-11-15 04:40 (Trace engine, A side)

Repo: https://github.com/13032585789-spec/Trace (branch `main`). Freeze ~07:30, submission 10:00.

## What is in this folder
| File | For | What |
|---|---|---|
| `16-backend-reply-44.md` | backend | Reply to handoff 44: base URL, auth, endpoints, errors, limits |
| `15-frontend-use-ask-and-evidence.md` | frontend | How to call `/ask` + `/evidence` and draw the boxes |
| `10-handoff-2.5D-scene.md` | frontend 3D | Scene format, frame, north |
| `14-handoff-0310.md` | all | Earlier handoff (still valid) |
| `13-demo-script.md` | demo | Demo flow |
| `integration/` | backend + frontend | 19 real responses (JSON) + 2 evidence PNGs, captured with the vision model on |

## Changes since the samples were captured (engine side, already pushed)
1. **Doors are counted per door leaf** by default (a double door = 2). Door sets stay in `alternatives[]`.
   The school vector sample is `129` (door sets 107 as the alternative).
2. **Door schedule cross-check** on project door counts → `evidence.cross_check`; disagreement lowers confidence to
   `low` and adds a warning. The value itself is never changed.
3. Raster sheets: no more "not shown on this drawing" when only the shrunk whole-sheet read missed the doors.

## Please confirm (reply in the chat, one line each)
1. **Scene check** — run your `node scripts/check_geometry_scene.mjs` on the three files
   `integration/scene_ifc_bathroom.json`, `scene_pdf_vector_school.json`, `scene_scan_school.json`. Pass / failures?
2. **Deployment** — on the server: Python version, is `ultralytics` installed, can you place our detector weights
   there yourselves (we do not redistribute them; we can hand them over directly)? Without them the scan scene has no
   fixtures. Is `GEMINI_API_KEY` set in the deploy environment (do not send the value)?
3. **Frontend** — do you show `alternatives[]` (door leaves / door sets) and `evidence.cross_check` warnings?
   Does the review panel call `/review` with `choose` for the alternative?
4. **Files we still need** — the Tallinn and Hitos files, and the 4 PDF sets you mentioned: path in the dataset or a
   link. We will not tune on Stoa samples.
5. **qa_sweep** — the list of questions that failed in your last sweep (question + file + expected), so we can check them.
6. **Who pushes / merges** — you push your repo; we push only Trace. Any route name you need changed, tell us now.
7. **Demo** — which three questions go in the demo, so we warm the caches before 10:00.

## Rules (unchanged)
- Keys only in local `.env` or the deploy environment; never in Git, chat or docs.
- Stoa samples are not used for training or tuning. RT-DETR weights are not redistributed.
