# Jaumo Bot — Admin Panel

## Project structure

```
77-JaumoBot/
├── bot/
│   └── engine.py          # JaumoClient (request layer), BotRunner (signup+swipe), MessageRunner
├── api/
│   ├── main.py            # FastAPI app: routes, WebSockets, startup (seed + legacy import)
│   ├── manager.py         # global thread pool, run lifecycle, event → DB/WebSocket fan-out
│   ├── proxies.py         # proxy line parsing, testing, ProxyPool (assignment)
│   ├── models.py          # SQLModel tables + SQLite engine (WAL)
│   ├── schemas.py         # Pydantic request shapes, ConfigSettings validation
│   ├── auth.py            # signed-cookie login
│   └── settings.py        # env settings
├── frontend/              # index.html + app.js + style.css (vanilla, no build step)
├── storage/               # THE single persistent volume (git-ignored)
│   ├── db.sqlite
│   ├── photos/
│   └── accounts.txt       # legacy file — imported once on startup, renamed to .imported
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Run locally

```
pip install -r requirements.txt
copy .env.example .env      # set ADMIN_PASS, SECRET_KEY
uvicorn api.main:app --port 8000
```
Open http://localhost:8000. **Always one uvicorn worker** — run state, proxy pool and WebSockets live in-process.

---

## Design decisions

### Engine (`bot/engine.py`)
- Everything is per-instance (proxy, device, APK credentials) → safe for parallel threads. No module globals change at runtime.
- **Jaumo request layer is unchanged** (signature, headers, endpoints, payloads). Only moved onto `JaumoClient`.
  `JAUMO_BASE_URL` env can point at a fake server for testing.
- Events go out through `emit(kind, data)`: `log`, `step`, `account_created`, `account_update`, `swipe`, `message`.
- Stop is responsive: delays use `stop_event.wait()`, checks between steps and every card.
- Gender is always **female** (looking for male).

### Swiping
- Runs **until blocked or stopped**: keeps fetching new zapping batches.
- `like_ratio` decides like vs dislike per card.
- `block_threshold` consecutive failed actions (e.g. 403) → account `blocked`, run ends.
- `max_empty_batches` empty batches in a row → run `done` ("no more cards").
- `max_swipes` optional cap (0 = unlimited).

### Accounts
- Account row is created right after signup (tokens never lost), then updated live.
- Status: `signing_up → active | photo_failed | blocked | failed`; admin stop keeps a ready account `active`.
- Liked / disliked / matches / messaged stored as JSON lists + counters.

### Messaging (separate job)
- Admin starts it from the Accounts tab (selected accounts or all eligible).
- One run per account: refresh token → message matches not yet messaged → random template from config.
- **TODO (needs APK analysis):** `MessageRunner.fetch_new_matches()` — matches that arrive after the signup run.

### Proxies
- Admin pastes lines (`host:port:user:pass`, `user:pass@host:port`, `scheme://user:pass@host:port`).
- **Shared** line = rotating gateway, all bots can use it at once.
- **Dedicated** lines = sticky session, one bot per line; extra bots wait until a line frees up.
- Dedicated preferred over shared; least-recently-used first. Test button shows exit IP + country.
- Config `require_proxy` (default on): no enabled proxy → run fails instead of going direct.

### Identity (global, Settings page)
- *Never reuse a name* / *Never reuse a photo* — one rule for every configuration. Name **and** photo are picked and
  reserved at launch (under a lock), so parallel launches never collide; a reservation is released if the bot fails
  before signup.
- Photo library: bulk upload of images, folders or ZIPs; images are re-encoded to clean JPEG (rotation fixed,
  EXIF/GPS removed, max 1600px, min 320px), duplicates skipped by hash, thumbnails generated. Used photos can't be deleted.

### Account page (live)
- `#account/<id>`: profile, stats, live session (step + log), activity timeline (`AccountEvent`: like / dislike / match /
  message / status), matches with messaged state, liked/disliked lists, all sessions, notes/status.

### Jaumo Accounts page (client layout)
- Dark navy UI by default (light/dark switch) and German by default (DE/EN switch in the user menu).
- Toolbar: search (name, ID, Jaumo ID, location, "worker-2"), status (Aktiv / Arbeitet / Gesperrt / Fehler / Gestoppt),
  worker, filter popover (location, created from/to, sort), "Neuer Account" (one by one or N parallel workers).
