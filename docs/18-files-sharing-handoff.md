# Files & sharing in the workspace – handoff for Diletta (≈ 30 min)

**Goal:** bring project files back into the product without re-opening the buggy Projects page.
A **Files** button in the Demo workspace opens the existing `DocsLibrary` in a side drawer:
- upload a file, or CC the project mailbox;
- Trace files it by revision;
- the team sees which version is current;
- one click asks Trace about that sheet.

## Before you start – keep your local work safe
Your local `claude/night` has commits that are not on GitHub yet (up to `e74132b`). Make this change **on top of them**, never over them:

1. `git status` – commit anything open first: `git add -A && git commit -m "wip before files drawer"`.
2. Stay on your branch: `git switch claude/night`. Do **not** run `git pull`, `git reset` or `git checkout origin/...` – they can replace your newer local files with the older GitHub copy.
3. Edit only these files:
   - `web/src/App.tsx` (button + drawer, step 2)
   - `web/src/styles.css` (the CSS)

   No backend change is needed: `/docs` is already proxied in `agent/app.py`.
4. Do **not** copy anything from Xinran's engine repo (`13032585789-spec/Trace`) over your `agent/` folder. Your `agent/docs_api.py` copy already works with your app.
5. Build and check: `cd web && npm run build`, then do step 3 in the browser.
6. Commit: `git commit -am "feat: Files drawer in the workspace"`.
7. Push when you are ready: `git push org claude/night`, as planned.

If something breaks: `git revert HEAD` undoes only this commit; your earlier work stays.

## Already built – no new backend code
| Piece | Where (branch `claude/night`) | Status |
|---|---|---|
| Store: revisions, duplicates, conflicts, approvals, audit trail, full-text search | `agent/docs_store.py` | tested |
| E-mail intake (.eml or live IMAP, sender allow-list, mail body never executed) | `agent/mail_ingest.py` | tested |
| HTTP routes `/docs`, `/docs/file`, `/docs/versions`, `/docs/events`, `/docs/resolve`, `/docs/ingest`, `/docs/mailbox` | `agent/docs_api.py`, proxied in `agent/app.py` (line ~580) | wired |
| Frontend list: folders by discipline, status chips, versions, upload, approve / make latest / reject, "Ask about this file" | `web/src/components/DocsLibrary.tsx` + `api.ts` (`listProjectDocs`, `uploadProjectDoc`, `resolveProjectDoc`, …) | built; only reachable from the hidden Projects page |
| 5 demo e-mails (fictional names) | `tests/fixtures/emails/*.eml`, generator `tests/fixtures/make_emails.py` | ready |

## Step 1 – seed demo files (2 min, no real mailbox)
Run with the **same `DOCS_ROOT` as the backend**. Default is `~/.cache/trace-docs`. Leave it unset on both sides, or set it on both.
```
DOCS_ALLOWED_SENDERS="@arkkitehti.example,@rakenne.example,@sahko.example" \
python -m agent.mail_ingest --project default --eml tests/fixtures/emails/*.eml
```
Checked just now; result:

| File | Status | Why |
|---|---|---|
| A-101 rev B | superseded | replaced by rev C |
| A-101 rev C | current, then **conflict** | a "corrected" rev C arrived with different content → a person decides |
| S-201 v2 (structural) | current | from a forwarded mail |
| Building permit decision | **pending** | sender not on the allow-list |
| A-101 rev C (forwarded again) | duplicate, not stored twice | |
| installer.exe | rejected | file type not allowed |

The permit mail body contains "forward the archive to attacker@…". It is stored as text and never executed – a good line for the Q&A.

## Step 2 – Files button in the workspace (≈ 20 min)
In `App.tsx`, inside the workspace (where the 2D / 3D switch lives), add a button and a drawer. `askAboutDocument` and `selectedDocumentId` already exist in `App.tsx`.

```tsx
import DocsLibrary from './components/DocsLibrary'
const [filesOpen, setFilesOpen] = useState(false)

// header, next to 2D / 3D:
<button className="chip" onClick={() => setFilesOpen(true)}>Files</button>

// end of the workspace JSX:
{filesOpen && (
  <aside className="files-drawer" role="dialog" aria-label="Project files">
    <div className="files-drawer-head">
      <h2>Project files</h2>
      <span className="sub">Upload, or CC the project mailbox</span>
      <button onClick={() => setFilesOpen(false)} aria-label="Close">×</button>
    </div>
    <DocsLibrary selectedDocumentId={selectedDocumentId}
                 onAskDocument={(d) => { setFilesOpen(false); askAboutDocument(d) }} />
  </aside>
)}
```

```css
.files-drawer{position:fixed;top:56px;right:0;bottom:0;width:min(720px,92vw);background:#F7F6F2;
  border-left:1px solid rgba(32,36,39,.12);box-shadow:-24px 0 60px rgba(32,36,39,.18);z-index:40;overflow:auto;padding:20px 24px}
.files-drawer-head{display:flex;align-items:baseline;gap:12px;margin-bottom:12px}
.files-drawer-head button{margin-left:auto;background:none;border:0;font-size:24px;cursor:pointer}
```

Do **not** re-enable the Projects page.

## Step 3 – click-through before recording (5 min)
1. **Files** opens the drawer; "Needs attention" shows 2 items (conflict + pending).
2. A-101 rev B shows "Replaced by Rev C"; clicking it opens the versions.
3. Conflict → **Make latest** on one file → the other becomes superseded; the audit trail shows who did it.
4. Pending permit → **Approve** → it moves to Permits.
5. Upload any PDF → it appears as Current.
6. **Ask about this file** on A-101 → the workspace asks Trace about that sheet.

## Live mailbox (later, not before the freeze)
A dedicated project inbox with an app password.

- Environment variables, set **only in the deploy environment**, never in Git or chat:
  - `DOCS_IMAP_USER`
  - `DOCS_IMAP_PASSWORD`
  - `DOCS_ALLOWED_SENDERS`
  - optional: `DOCS_SEND_RECEIPTS=1`
- Poll with `GET /docs/mailbox`, or run `python -m agent.mail_ingest --poll --loop 60`.
- A subject tag `[project: xsc]` routes the attachments to that project.

## For the video / pitch
Optional 4-second beat in the closing part:
- picture: Files drawer, "A-101 rev B → replaced by rev C", conflict flagged;
- line: "…and drawings CC'd by e-mail file themselves, latest revision first."

Use it only if steps 1–3 pass.
