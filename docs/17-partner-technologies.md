# Partner technologies in Trace – what each one does

For the submission forms and the pitch. Status 15 Nov, 05:45. Sources: engine code (`13032585789-spec/Trace`), app repo (`TRACE-Montree/Trace`, `.github/workflows/ci.yml`, README), Diletta's feature list, pitch deck, case study.

| Track | Submit? | Role in one line |
|---|---|---|
| Verda Compute Track | ✅ | Trains the detectors that answer two thirds of the dataset |
| Best Use of Gemini API | ✅ | Reads what only pixels show and routes free wording – never invents a number |
| Best Use of Codex | ✅ | Built the UI where every answer is checked |
| Best Use of Nemotron (NVIDIA) | ✅ | Second, independent count on scans – tells the user which answers to check |
| CRACI | ✅ | Every push and pull request is built and tested on CRACI runners |
| Best Use of Gemma | ❌ | Not used – untick |

---

## 1. Gemini API – Best Use of Gemini

**Role:** the part that code alone cannot do: understand free wording, and read drawings where the only data is pixels. It never invents a number.

**Where it runs**
- **Question routing (backend):** function calling maps a free-form question to the right engine tool and writes the answer sentence. Temperature 0, max 5 steps. A code check rejects any number in the answer that no tool returned.
- **Vector PDF sheets (engine):** the engine extracts facts from the PDF (text, scale, dimensions, door swing arcs, window symbols, tables). Gemini only picks the operation – count tags, count doors, read the schedule, compute an area expression. Code computes the number. For arithmetic, Gemini reads three times; majority wins, a split vote is flagged "uncertain".
- **Scans and raster PDFs (Stoa-style sheets):** image analysis proposes candidates (door hinge + swing arc, window gaps, filled marks). Gemini confirms them and counts tile by tile at full resolution. If readings disagree, a third count on a different grid decides (median); still split → answer marked uncertain.
- **CAD symbol naming:** repeated symbols (toilets, sinks …) are clustered by geometry; Gemini names each cluster once from a montage image – one call per sheet.
- **Sheet sets:** reads title blocks, classifies sheets by discipline and level, picks the right sheet (e.g. door schedule A-801, never the site plan).
- **CubiCasa room types:** one cached vision call per plan answers balconies, saunas, WC rooms, bathrooms and floors.

**Why it matters**
- Without Gemini, all Opening Design sheet-set questions are refused (zero-key run: 0 / 48).
- On scanned plans it lifts accuracy from 81.8 % (fully offline) to 86.0 %.
- 81 % of all questions never call it – cost stays low, and better Gemini versions make Trace cheaper, not obsolete.

**Form wording:** "Gemini never makes up a number. Code computes whatever it can; where only pixels exist, Gemini reads three times, flags disagreement and returns no number when unsure."

## 2. Verda – Compute Track

**Role:** training and hosting compute. It made our own detectors possible – not trainable on a laptop.

**What we did**
- Trained our own detectors on a **Verda A100 80 GB** on 3,604 CubiCasa5k plans: YOLO11m for doors, windows, toilets, sinks, showers/tubs; a second model for rooms; plus an RT-DETR model, used together with YOLO as an ensemble.
- Hosted Nemotron in a Verda container (section 4).

**How we use it**
- On scanned plans the detectors answer count questions with 0 LLM tokens, in milliseconds per plan, one numbered box per item.
- Duplicate boxes nested inside a larger box of the same class are removed (windows → 57 %, showers/tubs → 83 %).

**Why it matters**
- Scanned plans are 67 % of the dataset (85,514 of 127,044 questions).
- On 933 held-out plans: doors exactly right 73 % vs 37 % for a vision LLM; toilets 94 %.
- It is the fully offline mode (81.8 %) for customers whose drawings may not leave their network.
- Path to scale: retraining for a new customer's drawing style ≈ €12 (case study).

**To do:** post the process summary link in the Verda Discord. Use one training figure everywhere – deck says "≈ 1 h on one A100", case study says "5.6 GPU-hours ≈ €12".

## 3. Codex – Best Use of Codex

**Role:** built large parts of the frontend – the layer where a human checks each answer.

**What it built:** Ask page and workspace interactions; the "How I got this" provenance panel (method, source sheet and page, time, tokens, cost); the 3D / 2.5D views (2D Plan · 3D Building · 3D Floor, answered elements in amber); the project page. Commits are tagged `(codex)`; the README lists them under "Built with OpenAI Codex".

**Why it matters:** no effect on accuracy, but it carries Stoa's "visualised reasoning" criterion (25 %): numbered boxes, 3D highlights and Fix count all live in the frontend.

**To do:** verify the latest 2.5D build (FZK, Duplex, Tallinn, Swiss) before recording.

## 4. Nemotron (NVIDIA) – Best Use of Nemotron (one track, listed twice)

**Role:** an independent second opinion on scanned plans.

**What it does:** Nemotron 3.5 Super VL counts the same items again, in parallel with the engine. Agree → badge "2 independent methods agree". Disagree → badge "methods disagree – check the boxes".

**How we use it:** the engine value stays the answer – the detector is right 3–8× more often when they disagree. Nemotron's job is to tell the user which answers to check first. Hosted in a Verda container.

**Why it matters:** medium – it strengthens verifiability, not accuracy.

**To do:** NVIDIA key for the demo; the form needs a written explanation (the paragraph above).

## 5. CRACI

**Role:** the CI/CD that builds and tests every change before it ships.

**What we did:** `.github/workflows/ci.yml` runs both jobs on CRACI runners (`runs-on: craci`) on every push and pull request:
- **backend:** Python 3.12, `pip install -r agent/requirements.txt`, `pytest` – tests use small fixtures and fake model clients, so no data and no API keys enter the build;
- **web:** Node 22, `npm ci`, `npm run build`.

**How we use it:** every build records exactly which packages go into Trace (Python and npm dependencies), and that data is available through the CRACI API. Before the first push the full git history was scanned for keys (`AIza`, `nvapi-`, `sk-`) – none found.

**Why it matters:** Trace handles customers' construction drawings; a supply-chain problem in a dependency (PDF parsing, image libraries, the web build) would reach their data. CRACI shows what ships and catches it at build time.

**To do before submitting:** link one green CRACI run of `ci.yml` in the form. The README still says "actual execution depends on a configured CRACI runner" – update that sentence once the green run is linked.

## 6. Gemma – do not submit

Not used anywhere in Trace (README: "Planned; no Gemma integration is present"). Untick it.

---

## One line each (for the pitch)
- **Verda** trains the detectors that answer two thirds of the dataset.
- **Gemini** reads what only pixels show and routes free wording – it never invents numbers.
- **Codex** built the UI where every answer is checked.
- **Nemotron** counts scans a second time so users know which answers to check.
- **CRACI** builds and tests every change on every push.
