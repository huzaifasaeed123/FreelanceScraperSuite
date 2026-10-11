# Telegram Module — Implementation Plan

Goal: add Telegram to the existing admin panel as the first of many bot modules (10–15 planned).
The operator links several real Telegram accounts, the module captures their chats, the operator
builds reusable message workflows and runs one over selected chats, **one chat at a time**, with a
pause after every step. Everything is controlled from the panel.

Requirements source: the German developer brief (sections 1–15). Every requirement is mapped to a
phase in the table at the end.

---

## 1. Decisions (settled)

| Topic | Decision |
|---|---|
| Telegram library | **Telethon** (MTProto, real user accounts). The Bot API cannot read existing chats or act as a normal account. |
| Database | **The one existing SQLite database** (`storage/db.sqlite`), same engine/metadata as Jaumo. No second file. Tables are prefixed `tg_`. Models use only portable SQLModel/SQLAlchemy types (plain `JSON`), so a later move to another database needs no model changes. |
| Backend layout | One folder per bot under `modules/`, **three files**: `api.py` (tables + routes), `engine.py` (bot logic), `__init__.py` (declaration). |
| Frontend | **Same admin panel, no React, no build step.** One vanilla `panel.js` per bot, loaded lazily when its tab opens. |
| Process model | Single uvicorn worker (already required by the Dockerfile); the bot engine runs as asyncio tasks inside it. |
| Languages | Panel text German by default with English fallback, using the panel's existing `LANG` switch. |

---

## 2. Architecture

### 2.1 Backend

```
modules/
  base.py            BotModule + ModuleContext contract                (shared, written once)
  registry.py        AVAILABLE list, loads modules, mounts routes      (shared, written once)
  telegram/
    __init__.py      module = BotModule(key="telegram", ...)           (~8 lines)
    api.py           tg_* tables + /api/telegram routes                ("normal backend")
    engine.py        Telethon sessions, chat capture, workflow runner  ("bot engine")
    panel.js         the Telegram UI                                   (one file)
```

- **Adding the next bot** = create `modules/<key>/` with the same files + add `"<key>"` to
  `AVAILABLE` in `registry.py`. `main.py` is never edited again.
- The registry gives each module automatically: routes at `/api/<key>` **behind the panel login**
  (a module cannot forget auth), its own storage folder `storage/<key>/`, startup/shutdown hooks,
  a live-event channel (`hub.publish("<key>:events", {...})` → WebSocket `/ws/modules/<key>`), and
  an entry in `GET /api/modules` (the manifest the panel reads).
- `ENABLED_MODULES=telegram,...` in `.env` loads only some modules (default: all).
- If `api.py` or `engine.py` of a bot grows too large it can be split later; not up front.
- Jaumo code stays as it is (not migrated into `modules/`).

### 2.2 Frontend (vanilla, shared shell)

The existing shell (`index.html` + `app.js`) keeps the login, sidebar, topbar, theme, language.
Today a tab is a `<section class="tab" id="tab-x">` plus an entry in `TAB_LOADERS`. A small
**module host** (about 50 lines in `app.js`, added once in Phase 2) does this for every module:

1. After login, `GET /api/modules`.
2. For each module, add a sidebar group (like the Jaumo group) with its `nav` entries, and create an
   empty `<section class="tab hidden" id="tab-<tab>">` per entry.
3. Register a `TAB_LOADERS` entry that loads `panel.js` once (a `<script>` tag), then calls the
   module's `open(tab, container)`.
4. Expose the existing helpers to modules as `window.PanelKit = { api, toast, openModal, guard,
   esc, icon, wsUrl, fmtDate, relTime, t }` so each `panel.js` is small and looks like the rest.

A module's `panel.js` registers itself:

```js
PanelModules.telegram = { open(tab, el) { /* render into el */ }, close(tab) { /* close sockets */ } };
```

### 2.3 Request / data flow