- Header cards: total accounts, likes, matches, messages (inbox), actions — each with "+N heute" from AccountEvent.
- Rows: photo, name, ID, Jaumo ID, created date · stats tiles (likes, dislikes, matches, messages, visits, actions) ·
  status · worker (Worker-NN = parallel slot that created it) · last activity (relative, live) · view / edit / ⋯ menu.
- No "bot" wording in the UI: accounts are created by workers, one by one or in parallel.
- **Open (needs APK endpoints):** `Account.messages_received` (chats in the inbox) and `Account.profile_visits` stay
  empty ("–") until an inbox / visitors sync is implemented in the engine.

### Configurations
- Named configs with: APK profile, like ratio, max swipes, block threshold, age range, name pool,
  photo pool, signup photo URLs, locations, devices, message templates, all delays, request timeout.
- Names: **Auto** (built-in list of 200 female first names) or **Custom** (pasted list); typed names at launch go first.
  Names are picked and reserved at launch under a lock, least-used first. **Unique names** (default on): a name any
  account already has is never reused; typed duplicates are rejected; launch fails clearly when the list runs out.
  A reservation is released if the bot fails before signup. The editor strikes through used names.
- **Signup details**: every field sent to `signup/register` is shown; looking_for_gender, relationship_search,
  dating_relationship_search and allow_in_all_brands are editable (defaults = original values).
- **Messaging enabled** switch per config (default off): the messaging job refuses configs where it is off.
- Locations: same coordinate pool as the original bot; Jaumo resolves coordinates to the city at run time.
- **APK profiles** keep client_id + sign_secret + User-Agent together (must match the same APK build).
  Secrets are no longer in the code — add them in the panel (or seed via `JAUMO_*` env on first start).
- Each run stores a snapshot of its config, so editing a config doesn't change history.

### APK profiles (switch when one expires / gets banned)
- Keep several profiles; each config points at one. Switching is manual, from the panel.
- Health is recorded by every signup run at the client-token step: last OK, last failure + error,
  OK/fail counts, failure streak. Network/proxy errors are not counted against the APK.
- 3+ failures in a row → profile shows **failing** and the dashboard shows a warning banner.
- Disabled profiles cannot be launched. Disabling one that is in use opens **Switch configs…**, which moves
  every config to another profile in one click (healthiest suggested). Running bots keep their profile.
- Editing a profile's credentials resets its failure streak.
- DB columns added later are created automatically on startup (`_add_missing_columns`).

### Concurrency
- **One bot** with a FIFO queue of account sessions. *Settings → Accounts at the same time* (default 1, stored in the DB,
  changeable while running) decides how many accounts it works on in parallel. No `MAX_BOTS` env var any more.
- On startup, runs left `running/queued` by a restart are marked `interrupted`.
- Bot threads push to WebSockets with `loop.call_soon_threadsafe`.

---

## Status

- [x] Step 1 — Engine refactor (BotRunner / MessageRunner / JaumoClient)
- [x] Step 2 — Database models (SQLite + WAL)
- [x] Step 3 — FastAPI backend + cookie auth + WebSockets
- [x] Step 4 — Parallel execution with queue + stop
- [x] Step 5 — Proxy pool (shared / dedicated lines)
- [x] Step 6 — Frontend panel (Dashboard, Runs, Configurations, Proxies, Photos, Accounts)
- [x] Step 7 — Docker setup (single volume `/app/storage`)
- [ ] Step 8 — Coolify deploy
- [ ] Jaumo-side work (after APK analysis): fetch later matches, verify block signals / match response keys

## Coolify deploy

1. Push **this folder** as the root of its own private repo (not the whole FreelanceScraperSuite repo).
   `.env` and `storage/` are git-ignored — nothing secret in the code.
2. Coolify → New Resource → Docker Compose (or Dockerfile) → repo URL.
3. Env vars: `ADMIN_USER`, `ADMIN_PASS`, `SECRET_KEY` (+ optional `JAUMO_*` seed).
4. Persistent storage: mount one volume at **`/app/storage`** (DB + photos).
5. Domain → Coolify provisions SSL; WebSockets work through Traefik out of the box.
6. To carry over existing data: copy `storage/` contents into the volume (or upload photos in the panel).
