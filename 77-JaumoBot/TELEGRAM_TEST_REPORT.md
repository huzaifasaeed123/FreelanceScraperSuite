# Telegram Module - Test Report

For the project owner. All automated tests ran against a fake Telegram client (`tests/fake_telegram.py`), never against real Telegram. What that means is in "Known limitations" and in the manual checklist at the end.

## 1. Result in numbers

Final full run of `python -m pytest tests -q` on the finished state: **1389 passed, 5 skipped, 0 failed (46 minutes)**

| | Count |
|---|---|
| Tests before Telegram testing began | 178 passed (all Jaumo + early Telegram phases) |
| Tests at the end | 1394 collected: 1389 passed |
| Skipped | 5: 3 are parametrised cases that do not apply (the CSV export has no paging parameters), 2 need a real `ffmpeg`, which is not installed on the test machine |
| Duration of the full suite | about 46 minutes (browser tests with Edge, 10,000-chat and 50 MB upload cases) |

One test, `test_rapid_pause_resume_cycles_never_lose_or_repeat_a_message`, once failed with a 40 s timeout while the machine was heavily loaded by other jobs. It passed in every later run (alone and in the full suite). It is timing-sensitive; a wider timeout would make it more robust.

## 2. What was tested, per area

| Area | File(s) | What it covers |
|---|---|---|
| Contract and auth | `test_telegram_contract.py` (about 600 cases) | All 45 Telegram routes, `/api/modules` and the WebSocket refuse anonymous callers (4 cookie variants, with and without body). 404 for unknown ids, 422 for bad ids and malformed bodies (about 230), exact length limits, run state machine refusals (409), paging disjoint and complete for every sort and order, filters, date handling, CSV shape, same fields on every route, no secrets in any response, error responses are JSON. |
| Data integrity and scale | `test_telegram_integrity_scale.py` | Deleting accounts, workflows, runs leaves no orphans (foreign key check clean, also with 1,500 runs). No duplicate chats across repeated syncs, live messages during a sync, same contact on two accounts. Migration from older tables, migrating twice. 10,000 dialogs imported (about 5 s); list, search, sort and bulk actions on 10,000 chats; a 1,000-chat run with exact counters and bounded memory; a 500-run history; API stays responsive during a busy run. |
| Run engine matrix | `test_telegram_run_matrix.py` (78 cases), `test_telegram_runs.py` | Pause and resume at every position, remaining pause time after resume, rapid and concurrent controls, stop at six positions, stop then restart, restart recovery (5 positions, killed and graceful, two restarts), retry 1 to 5, "next" mode, FloodWait, PeerFlood, revoked session, dropped connection, parallel accounts, one run per account, changes to workflow/media/account during a run, no leaked tasks, clean shutdown. |
| Security | `test_telegram_security.py`, `test_telegram_security_ui.py` (about 230 cases) | No api_hash/session in any route, error, WebSocket frame or log; forged, expired and tampered tokens; WebSocket auth; SQL injection payloads in search and filters (sort is a whitelist, LIKE wildcards match literally); spoofed and damaged uploads, dangerous file names, path traversal (33 encodings), pixel-bomb PNG, header injection; ffmpeg errors do not leak paths; CSV formula injection neutralised; HTML/script payloads in every user-controlled field are inert on every tab in German and English (checked in a real browser). |
| Acceptance end-to-end | `test_telegram_e2e.py` | One scripted Edge/Playwright walk through brief sections 1 to 15 (about 63 s, 22 screenshots): two accounts, 2FA, chats, workflows with real OGG/JPEG files, selection, a run with errors, pause, resume, stop, restart, dashboard, history, CSV export, English labels, no horizontal overflow at 390 px. |
| UI quality | `test_telegram_ui_quality.py` (40 cases) plus the UI test files of each phase | Fit at 390, 768 and 1300 px in German/English and dark/light; empty states; hostile text; thousands separators; 5,000 chats; dialogs close with Escape and take focus; keyboard reorder; unsaved-changes prompt; no leaked sockets or timers when switching tabs during a run; reload during a run; error and slow-server messages; language and theme switch in place; contrast. |
| Gaps found by the review | `test_telegram_gaps.py` and additions to the UI tests | Unsupported step types are refused (video, document, file, sticker, audio, gif, poll); replacing a voice file in a step releases the old file; long pauses (150 s, 2 h, 24 h); a stopped run reports aborted chats, duration and CSV columns; the retry option in the start form; the first-contact date in the chats table. |
| Regression | all Jaumo tests | Unchanged and green. No existing Jaumo test was edited (only `tests/conftest.py` got a small graceful-stop helper). |