```
panel.js ──REST──▶ api.py ──▶ SQLite (tg_*)
   ▲                 │
   │              engine.py ──Telethon──▶ Telegram
   └──WebSocket /ws/modules/telegram◀── hub.publish("telegram:events", …)
```

---

## 3. Data model (all in `modules/telegram/api.py`, already created)

| Table | Purpose |
|---|---|
| `tg_account` | Linked account: phone, api_id, api_hash, `session_string`, status (offline/connecting/online/error), status_msg |
| `tg_chat` | One contact per account: telegram_id (str), username, display_name, first/last contact, last_message, `chat_status` (pending/in_progress/done/error/paused), messages_sent, last_processed_at, error_reason, notes |
| `tg_workflow` | Name + `steps` JSON: `[{"type":"text\|image\|voice", "content"/"file", "pause_after": seconds}]` |
| `tg_run` | One execution: account, workflow snapshot (frozen at start), status, counters, resume point (`current_run_chat_id`, `current_step_index`), `next_action_at` |
| `tg_run_chat` | A chat inside a run: position, status, steps_done, error_reason, timestamps — the audit trail |

Limits enforced by the API: account label 60 characters, workflow name 80, text step 4096, chat notes 2000, at most 100 steps per workflow, api_id 1..2^31-1, api_hash 64 characters, voice files 50 MB (also after conversion), images 10 MB. `tg_chat` also holds `access_hash` (needed to send) and `search_text` (lower-cased name/username/id for search and sorting; backfilled at startup).

Security rules: `session_string` and `api_hash` are **never** returned by any endpoint (show
`…last4` like the APK secret hint). A session string is full access to the Telegram account.

---

## 4. Account linking (how the operator signs an account in)

Telegram logins are interactive: phone → code Telegram sends → optional two-step password. The
panel hides this behind a 3-step dialog, so the operator only ever types what Telegram shows them.

```
 Accounts  ▸  [ + Telegram-Konto verbinden ]

 Step 1   Phone number  [+49 …]
          API ID / API Hash  [   ] [   ]   (remembered after the first account; link to my.telegram.org)
          [ Code senden ]
 Step 2   "Telegram hat einen Code gesendet (in der Telegram-App oder per SMS)"
          Code [ _ _ _ _ _ ]     [ Zurück ]  [ Bestätigen ]
 Step 3   (only if the account has two-step verification)  Password [    ]  [ Fertig ]
 Done     ● Online — account appears in the list; chats start syncing
```

- API ID/Hash come from my.telegram.org (one-time). They are stored in the panel settings and
  pre-filled for every further account, so account 2..N only needs a phone number and a code.
- Backend: `engine.start_login()` keeps a short-lived pending client (5 min) → `finish_login()`
  signs in, stores the StringSession, sets status Online. A wrong/expired code returns a clear
  message and lets the operator retry without starting over.
- Each account row shows: status badge (Online / Offline / Fehler), Verbinden, Trennen, Neu
  anmelden (if the session was revoked), Entfernen.
- On server start all accounts that have a session reconnect automatically.

---

## 5. Run engine design (the important part)

- One asyncio task per run; only **one active run per account**; different accounts may run at the
  same time (chats within a run are strictly sequential — never in parallel).
- Loop: for each `tg_run_chat` in `position` order → for each step: send → persist progress →
  wait `pause_after` seconds → next step. Chat finished → mark done, next chat.
- **Pause/Resume** uses a gate, not task cancellation: the runner awaits an `asyncio.Event` between
  actions and sleeps in small slices, so *Pause* freezes the countdown (remaining seconds are kept)
  and *Resume* continues at exactly the same chat/step with the remaining time.
- **Stop** ends the run; unprocessed chats are marked `skipped`. **Neustart** = a new run over the
  same workflow and chat selection.
- **Errors:** a failed step marks that chat `error` (reason stored, e.g. "user privacy settings",
  "FloodWait 120s") and the run continues with the next chat. The run has an `on_error` option
  (`next` / `retry` with N attempts). An error never stops the whole run.
