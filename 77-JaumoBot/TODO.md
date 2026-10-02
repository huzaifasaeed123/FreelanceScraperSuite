# Next steps — bugs, fixes and features

Status: **plan only — nothing below is implemented unless marked "done locally".**
Rule for this round: everything is built and tested **locally**; **nothing is pushed** until approved
(the server is creating accounts right now).

Contents
1. [Already done locally (not pushed)](#1-already-done-locally-not-pushed)
2. [Statistics: what each number means (client definition)](#2-statistics-what-each-number-means-client-definition)
3. [Stats sync from Jaumo (likes / visitors / messages / matches received)](#3-stats-sync-from-jaumo)
4. [Signup values exactly as the APK expects (relationship dropdowns)](#4-signup-values-exactly-as-the-apk-expects)
5. [Remove "Signup photo URLs" from the panel](#5-remove-signup-photo-urls-from-the-panel)
6. [Bot log in the Coolify runtime log](#6-bot-log-in-the-coolify-runtime-log)
7. [Live updates: how they work and reducing API calls](#7-live-updates-how-they-work-and-reducing-api-calls)
8. [Smaller fixes](#8-smaller-fixes)
9. [Tests](#9-tests)
10. [Release (only after approval)](#10-release-only-after-approval)
11. [Open questions — please answer before implementation](#11-open-questions)
12. [Backlog (not in this round unless requested)](#12-backlog)

---

## 1. Already done locally (not pushed)

| # | Change | Files | Tested |
|---|---|---|---|
| 1.1 | **City radius**: each account gets a random point inside a circle around the city (default radius per config, optional per city `label,lat,lon,radius_km`). Even spread, true circle, radius 0 = old behaviour. Point stored on the account (`latitude`, `longitude`) and shown on the account page. | `bot/engine.py` (`jitter_location`), `api/schemas.py`, `api/models.py`, `api/manager.py`, `frontend/app.js` | maths verified with 20 000 points; **needs** an engine + integration test (see §9) |
| 1.2 | **Live updates fix**: the Accounts list / dashboard / account page no longer freeze while a worker is busy (debounce replaced by throttle — refresh at most every ~1–1.5 s). | `frontend/app.js` | browser test passes |
| 1.3 | **Phone layout**: Photos page filter bar no longer makes the page scroll sideways. | `frontend/style.css` | browser test passes |
| 1.4 | **Search ranking**: exact matches (ID, Jaumo ID, name) are listed first. | `api/main.py` | integration test passes |
| 1.5 | **Test suite**: fake Jaumo (signature-checking), fake proxy, engine / integration / resilience / browser tests. | `tests/`, `pytest.ini` | 30 + 16 + 11 + 10 passing, 1 failing (see 9.2) |
| 1.6 | Engine change "refresh token after photo" was **reverted** on request — `bot/engine.py` only differs from the deployed version by 1.1. | `bot/engine.py` | `git diff` checked |

---

## 2. Statistics: what each number means (client definition) — ✅ done locally

The client's definitions (German original → meaning → where the number comes from):

| Panel label (DE) | Client definition | Meaning | Source | Today |
|---|---|---|---|---|
| **Likes** | erhaltene Likes, die unser Profil geliked haben | likes **received** | Jaumo `likesIn` (sync, §3) | ❌ not collected |
| **Besucher** | erhaltene Besucher, die unser Profil besucht haben | profile **visitors** | Jaumo `visitsIn` (sync) | ❌ not collected (shown "–") |
| **Nachrichten** | erhaltene Nachrichten, die dem Profil geschrieben wurden | messages **received** (contacts who wrote to us) | Jaumo `conversationsIn` (sync) | ❌ not collected (shown "–") |
| **Matches** | Übereinstimmung im Matchgame durch Liken | mutual likes | like response `match:true` **plus** later matches found by sync | ⚠️ only instant matches counted |
| **Gesendete Likes** | Likes, die wir gesendet haben | likes **sent** | bot (swipe) | ✅ (currently labelled "Likes" — **wrong label**) |
| **Dislikes** | die wir als nicht-like getätigt haben | dislikes **sent** | bot (swipe) | ✅ |
| **Nachrichten gesendet** | wenn wir Nachrichten an User gesendet haben | messages **sent** | messaging job | ✅ (only on account page) |
| **Aktionen** *(from the first screenshot)* | Aktionen, die wir gemacht haben | sent likes + dislikes + sent messages | computed | ✅ — keep? see Q2 |

### Steps
2.1 **Database** (`Account`, auto-migrated): add `likes_received`, `visits_received`, `messages_received`
    (exists), `matches_synced` (list of user ids), `stats_synced_at`, `stats_sync_error`. Keep existing
    `liked_count` = sent likes, `disliked_count`, `messages_sent`.
2.2 **Matches** = union of instant matches (swipe) and matches found by sync; `matches_count` = size of the union.
    The messaging job then also reaches matches that happened after the swipe session.
2.3 **API**: `/api/accounts`, `/api/accounts/{id}`, `/api/accounts/summary`, export: return all 7 (8) numbers
    with clear names (`likes_received`, `visits_received`, `messages_received`, `matches`, `likes_sent`,
    `dislikes_sent`, `messages_sent`, `actions`). Unsynced values stay `null` → panel shows "–", never 0.
2.4 **Accounts page** (client layout):
    - header cards: Gesamt Accounts · Likes (received) · Matches · Nachrichten (received) · Aktionen
    - row tiles (2 rows of 4): **Likes · Besucher · Nachrichten · Matches** / **Gesendete Likes · Dislikes · Nachrichten gesendet · Aktionen**
    - "+N heute" only where we know when it happened (sent values, matches); received values show "synced X ago".
2.5 **Account page**: same 8 numbers with the client's wording; "Last synced" + Refresh button (§3).
2.6 **Dashboard**: rename "Likes" → "Gesendete Likes" where it means sent; add received numbers once synced.
2.7 **Translations**: DE labels exactly as the client wrote them; EN equivalents
    (Likes received, Visitors, Messages received, Matches, Likes sent, Dislikes, Messages sent, Actions).
2.8 Tooltips on each tile with the client's definition, so nobody confuses sent and received again.

---

## 3. Stats sync from Jaumo — ✅ done locally

**Goal:** fill Likes (received), Besucher, Nachrichten (received) and later Matches — **read-only**, and
**not continuously** (each sync costs proxy traffic and Jaumo requests).

### What we already know (from the live log of "Sabrina Lehmann")
`GET /me` returns the exact links:
```
likesIn          https://api.jaumo.com/v2/me/likes/in/
visitsIn         https://api.jaumo.com/v2/me/visits/in/
conversationsIn  https://api.jaumo.com/v2/conversation/inbox/
```
The bot never calls them today — that is why visitors/messages show "–" (unknown, not zero).

### APK findings (2026-10-02)
- **All URLs come from the API root**: `Endpoint "Production" = https://api.jaumo.com/v2/` (`com/jaumo/network/Endpoint`).
  The app loads `GET /v2/` → `V2 { links }` and takes every address from it (no hard-coded paths).
- `V2.Links.unseen` → **`UnseenResponse`** (`com/jaumo/unseen`): integer counters
  **`likes`, `visits`, `conversations`, `matches`, `requests`, `communities`**. Used by the app for its badges
  (`GetUnseen` = GET of `links.unseen`). Our accounts are never opened in the app, so nothing is marked seen —
  the counters equal the totals received. **One request for all received numbers.**
- `V2.Links.likes` = `{in, mutual, out, matchInfo}`, `V2.Links.visits` = `{in}`,
  `V2.Links.conversations` = `{in, trash, chatbot}` (`com/jaumo/v2/V2$Links*`).
  `likes.mutual` = the app's **matches list**; lists are `UserListResponse {items, links{next, previous}}`
  (no total field → counting a list means paging).
- Inbox list = `InboxListResponse {countNew, items, noResult, links}`, item has `countUnseenMessages`, `lastSender`.
- `ResolveUserListUrl`: LikesIn → `likes.in`, LikesOut → `likes.out`, VisitsIn → `visits.in`, around → `users.around`.

**Chosen sync flow (cost ≈ 3 requests/account):** refresh token → `GET /v2/` → `GET links.unseen`
→ only if `matches` > matches we already know: page `links.likes.mutual` (max 5 pages) to get the match user ids
for the messaging job. Mapping: Likes ← `likes`, Besucher ← `visits`, Nachrichten ← `conversations`,
Matches ← `matches` (ids from `likes.mutual`). The raw (redacted) `unseen` response is kept in the sync log so the
mapping can be checked against the first real account.

### Steps
3.1 **APK analysis first** (no guessing — the app must recognise every request):
    - find the request code for `likes/in`, `visits/in`, `conversation/inbox` in `decoded apk/smali*`
      (method = GET, query parameters such as `limit`/`offset`/`cursor`, headers);
    - find the response models: is there a **total count** field (one cheap request) or must we page
      through the list (more requests = more cost)?
    - find how the app detects **matches** after the fact (a `matches` link, a flag in `likesIn` items,
      or the conversation list) → decide the source for §2.2;
    - write the findings into this file before coding.
3.2 **Engine**: new read-only `StatsSyncRunner` (separate from signup/swipe; the signup/swipe flow is not
    touched): refresh token → `GET /me` (to get the current links, never hard-code them) → the 3 GETs →
    counts. Uses the account's own device id/device model, APK profile and a proxy, exactly like the
    messaging job. Sends nothing, changes nothing on the account.
3.3 **Triggers — no background polling:**
    - **Refresh button** on the account page (one account);
    - **Refresh stats** for the selected rows on the Accounts page (bulk), and "all active" with a confirm
      dialog that shows the number of accounts (= cost);
    - **cooldown 15 s per account** (button disabled with a countdown; the API refuses earlier calls with
      a clear message) — see Q1 for the exact meaning of "after 15 seconds".
3.4 **Queue**: sync jobs run through the same worker queue (respect "accounts at the same time"),
    kind = `sync`, with log + status like other sessions; they never run on an account that is busy.
3.5 **Storage**: write the numbers + `stats_synced_at`; on failure keep the old numbers and store the
    error (shown as a small warning on the account page).
3.6 **Panel**: "synced 3 min ago" under the numbers; values never synced stay "–".
3.7 **Cost display**: before a bulk refresh show "N accounts × ~4 requests".

---

## 4. Signup values exactly as the APK expects — ✅ done locally

Fields sent to `signup/register` today: `gender`, `birthday`, `looking_for_gender`, `photo_url`, `name`,
`relationship_search`, `dating_relationship_search`, `allow_in_all_brands`, `location_permission`,
`notifications_services`. The panel currently lets the admin type **free text** for the two relationship
fields — a wrong value would not be recognised by the app.

### Already found in the APK
- `com/jaumo/signup/model/SignUpStepResponse$RelationshipStepResponse$RelationshipItem.smali` defines the
  relationship options: **`UNSET`**, **`FLIRT`**, **`FRIENDSHIP`** (with title/subtitle/icon per item).
- `com/jaumo/signup/model/SignUpStep.smali` (lines ~378/403) writes **both** `relationship_search` and
  `dating_relationship_search`.
- `com/jaumo/signup/notificationservices/data/NotificationServicesSet.smali` — values for `notifications_services`.

### Steps
4.1 **Trace the flow in the APK** (step → model → request): which UI step sets `relationship_search`, which
    sets `dating_relationship_search`, and which of `UNSET / FLIRT / FRIENDSHIP` each one may carry
    (they may differ). Also confirm `looking_for_gender` values, `allow_in_all_brands` ("1"/"0"?),
    and what `location_permission` / `notifications_services` contain when the user allows/denies.
4.2 **Check the server's own list**: the bot already calls `GET signup/defaults` before registering
    ("APK calls this before registering — returns allowed values"). Log its response once (redacted) and
    compare with 4.1 — the allowed values come from Jaumo itself.
4.3 **Panel**: replace the text inputs with **dropdowns** containing only the values confirmed in 4.1/4.2,
    each with the app's own wording (e.g. FLIRT = "Flirt/Dating", FRIENDSHIP = "Freundschaft").
    Default stays **FRIENDSHIP** (what the working script sent) until you decide otherwise (Q5).
4.4 **API validation**: the backend accepts only those exact values (enum), so nothing else can reach the bot.
4.5 **Bot**: sends the chosen value unchanged (no mapping, no case change) in the same field order as today.
4.6 **Tests**: fake Jaumo rejects unknown values; one test per allowed value proves panel → API → bot →
    request body carries exactly that value.
4.7 Show the chosen values on each account page (what the account was registered with).

---

## 5. Remove "Signup photo URLs" from the panel — ✅ done locally

The original script sent one fixed `photo_url` at registration
(`https://i.jaumo.com/gallery_orig/113550,0339ee18d142fbf39e.jpg`). Opening it gives 404, but registration
works with it — Jaumo does not seem to use it as the profile picture (the real picture is uploaded after
signup from the photo library).

### Steps
5.1 Remove the textarea from the configuration editor and the "Also sent" hint mentions it as a fixed value.
5.2 Bot always sends the original fixed value (constant in `bot/engine.py`, exactly as the original script).
5.3 Old configs that still contain `signup_photo_urls` are ignored (no migration needed; no validation error).
5.4 Check in the APK (with 4.1) whether the app sends `photo_url` at all / empty / a real URL — if the app
    sends it empty, decide with you whether to keep the original fixed value (it worked) or match the app.

---

## 6. Bot log in the Coolify runtime log — ✅ done locally

Today the bot's log goes only into the database (Runs & logs, account page). Coolify shows only HTTP lines.

6.1 Also print each **info / warning / error** line to the server output as
    `[session 12 · Worker-01 · Sabrina Lehmann] [LIKED] User 7137…` (no HTTP bodies, no tokens).
6.2 Start/finish of every session with its result (`done`, `blocked`, `failed: reason`).
6.3 Optional env `LOG_BOT_TO_STDOUT=0` to turn it off.

---

## 7. Live updates: how they work and reducing API calls — ✅ done locally

**How it works today (WebSocket + refetch):** the server pushes small events over one WebSocket
(`/ws/events`: "session 12 changed", "account 5 changed"). The page then **re-loads** the data it shows
(`/api/accounts`, `/api/accounts/summary`, `/api/stats`). While a worker swipes, an event arrives every few
seconds, so the browser re-loads those endpoints about once per second — that is the repeated requests you
saw in DevTools. Each call is small (12 rows), but it adds up with several open tabs.

### Steps
7.1 **Push the data, not just "something changed"**: send the updated counters in the WebSocket event and
    patch the visible row/cards directly — no HTTP request for counter changes.
7.2 Re-load the list only when the **set of rows** changes (new account, status change) — at most every 3 s.
7.3 `/api/stats` and the summary: at most every 5 s while work is running; not at all while idle.
7.4 Pause all refreshes while the browser tab is hidden; catch up once when it becomes visible.
7.5 Keep the account page's per-account WebSocket (already push-based for the timeline/log).
7.6 Measure before/after: number of requests per minute with 1 and 3 workers busy (target: ≤ 1/3 of today).
    **Result (3 workers busy, browser open):** accounts page 180 → 16 requests/min, dashboard 80 → 8 requests/min.
    Counters now arrive as `counters` WebSocket events and patch rows/cards in place (test: `test_counters_are_pushed_without_reloading_the_list`).

---

## 8. Smaller fixes — ✅ done locally

8.1 **"Neuer Account" with an empty photo library**: the first start on the server failed with 422
    ("no photos") shown only as a short red toast. Show the reason inside the dialog and disable
    "Create" with a link to Fotos (same for "no APK profile", "no proxy" when required).
    ✅ done locally — `POST /api/runs/check` runs the same checks as the start (nothing is started); the dialog lists
    every reason with a "Beheben" link and disables Create until it is fixed.
8.2 **First-run checklist** on the dashboard (APK profile ✓ · proxy ✓ · photos ✓ · names ✓) so setup is obvious.
    ✅ done locally — uses the same server check; shown only while something is missing, each item with "Beheben".
8.3 Config editor: group "advanced" sections (devices, delays) as collapsible, keep the important ones on top.
    ✅ done locally — Signup details, Devices and Delays are collapsed at the bottom; an invalid field opens its section.

---

## 8b. Panel structure per client mockup (2026-10-02) — ✅ done locally

- Sidebar: Übersicht → Armaturenbrett; collapsible **Jaumo** group (header = accounts overview) with
  Konfiguration · Fotos · Proxies · Nicknamen · Städte · Logs / Protokolle. Ready for more bots as further groups.
- **One configuration** (no list, no duplicate/delete). `GET/PUT /api/config` (partial saves); runs, messaging and the
  start check use it when no `config_id` is sent. On an existing server the configuration used for the latest signup
  is kept.
- **APK keys from env vars** `JAUMO_CLIENT_ID` / `JAUMO_SIGN_SECRET` / `JAUMO_USER_AGENT`; if not set, the APK profile
  already stored on the server keeps being used. The Konfiguration page shows the source and health (read-only).
- Einstellungen page removed: workers, stats-refresh pause and photo rule → Konfiguration; name rule → Nicknamen;
  locations + radius → Städte.
- Left out on purpose (need new Jaumo requests in the engine, decided with the user): Nicknamen-ändern,
  Profiltexte / Über mich, Emails.
- Before deploying: if `JAUMO_*` env vars are set in Coolify, they win — make sure they hold the keys that work now.

---

## 8c. Continue swiping after a stop — ✅ done

- New job `swipe` (`POST /api/accounts/swipe`, `POST /api/accounts/{id}/swipe`): an existing account logs in again
  with its stored token and device identity and runs the same swipe loop — no signup, photo or location change.
  Skips accounts that are working, blocked, never fully set up, or have no token. Same worker queue as creation.
- Engine: new `SwipeRunner` class only (58 added lines; BotRunner unchanged).
- Panel: "Weiter swipen" in the row menu, bulk bar and account page; "Stats aktualisieren" also in the row menu.

---

## 8d. Profile text / Über mich — ✅ done

- APK flow (EditAboutMeViewModel -> UserManager.C): `GET me.links.data` (MeData) -> `PUT` its `aboutme` link with the
  form field `data=<text>` (same family as the existing `me/data/location` call).
- Engine: `JaumoClient.set_about_me`; BotRunner sets the reserved text after the photo is verified, before swiping.
  A rejected text is logged and the account continues.
- Panel: "Profiltexte / Über mich" page (one text per line, usage, "never reuse a text"), off by default; texts are
  reserved per signup like names; start check + setup checklist; the text is shown on the account page.

---

## 8e. Agreed next steps (2026-10-03) — items 1–4 ✅ done

Finding from the live log (2026-10-03 01:47): the "unlock" answer on zapping is NOT a daily like limit. Jaumo sent
`"items": null` with an `unlock` dialog of `"type": "rate_app"` ("Will you give us 5 stars?") and
`"unlockExpiresIn": 147` — cards are locked for ~2.5 min, after ~380 actions in that session.

1. **Wait out short Jaumo pauses instead of ending the session.** When zapping returns `unlock` with
   `unlockExpiresIn` below a limit (proposal: 15 min), log "Jaumo-Pause N s (<dialog type>)", wait that long
   (+ a few random seconds, stop-aware), then fetch cards again and keep swiping. End the session only for a long
   lock or a real Premium / verification wall. The bot never clicks the dialog.
2. **Show the last session's result next to the status** — under the badge in the accounts list and at the top of
   the account page (e.g. "Fertig: max swipes", "Jaumo-Pause 147 s", "Gesperrt: like HTTP 403",
   "Fehler: …"). Today the reason is only in Logs, the account's session table, the session log and dashboard cards.
3. Rename the reason text: "swipe limit reached" -> "Jaumo-Pause N s (Bewertungs-Dialog)" when type is rate_app.

4. ✅ done: **Stop / remove from queue per account** — row menu "Stoppen" /
   "Aus Warteschlange entfernen", bulk "Stoppen", "Stoppen" on the account page; queued accounts show the badge
   "In Warteschlange". API: `POST /api/accounts/stop`, `POST /api/accounts/{id}/stop`. Tests pass.

Done 2026-10-03: (1) short Jaumo pauses (≤ 15 min) are waited out + a few random seconds, then swiping goes on;
a longer lock or 3 pauses in a row without a swipe end the session; never clicks the dialog; stop works while waiting.
(2) last session result under the status badge and on the account page; reasons shown in German.
(3) reasons "Jaumo lock: cards locked for N s (type)" / "Jaumo-Sperre … (Bewertungs-Dialog)". Plus the
"Über mich Text:" label on the account page.

Still open from the client confirmation (2026-10-03): nickname change (after signup or later, separate list),
automatic stats refresh (after every session + every 30 min), "Über mich Text:" label, photo-rejected display,
panel fully in German. "Emails" only if the client asks for it.

---

## 9. Tests

9.1 Add tests for: city radius (engine + stored coordinates), relationship dropdown values (§4.6),
    photo_url constant (§5), stats sync with fake `likes/in`, `visits/in`, `conversation/inbox`
    endpoints incl. cooldown and failures (§3), stdout log lines (§6), WebSocket payload patching (§7).
9.2 Fix the failing browser test `test_filters_search_paging` — test data is random (blocked account not
    guaranteed); make the "blocked" account deterministic.
9.3 Test helper: show the server traceback context in failures (the patch did not apply).
9.4 Run the **full suite** (engine, integration, resilience, browser) — all green before release.
    Status 2026-10-02: **90 passed** locally. Fixed on the way: parallel `signup_defaults` save (upsert), account page
    missed events between page load and WebSocket open (subscribe first), timing-dependent tests made order-independent;
    the server-log check now also fails on swallowed `[emit error]` lines and ignores Windows-only socket-reset noise.

---

## 10. Release (only after approval)

10.1 Summary of all changes for review.
10.2 Commit locally; **push only when you say so** (Coolify redeploys on push and restarts running work —
     the restart marks running sessions "interrupted"; better to push when no account is being created).
10.3 After deploy: check `/health`, open the panel, run 1 account, run a stats refresh on one account.

---

## 11. Decisions (answered 2026-10-02)

- **Q1 → Refresh per account** (one refresh at a time per account, 15 s cooldown). **"Refresh all"** is allowed and
  works through the accounts **one after another with a delay** between accounts (not all at once).
- **Q2 → keep Aktionen.**  **Q3 → both** (selected + all, with confirmation showing the cost).
- **Q4 → yes**, the messaging job also uses matches found by sync.
- **Q5 → default relationship value = FLIRT** (after the APK confirms the exact value).

## 11b. Open questions (original)

| # | Question | Default if no answer |
|---|---|---|
| Q1 | "Sync can be after 15 seconds and when admin clicks refresh": does this mean **(a)** only on Refresh, with a 15-second cooldown between refreshes of the same account, or **(b)** automatically once, 15 s after an account's session ends, plus the Refresh button? | (a) |
| Q2 | Keep the **Aktionen** card/tile (sent likes + dislikes + sent messages) next to the client's 7 numbers? | keep |
| Q3 | Bulk refresh for **all** accounts allowed, or only selected accounts? | both, with confirm + cost shown |
| Q4 | Should the messaging job also message **matches found by sync**? | yes |
| Q5 | Default relationship value for new accounts after the APK check: keep **FRIENDSHIP** (current) or switch to **FLIRT**? | keep FRIENDSHIP |

---

## 12. Backlog

- Translate the remaining pages (Konfigurationen, Proxys, Fotos, Logs, Einstellungen) fully to German.
- Stats history per day (chart of received likes/visitors over time) — needs repeated syncs, so only on request.