## 3. Bugs found and fixed

| # | Severity | Bug | Fix |
|---|---|---|---|
| 1 | Major | A long unbroken workflow name or account label pushed the live run panel and the history detail out of the page on a phone (page 630 px wide in a 390 px window). | Names wrap in the live panel, history detail and history table. |
| 2 | Minor | Ids or offsets of 2^63 or more gave HTTP 500 on about 20 routes. | Global handler answers 422. |
| 3 | Minor | NaN, Infinity or a lone surrogate in a JSON body gave 500 on every write route (also on Jaumo routes). | The validation error no longer echoes the bad input, so it can be sent as 422. |
| 4 | Minor | A lone surrogate inside an accepted text field gave 500 when saving. | Rejected with 422 (settings, account label, chat notes, workflow name and text). |
| 5 | Minor | Negative or huge API ID accepted; API hash unlimited (12 MB accepted). | API ID must be 1 to 2^31-1, API hash at most 64 characters. |
| 6 | Minor | Account label unbounded; workflows with unlimited steps. | Label 60 characters, workflow 100 steps. |
| 7 | Minor | A converted voice file could grow beyond the 50 MB limit (the limit was only checked on the upload). | Checked after conversion (413). |
| 8 | Minor | Dates at the edge of the year range crashed the date filters. | 422. |
| 9 | Minor | `/openapi.json` was readable without login. | Switched off. |
| 10 | Minor | Chats stored before the search column existed could not be found by search, and name sorting was arbitrary, until the next sync. | Backfill at startup. |
| 11 | Minor | A chat held by a paused run was shown as "In Bearbeitung". | The run waits at its pause point before starting the next chat. |
| 12 | Minor | Stopping a run left a chat that received nothing as "Pausiert" with a processing date, so "all unprocessed" no longer selected it. | A chat without any message goes back to "Noch nicht bearbeitet". |
| 13 | Minor | A chat row deleted from the database during a run ended the whole run with an error. | That chat becomes an error, the run continues. |
| 14 | Minor | The Konten, Chats, Abläufe and Verlauf tabs were blank while the server answered slowly. | Title and "Wird geladen ..." appear at once. |
| 15 | Minor | Confirmation, chat edit and unused-files dialogs did not take keyboard focus; Tab left an open dialog. | Shared `openModal` focuses the first control, keeps Tab inside, returns focus on close. This also changes Jaumo dialogs (all Jaumo tests pass). |
| 16 | Minor | Light theme: secondary text had a contrast of 2.88:1. | Colour changed from #8a94a6 to #5f6a7d (shared token, affects Jaumo pages too). |
| 17 | Cosmetic | Dashboard said "1 Konten" / "1 accounts". | Singular forms. |
| 18 | Cosmetic | The chat name column wrapped to three lines at tablet width. | Minimum width. |

## 4. Open bugs and gaps (honest list)