- **FloodWait** (Telegram rate limit) is waited out and shown in the live panel, then retried.
- **Restart safety:** at startup, runs left `running` are set to `paused` with their position kept,
  so the operator can resume after a deploy (same idea as Jaumo's `mark_interrupted`).
- **Live status** (WebSocket): current chat, current step, next step, seconds until the next
  action, processed / total, success, errors, percent.

---

## 6. Phases

Each phase ends in a working, testable state and is implemented and verified before the next.

### Phase 1 — Module foundation  ✅ DONE
`modules/base.py`, `registry.py`, `telegram/__init__.py`, `telegram/api.py` (5 tables +
`GET /api/telegram/status`), `main.py` hooks (load, startup/shutdown, mount, generic WebSocket
`/ws/modules/{key}`), Dockerfile copies `modules/`, `telethon` in requirements, `tests/test_modules.py`.
**Result:** server starts, tables exist in the one database, routes need login, the 160 existing
tests + 5 module tests pass.

### Phase 2 — Panel module host + Telegram shell  ✅ DONE
- Module host in `frontend/app.js` only (`index.html` is untouched — sections are created from the
  manifest): sidebar group per module (header = first page, sub-menu = the rest, fold state remembered),
  one tab section per nav entry (`#tab-<key>-<tab>`, hash route `#<key>-<tab>`), lazy `panel.js`
  loading, `window.PanelKit` helpers, `window.PanelModules[key] = { open, close }`, `close` called when
  leaving a tab. `switchTab` now opens whichever sidebar group holds the page (was Jaumo-only).
- `modules/telegram/panel.js`: six tabs (Dashboard / Konten / Chats / Abläufe / Versand / Verlauf);
  Dashboard shows live counts from `/api/telegram/status`, the others are placeholders. German/English.
- Registry serves `panel.js` uncached; nothing else from a module folder is public.
**Verified:** in a real browser (Edge via Playwright) — all six tabs open and exclusively visible, deep
link + reload works, language switch re-renders, Jaumo dashboard/accounts unchanged, mobile menu OK, no
console errors; `tests/test_modules.py` 6 passed.
**Not yet added (on purpose, with first use in Phase 3):** a `PanelKit` helper for the module WebSocket.

### Phase 3 — Account linking (brief §1)  ✅ DONE (needs one check with a real account, see below)
**Built:** `engine.py` (Telethon login with code and two-step password, connect / disconnect, reconnect at
startup in the background, live status events, friendly error messages); `api.py` routes
`/settings`, `/accounts`, `/accounts/start`, `/{id}/code|password|cancel|connect|disconnect`, `PATCH`,
`DELETE`; `auto_connect` column (a manually disconnected account stays off after a restart); Konten tab
with the 3-step dialog, status badges that update live over the module WebSocket, rename, remove;
`PanelKit.moduleSocket`. Server messages are English and translated to German in `panel.js`.
Behaviour worth knowing: a session Telegram has ended is cleared (status Fehler, "Anmelden" button); a
network error keeps the session; closing the dialog half-way removes the half-created account; API
ID/Hash are only remembered after Telegram accepted them.
**Verified:** 17 backend tests against a fake Telethon client (`tests/fake_telegram.py`, plugged in with
`TELEGRAM_CLIENT_FACTORY`) incl. 2FA, wrong code/password, revoked session, network error, restart
reconnect, WebSocket events, secrets never returned; full browser walk-through (Edge/Playwright) of the
dialog, live updates, rename, delete, language switch, mobile.
**Still to do by hand:** link one real account once (needs API ID/Hash from my.telegram.org) — the fake
client cannot prove Telegram's real behaviour (code delivery, rate limits).

(Original scope, kept for reference:)
- `engine.py`: client pool, `start_login` / `finish_login` (code + 2FA), `connect` / `disconnect`,
  reconnect at startup, status updates published to the WebSocket.
- `api.py`: `POST/GET/DELETE /accounts`, `POST /accounts/{id}/code` and `/password`, `/connect`,
  `/disconnect`, settings for the remembered API ID/Hash.
- `panel.js`: Konten tab with the 3-step dialog and status badges (live via WebSocket).
- Tests use a fake Telethon client (no real Telegram traffic in tests).
**Done when:** a real account links with phone + code, shows Online, survives a server restart,
can be disconnected and reconnected.

### Phase 4 — Chat capture and Chats tab (brief §2, §6 selection basis)  ✅ DONE (needs one check with a real account)
**Built:** live NewMessage capture + background chat sync (iter_dialogs, batched, FloodWait, per-account guard), access_hash column, /chats list|ids|summary|{id}|PATCH|bulk-status, sync-chats; reusable chatTable in panel.js with selection across paging, live refresh, sync progress.
**Verified:** 27 new tests (24 backend, 3 Edge UI) and full suite 205 passed; independent browser check (DE/EN/390px, HTML names, reload mid-sync, double sync).
**Open:** real Telegram untested (iter_dialogs FloodWait, min-user access_hash). (Long unbroken names now wrap; fixed in Phase 10.)
- `engine.py`: initial import of existing private dialogs, plus a live `NewMessage` handler that
  creates/updates `tg_chat` (first/last contact, last message, name/username) for **incoming**
  messages. Outgoing counts update `messages_sent`.
- `api.py`: `GET /chats` (search by name/username/id, filter by status and date, sort, paginate),
  `PATCH /chats/{id}` (status, notes), `POST /chats/bulk-status`, `POST /accounts/{id}/sync-chats`.
- `panel.js`: Chats tab — table, search, status chips (🟢 🔵 ✅ ❌ ⏸), date filter, checkboxes,
  "n Chats ausgewählt" counter, "alle unbearbeiteten auswählen".
**Done when:** existing chats appear after sync and a new incoming message shows up live.

### Phase 5 — Workflows and media (brief §3, §4, §5, §14)  ✅ DONE (real ffmpeg conversion only tested with a stand-in)
> Exists: workflow CRUD/duplicate/rename with one-place STEP_TYPES validation, media upload/serve/delete with magic-byte checks and ffmpeg to OGG/Opus, and the Abläufe tab (cards, step editor, drag + buttons, pauses, validation, unsaved warning).
> Verified: 305 tests pass (2 real-ffmpeg skips), Edge walk-throughs in German, English and 390 px build, reorder, save and reload the brief workflow.
> Known minor: the English "not a image file" toast is not translated. Only text, image and voice steps exist; other message types (video, file, sticker, ...) are refused on purpose (tests/test_telegram_gaps.py).
- `api.py`: workflow CRUD + duplicate; media upload/serve/delete into `storage/telegram/media/`
  with type/size validation.
- Voice memos: accept `.ogg`/`.opus` directly; other formats (mp3/m4a/wav) converted with `ffmpeg`
  (installed in the Docker image) because Telegram only shows a real voice bubble for OGG/Opus.
- `panel.js`: workflow list + editor — step cards (text / image / voice), per-step pause
  (0 / 10 / 30 / 60 s, minutes, free input), edit / replace / delete, drag-and-drop reorder (native
  HTML5 drag), add step, save, duplicate. Image preview and audio player in the cards.
- Validation: at least one step, text not empty, media exists, pause ≥ 0.
**Done when:** workflows such as Sprachmemo → 60 s → Text → 30 s → Bild → 10 s → Sprachmemo can
be built, saved, reloaded unchanged, and several workflows coexist.

### Phase 6 — Run engine (brief §7, §8, §9, §11)
**Status: DONE.** RunEngine (engine.py) with one task per run, gate-based pause/resume, stop, restart, error mapping, retry, FloodWait, offline pause and restart recovery; /runs routes in api.py.
Sends text/image/voice to InputPeerUser from the stored access_hash; chat statuses and counters are persisted per step and published on the WebSocket.
Verified by tests/test_telegram_runs.py (32 tests against the fake client) and an independent full-suite run: 337 passed, 2 skipped (ffmpeg missing).
- `engine.py`: the runner from section 5 (sequential, gate-based pause/resume, stop, error handling,
  FloodWait, restart recovery) and the three send functions (text, image, voice note).
- `api.py`: `POST /runs` (validates: account online, no other active run for it, ≥ 1 chat),
  `GET /runs`, `GET /runs/{id}`, `POST /runs/{id}/pause|resume|stop|restart`.
- Tests against a fake client: order of messages, pause timing, resume position, error continues,
  stop marks the rest skipped, restart recovery.
**Done when:** a run sends a workflow to 3 real test chats in order with the right pauses, and
pause / resume / stop behave as specified.

### Phase 7 — Run UI and live status (brief §6, §7, §9, §10, §15)
**Status: DONE.** Versand tab: START form (workflow, presets, reused chat table, on_error, confirmation) and live panel (badge, current chat/step, countdown, progress, counters, per-chat results, Pause/Fortsetzen/Stoppen/Neustart); sidebar run badge.
The module WebSocket stays open for the login session and every (re)connect re-reads /runs, so reloads and dropped sockets recover; tab switches leak no timers or sockets.
Verified by tests/test_telegram_runs_ui.py (4 browser tests, DE/EN/390 px) plus an independent browser walk and full suite: 341 passed, 2 skipped (ffmpeg missing).
- Versand tab: choose workflow → choose account → select chats (same table as Chats, with
  filters and "n Chats ausgewählt") → big **START**.
- Live panel from the brief: bot status, current chat, current step, next step, countdown, progress
  bar, processed / success / errors, Pause / Fortsetzen / Stoppen / Neustart.
- Per-chat result list for the running run (error reasons visible).
**Done when:** the operator can start and fully control a run from the panel and always see which
chat/step is active, the next pause, how many are done/open, and the errors.

### Phase 8 — Dashboard and history (brief §12, §13)
**Status: DONE.** Dashboard tab: GET /stats with all section-13 values as 10 KPI tiles, a live run card (module WebSocket), last-run summary and a UTC sends-per-day chart; account filter.
Verlauf tab: filterable runs table with durations, per-chat detail (time, result, error reason), CSV export (runs and per run), cleanup by days, delete run; chat statuses stay untouched.
Verified by tests/test_telegram_history.py (17) and test_telegram_history_ui.py (8 browser tests, DE/EN/390 px) plus an independent browser walk and full suite: 366 passed, 2 skipped (ffmpeg missing).
- `GET /stats` and the Dashboard tab: all chats, unprocessed, processed, with errors, running
  workflow, successful / failed sends, last run, active chat, progress.
- Verlauf tab: every run (start, end, workflow, chats selected / ok / errors / aborted, duration)
  with a detail view of which chat was handled when and its result; CSV export; old-run cleanup.
**Done when:** every item of brief §12 and §13 is visible in the panel.

### Phase 9 — Hardening  ✅ DONE
**Built:** a watcher task per connected account (lost connection -> status "connecting", its runs pause with
"Connection to Telegram lost", a reconnect loop with doubling waits 2 s ... 60 s; a session Telegram has ended -> status
"error", login dropped, runs paused, panel offers "Anmelden"); a periodic session check; per-run `auto_resume` (default off);
PeerFlood counted on the run (`peer_floods`) and shown as banner + toast, FloodWait toast; the Versand form shows a limits notice
and the auto-resume option; `GET /media/unused` and `POST /media/cleanup` with an "Ungenutzte Dateien" dialog; abandoned logins
removed at startup and by a janitor task; shutdown awaits every task and closes every client; operator guide below.
**Verified:** tests/test_telegram_hardening.py (21) and test_telegram_hardening_ui.py (5), fake client extended with control.json.
Independent gate: full suite 392 passed, 2 skipped (no ffmpeg); own Edge walk-through (German, English, 390 px) of drop, Trennen,
manual resume, revoke, PeerFlood banner and toast, unused-files dialog, HTML in chat names escaped, no console errors.
Not exercised: real Telethon (is_connected / get_me semantics), the Docker image with ffmpeg.
(Original scope, kept for reference:)
- Revoked/banned session → account status Fehler with a re-login prompt.
- Dropped connection mid-run → reconnect and continue.
- Safe defaults and warnings: automated first-contact messages from user accounts can get accounts
  limited; the run UI recommends non-zero pauses and shows FloodWait events plainly.
- Log retention, media cleanup for deleted workflows, documentation for adding the next bot module.
**Done when:** a long run survives network drops and a server restart without losing its place.

---

### Phase 10 — Comprehensive testing (last)  ✅ DONE
**Status: DONE.** Contract, integrity/scale, run matrix, security, UI-quality and gap tests plus the browser acceptance test of brief §1-§15 (tests/test_telegram_*.py); 1389 tests pass, 5 skipped (no ffmpeg, export has no paging).
Verified by an independent gate: full suite green, own browser walk (all tabs, DE/EN, 390 px, HTML in names escaped, no console errors) and API abuse probes (huge ids, bad JSON, wrong state transitions).
Open: real Telegram/ffmpeg only via fake client; browser Back between tabs not supported by the shared shell.
Run by separate test agents after Phase 9, reviewed by the main agent; the result is written up in `TELEGRAM_TEST_REPORT.md` (includes the manual checklist for the operator).
- **Contract & auth:** a generic test walks every route of the module and proves each one refuses an
  anonymous caller; negative tests (bad ids, bad bodies, wrong states) for every endpoint.
- **Data integrity:** deleting accounts/workflows/runs leaves no orphans; foreign keys; duplicate chats
  across syncs; big data (10,000 chats: pagination/search speed; a 1,000-chat run with 0 s pauses).
- **Engine:** pause/resume/stop at every position (mid-step, mid-pause, between chats); pause timing
  accuracy; two runs on one account refused; two accounts in parallel; restart recovery matrix (while
  running / paused / in a pause); FloodWait, revoked session and network drop mid-run; no leaked tasks.
- **Acceptance (browser, fake client):** the whole brief, §1–§15, as one scripted scenario.
- **Security:** secrets never returned; upload validation (type, size, path traversal, double
  extensions); HTML in chat names/messages/workflow text is escaped in the panel; no SQL built from input.
- **UI:** German and English, phone width, console free of errors, drag and drop with keyboard fallback.
- **Regression:** the Jaumo tests and all module tests (the 178 tests before Telegram testing began, 1389 passed + 5 skipped in total now).
- **Manual checklist for the operator** (cannot be automated, needs real accounts): link a real account,
  sync, run a workflow with a voice memo to 2–3 own test chats, watch a FloodWait, leave a long run overnight.

---

### Added after the first live test (client feedback)
- **Step type "Nutzer blockieren"** (`block`): a final action, only allowed as the LAST step (once). Sends Telegram's plain
  `contacts.BlockRequest` - no spam report and the chat is NOT deleted (the two boxes of the app's block dialog stay
  unticked, as the client wants it). The contact is flagged `blocked` in the Chats table; unblocking is manual in Telegram.
- **Display time of images/voice** (`self_destruct`): like Telegram's own menu - Nicht löschen / Einmalig zeigen / 3 / 10 / 30 s
  (a voice message: only once). Sent as Telethon `ttl` (once = 2147483647, what the official apps send). Not yet tried against
  real Telegram: check on the first live run that the photo really shows the flame icon and opens only once.
- **Open the chat first** (`mark_read`, on by default, a checkbox on the Versand start form): before the first message of each chat the
  contact's messages are marked as read (`send_read_acknowledge`), so the customer sees the two ticks before our messages arrive.
  Once per chat (not again when a chat is resumed in the middle); a failure of that call never fails the chat. Stored on the run, so
  a restart of the run keeps the choice. Dashboard button "Daten auf null setzen" resets the stored chats and runs.
- **Main dashboard = overview** (client request): one card per project - Telegram (from its module), WhatsApp as "coming soon"
  (until a `whatsapp` module exists), Jaumo (its own stats) - each with three numbers, a status and a link to the project's own
  dashboard. The former Jaumo dashboard is now the first page of the Jaumo group (`#jaumo`). Telegram card: Open chats /
  Sent (messages) / Replies. A module opts in with `BotModule(summary=fn, color="#hex")`; `GET /api/modules/summary` collects
  the cards (a failing module shows as error, never breaks the others).
- **Replies** (`replied_at` on a chat): set when the contact answers something we sent - live (a message arriving after we wrote),
  or found by a later sync (the contact's last message is newer than our last run on the chat). First answer kept. Shown as
  "geantwortet" in the Chats table, as the "Antworten" tile on the Telegram dashboard and on the overview card.
- **No reset button** (client request: too easy to wipe the statistics by accident). The button and the `POST /reset` route are
  removed; every chat and run stays in the statistics. If a reset is ever needed, it is done once on the server by hand.
- **Upload names with dots** (WhatsApp names like `... at 01.23.45.ogg`) are accepted; the old "double extension" rule
  protected nothing (files are stored under a generated name and judged by their content).

## 7. How the work is run (orchestration and testing)

- **Main agent** (this session) owns the plan, hands each phase to a separate **phase agent**, and
  decides whether a phase is accepted. Phases run one after another (they edit the same files).
- **Phase agent** gets: the goal, the phase section of this file, the relevant brief sections, the
  structure rules (§2: `api.py` / `engine.py` / `panel.js`, one database, no new top-level folders,
  minimal shell changes), and must return a report: files changed, endpoints, tests added + results,
  browser evidence, deviations, open problems. It writes tests with the phase, never commits.
- **Gate after every phase (main agent, independently of the agent's report):**
  1. read the diff and check scope (nothing unrelated touched, structure rules kept);
  2. run the new tests, then the **full suite** (Jaumo regression must stay green);
  3. UI phases: browser walk-through with screenshots (Edge/Playwright, German + English, phone width);
  4. trace the brief requirements the phase claims to evidence (test or screenshot);
  5. only then mark the phase done here. A failed gate sends the phase back to the agent with the findings.
- **Final:** Phase 10 (above), then a summary for the operator with the manual checklist.

---

## 8. Requirements coverage

| Brief section | Phase |
|---|---|
| 1 Connect account, status, disconnect/reconnect, dashboard stats | 3, 8 |
| 2 Capture chats, fields, search/filter, statuses | 4 |
| 3 Workflow, step types, edit/move/delete/replace | 5 |
| 4 Individual pauses (0 s … free input) | 5 |
| 5 Workflow editor, drag and drop | 5 |
| 6 Select chats (single, multiple, all unprocessed, filters, count) | 4, 7 |
| 7 START, chats worked one after another | 6, 7 |
| 8 No parallel processing | 6 |
| 9 Pause / resume / stop / restart, current chat visible | 6, 7 |
| 10 Live status | 7 |
| 11 Error handling, continue or retry | 6 |
| 12 History | 8 |
| 13 Dashboard | 8 |
| 14 Several saved workflows | 5 |
| 15 Overall goal visibility | 7, 8 |
| (all of the above) end-to-end | 10 |

---

## 9. Adding the next bot later (recipe)

1. Create `modules/<key>/` with `__init__.py` (a `module = BotModule(...)`), `api.py`, `engine.py`,
   `panel.js`. Prefix its tables with a short key (`tg_`, `ig_`, ...).
2. Add `"<key>"` to `AVAILABLE` in `modules/registry.py`.
3. Done — routes, auth, storage folder, live channel, sidebar group and tabs come from the framework.

What the Telegram module taught us (do the same for the next bot):

- **Own every task.** Start background work only through one `_spawn()` that remembers the task; on shutdown cancel all of
  them, `await asyncio.gather(..., return_exceptions=True)`, then close the connections. A task that catches
  `CancelledError` must close what it opened (half-open clients) and re-raise.
- **A watcher per live connection.** Never trust that a client stays connected: look at `is_connected()` on a timer, keep the
  status honest (online <-> connecting), pause dependent work with a reason, reconnect with doubling waits. Distinguish "network
  problem" (keep the login, retry) from "login ended" (drop the secret, ask for a new login, never retry).
- **Pause with a reason, resume by the operator.** Work that depends on a connection pauses (position and countdown kept); an
  opt-in flag resumes it by itself, but a pause the operator set is never lifted automatically.
- **A failing health check must not end the loop.** Log and go on; the same for event handlers.
- **Make failures testable.** The fake client reads a control file so a test can drop the connection, revoke or ban a session
  and count connects/disconnects (`tests/fake_telegram.py`). Windows: start the server in its own process group and use
  CTRL_BREAK to test a graceful shutdown (`AppServer.stop_gracefully`).
- **Housekeeping from day one:** unused uploaded files (never delete a file younger than an hour: an editor may be about to
  save it), half-made logins, old history.
- Server messages stay English; the panel translates the known ones; every new message needs a line in the DE table.

## 10. Operator guide (Telegram)

**1. Get API ID and API Hash (once).** Sign in at https://my.telegram.org with the phone number, open "API development
tools", create an application (any name) and copy `api_id` and `api_hash`. The panel remembers them for further accounts.

**2. Link an account.** Konten -> "Telegram-Konto verbinden": phone number (with country code) -> "Code senden" -> enter the code
Telegram sends (in the Telegram app, chat "Telegram", otherwise SMS) -> if the account has a cloud password, enter it. The account
turns "Online" and its chats are imported in the background.

**3. Build a workflow.** Abläufe -> "Neuer Ablauf": add steps (text, image, voice memo), set the pause after each step,
drag to reorder, save. Use pauses above 0 seconds.

**4. Start a run.** Versand: choose the account, the workflow and the chats (presets for "all not processed"), choose what
happens on errors and whether the run should resume by itself after a connection drop, press START and confirm. Chats are
worked one after another. Pause / Fortsetzen / Stoppen / Neustart are on the live panel; Verlauf keeps every run.

**5. What the statuses mean.** Account: Online (connected), Verbindet (connecting or reconnecting after a drop, it retries by
itself), Offline (you disconnected it, it stays off), Fehler (see the message; "Telegram hat diese Sitzung beendet" or "gesperrt"
means log in again with "Anmelden"). Run: AKTIV, PAUSIERT (the reason is shown: Konto offline, Verbindung verloren, Server neu
gestartet, Sitzung beendet), FERTIG, GESTOPPT, ABGEBROCHEN. Chat: Noch nicht bearbeitet, In Bearbeitung, Bearbeitet, Fehler
(reason in the list), Pausiert.

**6. FloodWait.** Telegram asks to wait n seconds: the run waits and goes on by itself, the countdown shows "Wartezeit von
Telegram". Frequent FloodWaits mean the pauses are too short: raise them.
**PeerFlood.** Telegram has limited the account for writing to new people. The run shows a red banner; the affected chats are
errors. Stop, wait some hours (sometimes a day), use longer pauses and fewer new contacts; later restart the run over the error
chats ("Alle mit Fehler").

**7. Revoked or banned session.** The account turns "Fehler", running work pauses with the reason. Konten -> "Anmelden" (same
phone number). If the run had auto-resume it continues by itself, otherwise press "Fortsetzen". A banned account cannot be
fixed here (Telegram support).

**8. Housekeeping.** Abläufe -> "Ungenutzte Dateien" lists and deletes uploads that no workflow uses; Verlauf cleans old runs.