- **Browser Back does not move between panel tabs, and not from run details back to the list.** The shared shell uses `history.replaceState` on purpose; changing it would change Jaumo navigation as well. Reload on the current address returns to the same tab (tested). Not fixed.
- **Nothing was tested against real Telegram or real ffmpeg.** See limitations.
- The panel briefly shows the previous content of a tab (old rows and chips) until its data is reloaded. Cosmetic.
- "Failed sends" on the dashboard sums the failed chats over all runs. A stopped run and its restart that both hit the same two error chats count four. This matches the documented meaning ("chats that ended in an error") but may surprise.
- Runs work the chats in ascending chat id order, not by last contact.
- The WebSocket handshake has no Origin check; it relies on the SameSite=lax login cookie. Tokens are stateless, so logging out does not invalidate a stolen cookie. These are properties of the shared Jaumo shell.
- The API ID is returned by `/settings` and `/accounts` (only API hash and session string are hidden).
- A search text consisting of a NUL character matches every chat. Harmless.
- Pydantic validation errors have a list as `detail`, hand-raised errors a string. The panel handles both.
- A phone number written as `0049...` is normalised to `+0049...` (no international-prefix handling).
- Stopping a run before a chat's first message resets that chat to "Noch nicht bearbeitet", so it no longer remembers a "Bearbeitet" status from an earlier run.
- Stop or pause during the last send of the last chat ends the run as "Fertig" (consistent, accepted).

## 5. Coverage of brief sections 1 to 15

| § | Topic | Evidence |
|---|---|---|
| 1 | Connect accounts, status, disconnect/reconnect | `test_telegram_accounts.py` (2FA, wrong code/password, revoked, restart reconnect); E2E walk (two accounts, Online/Offline/Fehler); hardening tests (drop, reconnect); contract tests for login steps. Real login: manual checklist. |
| 2 | Chats: name, username, id, last message, first/last contact, status, search, filter | `test_telegram_chats.py`, `test_telegram_chats_ui.py` (first-contact date column), integrity/scale (10,000 chats, no duplicates), contract (search, filters, paging); E2E (live new chat, search, date filter, chips). |
| 3 | Workflow with steps; edit, move, delete, replace; other message types | `test_telegram_workflows.py`, `_ui.py`; gaps tests (voice file replaced and old file released; video/file/sticker etc. deliberately refused). Only text, image and voice exist by decision. |
| 4 | Individual pauses, 0 s to free input | Workflow tests and E2E (60/30/10/0 s, 20 s, 5 s, 1 s, 2 min); gaps tests (150 s, 2 h, 24 h counted in seconds and frozen on pause); run timing checked with small pauses only. |
| 5 | Editor, drag and drop, arrows | Workflow UI tests (real mouse drag, arrows between cards), UI-quality keyboard reorder, unsaved-changes prompt, editor with 30 steps at three widths. |
| 6 | Select chats: single, many, all unprocessed, filters, count | Chats UI test (1,300 chats, "1.300 Chats ausgewählt"), UI-quality (5,000 chats, selection across pages), E2E (date-range selection, "9 Chats ausgewählt"). |
| 7 | START, chats one after another, voice as real voice message | Run tests and run matrix; E2E outbox shows strict order and no interleaving. Voice conversion only with a stand-in ffmpeg; the voice flag is not checked against real Telegram. |
| 8 | No parallel processing | Run matrix (one run per account, sequential chats, two accounts in parallel), E2E outbox order. |
| 9 | Pause, resume, stop, restart, current chat visible | Run matrix (all positions), E2E (countdown freezes, resume at same step, stop, restart), UI-quality (live panel at three widths, reload during a run). |
| 10 | Live status | `test_telegram_runs_ui.py`, E2E (chat, step n of m, next step, countdown, progress, counters), UI-quality (no leaked sockets). |
| 11 | Error handling, continue or retry | Run matrix (retry 1 to 5, next mode, per-step budget, FloodWait, PeerFlood, deleted chat row); retry option chosen in the start form and shown in the confirmation (UI test); E2E (run continues past two failing chats with German reasons). Real Telegram error types: manual. |
| 12 | History | `test_telegram_history.py`, `_ui.py`, gaps tests (aborted chats, duration, CSV columns for a stopped run), E2E (list, detail, CSV, filters, delete keeps chat status). Audit trail after a hard server kill is covered only through the chat/run status checks of the matrix. |
| 13 | Dashboard values | History tests (`/stats`), UI-quality (follows a live run), E2E (before, during, after; cross-checked against the API). |
| 14 | Several saved workflows | Workflow tests and E2E (four workflows incl. the 60/30/10/0 s example). |
| 15 | Overall visibility | E2E screenshots (dashboard, live panel, history), UI-quality (phone/tablet/desktop, both languages and themes), contrast test. |

## 6. Known limitations

- **Real Telegram untouched.** Code delivery, rate limits, FloodWait with real durations, PeerFlood, `iter_dialogs` on real accounts, min-user access hashes, session reuse after restart with live accounts: only the fake client was used.
- **Real ffmpeg untouched.** Conversion of mp3/m4a/wav to OGG/Opus was tested with a stand-in. The 300 s ffmpeg timeout and a real bomb file were not run. The Docker image with ffmpeg was not built here.
- **Browser coverage is Edge only** (Playwright). Firefox and Safari were not tried.
- Run timing was tested with pauses of a few seconds; long pauses are verified as stored and counted down, not waited out.
- Sending first-contact messages from user accounts can get accounts limited by Telegram. The panel warns, but the safe pause length is the operator's choice.

## 7. MANUAL CHECKLIST for the owner (real accounts needed)

Use your own test accounts and 2 or 3 chats with people who know about it.

1. **API credentials.** Create API ID and API hash at https://my.telegram.org and enter them in Konten, "Telegram-Konto verbinden".
2. **Link a real account.** Phone number with country code, enter the code (Telegram app or SMS), enter the cloud password if the account has one. Expect Online. Link a second account and check that API ID/hash were remembered.
3. **Restart the server** (stop and start it) with the accounts linked. Expect them to reconnect by themselves. Disconnect one with "Trennen", restart, and check it stays Offline.
4. **Sync chats.** Check that your existing private chats appear with the right names, usernames and last message. Send yourself a new message from another phone and watch the chat appear or update live.
5. **Build the example workflow:** voice memo, 60 s, text, 30 s, image, 10 s, voice memo. Upload a voice file as `.ogg` and one as `.mp3`. Make sure ffmpeg exists in your deployment (Docker image has it) and that the mp3 arrives as a real voice bubble with the wave form, not as an audio file.
6. **Run to 2 or 3 own test chats.** Confirm: order of messages, pauses as set, chats strictly one after another, counters and statuses in the panel, entries in Verlauf, CSV export.
7. **Pause, resume, stop, restart** during a pause and during a send. Check that nothing is sent while paused and that resume continues at the right step with the remaining time.
8. **Errors.** Add a chat that blocked the account or has privacy settings that refuse messages. Expect an error with a reason for that chat and the run continuing.
9. **FloodWait.** Run with 0 s pauses over many chats (only with a test account you can afford to limit) until Telegram answers with a wait. Expect the countdown "Wartezeit von Telegram" and an automatic continue. If PeerFlood appears, expect the red banner.
10. **Connection loss.** Disconnect the network of the server for a minute during a run. Expect status "Verbindet", the run paused with the reason, and a reconnect (with "auto resume" on the run continues by itself).
11. **Revoked session.** In Telegram, Settings, Devices, end the session of the panel. Expect "Fehler" and a working "Anmelden".
12. **Restart during a run.** Restart the server in the middle of a run. Expect the run to come back paused with "Server neu gestartet" and to continue at the right chat and step after "Fortsetzen". No message may be sent twice.
13. **Long run overnight.** Start a run over many chats with realistic pauses and check in the morning: finished or still running, no stuck chat "In Bearbeitung", server memory stable, history complete.
14. **Phone.** Open the panel on your phone and check the live panel and the START bar.
