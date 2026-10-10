"""Acceptance test of the whole Telegram brief (sections 1-15) as ONE scripted browser scenario (Edge via Playwright)
against the real server and the fake Telethon client, driven only through the panel:

  1. link two accounts (the second one with a two-step password), Online / Offline / Fehler, disconnect and reconnect
  2. import existing chats, receive a new incoming chat live, search / filter / select them
  3. build the three workflows of brief section 14 (voice file, image, text, pauses 60 / 30 / 10 / 0 and custom values)
  4. select chats by search, date and "all not processed", watch the counter, start
  5. watch the live status, pause, resume on the same spot, stop, restart; errors in some chats do not stop the run
  6. chat statuses and counters afterwards, dashboard, history with the per-chat audit, CSV export

Screenshots go to the folder named in E2E_SHOTS (default: a temporary folder). Any JS error, console error or failed
request (apart from the deliberate wrong code / wrong password) fails the test."""

import csv
import io
import json
import os
import re
from datetime import datetime
from pathlib import Path

import pytest

from conftest import ADMIN_PASS, jpeg_bytes, ok, wait_until
from test_telegram_accounts import ENV, PHONE, PHONE_2FA
from test_telegram_chats import Scenario, accounts, chats, dlg, wait_sync
from test_telegram_hardening import FAST, ctl
from test_telegram_runs import outbox
from test_telegram_workflows import ogg_opus

pw_sync = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.ui

API = "/api/telegram"
ACC = "#tab-telegram-accounts"
CHATS = "#tab-telegram-chats"
WF = "#tab-telegram-workflows"
RUNS = "#tab-telegram-runs"
LIVE = f"{RUNS} [data-live]"
DASH = "#tab-telegram-dashboard"
HIST = "#tab-telegram-history"
SHOTS = Path(os.environ["E2E_SHOTS"]) if os.environ.get("E2E_SHOTS") else None
NEW_ID = 555001          # the chat that writes to us while the panel is open


@pytest.fixture(scope="module")
def browser():
    with pw_sync.sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="msedge")
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"Edge is not available: {e}")
        yield b
        b.close()


# --- helpers ---------------------------------------------------------------------------------------

class Panel:
    """The logged-in admin panel in one browser page, with the problems it reports."""

    def __init__(self, browser, app, shots, lang="de", viewport=(1400, 1100)):
        self.ctx = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]}, locale="en-US")
        self.ctx.add_init_script(f"try{{localStorage.setItem('lang','{lang}')}}catch(e){{}}")
        self.page = self.ctx.new_page()
        self.problems = []
        self.shots = shots
        self.page.on("pageerror", lambda e: self.problems.append(f"JS error: {e}"))
        self.page.on("console", lambda m: m.type == "error" and self.problems.append(f"console: {m.text}"))
        self.page.on("response", lambda r: r.status >= 400 and self.problems.append(f"HTTP {r.status} {r.url}"))
        self.page.on("dialog", lambda d: d.accept())
        self.page.goto(app.url + "/#telegram-accounts")
        self.page.fill("input[name=username]", "admin")
        self.page.fill("input[name=password]", ADMIN_PASS)
        self.page.click("#login-form button[type=submit]")

    def shot(self, name):
        if self.shots:
            self.page.screenshot(path=str(self.shots / f"{name}.png"), full_page=True)

    def tab(self, name, ready):
        self.page.click(f"#tabs button[data-tab=telegram-{name}]")
        self.page.wait_for_selector(ready)

    def unexpected(self):
        """Problems other than the deliberate rejections (wrong code / wrong password -> HTTP 422)."""
        return [p for p in self.problems if "422" not in p]


def wait_text(page, selector, pattern, timeout=30000):
    page.wait_for_function("([sel, re]) => { const n = document.querySelector(sel); return !!n && new RegExp(re).test(n.textContent); }",
                           arg=[selector, pattern], timeout=timeout)


def account_row(page, phone):
    return page.locator(f"{ACC} tbody tr", has_text=phone)


def link_through_dialog(page, phone, *, api=None, password=None, wrong_first=False):
    """The 3-step dialog: phone (+ API access the first time) -> code -> password (two-step accounts only)."""
    page.click(f"{ACC} [data-act=add]")
    page.fill("#modal input[name=phone]", phone)
    if api:
        page.fill("#modal input[name=api_id]", str(api[0]))
        page.fill("#modal input[name=api_hash]", api[1])
    else:
        assert "API-Zugang gespeichert" in page.inner_text("#modal")      # remembered after the first account
        assert page.locator("#modal input[name=api_id]").count() == 0
    page.click("#modal [type=submit]")
    page.wait_for_selector("#modal input[name=code]")
    assert "Telegram hat einen Code gesendet" in page.inner_text("#modal")
    if wrong_first:
        page.fill("#modal input[name=code]", "00000")
        page.click("#modal [type=submit]")
        wait_text(page, "#modal .error", "Der Code ist falsch")
    page.fill("#modal input[name=code]", "12345")
    page.click("#modal [type=submit]")
    if password:
        page.wait_for_selector("#modal input[name=password]")
        assert "Zwei-Schritt" in page.inner_text("#modal")
        page.fill("#modal input[name=password]", "wrong")
        page.click("#modal [type=submit]")
        wait_text(page, "#modal .error", "Falsches Passwort")
        page.fill("#modal input[name=password]", password)
        page.click("#modal [type=submit]")
    page.wait_for_selector("#modal", state="hidden")


def build_workflow(panel, name, steps):
    """Create a workflow in the editor. steps: ("voice"|"image", bytes, mime, file name | "text", text, ...) + pause, where
    pause is "0"/"10"/"30"/"60" (preset) or (n, "s"|"min") (custom value)."""
    page = panel.page
    page.click(f"{WF} [data-act=new]")
    page.fill(f"{WF} [data-name]", name)
    for kind, payload, pause in steps:
        page.click(f"{WF} [data-act=add-toggle]")
        page.click(f"{WF} [data-add={kind}]")
        card = page.locator(f"{WF} .tg-step").last
        if kind == "text":
            card.locator("[data-content]").fill(payload)
        else:
            data, mime, fname = payload
            card.locator("[data-file]").set_input_files({"name": fname, "mimeType": mime, "buffer": data})
            card.locator("audio, img").first.wait_for()
        if isinstance(pause, tuple):
            card.locator("[data-pause]").select_option("custom")
            card.locator("[data-pause-n]").fill(str(pause[0]))
            card.locator("[data-pause-unit]").select_option(pause[1])
        else:
            card.locator("[data-pause]").select_option(pause)
    panel.shot(f"editor_{len(name)}")
    page.click(f"{WF} [data-act=save]")
    page.wait_for_selector("#toasts >> text=Ablauf gespeichert")
    page.click(f"{WF} [data-act=back]")
    page.wait_for_selector(f"{WF} .tg-wf-card:has-text('{name}')")


def seconds(page):
    m = re.search(r"\d+", page.inner_text(f"{LIVE} [data-count] .tg-count"))
    return int(m.group()) if m else None


def badge(page):
    return page.inner_text(f"{LIVE} [data-badge]").strip()


def runs(api, **params):
    return ok(api.get(f"{API}/runs", params=params))["items"]


def counts_line(page):
    return page.inner_text(f"{LIVE} [data-counts]")


def starts_of(rows, chat_id):
    return [r for r in rows if r["chat_id"] == chat_id]


def blocks(rows):
    """The chat ids of the outbox in order, consecutive repeats collapsed: a chat that is worked on twice in a row
    would show up twice, interleaved chats show up repeatedly."""
    out = []
    for r in rows:
        if not out or out[-1] != r["chat_id"]:
            out.append(r["chat_id"])
    return out


# --- the scenario ----------------------------------------------------------------------------------

def test_the_whole_brief_in_one_walk_through(browser, make_app, tmp_path):
    shots = SHOTS or tmp_path / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    scn = Scenario(tmp_path / "fake_tg")
    scn.dialogs([dlg(i, i, last_message=f"Nachricht {i}") for i in range(1, 9)])   # user1..user8, 1..8 days before 1 March
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir), TELEGRAM_AUTH_PROBE="0.4", **FAST)
    api = app.client()
    panel = Panel(browser, app, shots)
    page = panel.page

    # === §1 connect accounts: status, disconnect, reconnect ===============================================
    page.wait_for_selector(f"{ACC} .empty")
    assert "Noch kein Konto verbunden" in page.inner_text(ACC)
    panel.shot("01_accounts_empty")

    link_through_dialog(page, PHONE, api=(12345, "abcdef0123456789"), wrong_first=True)
    page.wait_for_selector(f"{ACC} tbody tr .badge.ok")
    wait_sync(api, PHONE)
    link_through_dialog(page, PHONE_2FA, password="secret")
    wait_sync(api, PHONE_2FA)
    accs = accounts(api)
    acc1, acc2 = accs[PHONE], accs[PHONE_2FA]
    assert acc1["status"] == acc2["status"] == "online"
    page.reload()
    page.wait_for_selector(f"{ACC} tbody tr:nth-child(2)")
    for phone in (PHONE, PHONE_2FA):
        row = account_row(page, phone)
        assert row.locator(".badge.ok").inner_text().strip() == "Online"
        assert row.locator("td").nth(2).inner_text().strip() == "8"            # imported chats of this account
        assert row.locator("[data-act=disconnect]").count() == 1
    assert "fake:" not in page.content() and "abcdef0123456789" not in page.content()   # secrets never reach the browser
    panel.shot("02_accounts_online")

    row2 = account_row(page, PHONE_2FA)
    row2.locator("[data-act=disconnect]").click()
    page.wait_for_selector(f"{ACC} tbody tr:has-text('{PHONE_2FA}') .badge.queued")
    assert account_row(page, PHONE_2FA).locator(".badge").inner_text().strip() == "Offline"
    assert accounts(api)[PHONE_2FA]["status"] == "offline" and account_row(page, PHONE).locator(".badge.ok").count() == 1
    panel.shot("03_account_offline")
    account_row(page, PHONE_2FA).locator("[data-act=connect]").click()
    page.wait_for_selector(f"{ACC} tbody tr:has-text('{PHONE_2FA}') .badge.ok")

    ctl(scn, revoke=[PHONE_2FA])                                              # Telegram ends the session -> Fehler, live
    page.wait_for_selector(f"{ACC} tbody tr:has-text('{PHONE_2FA}') .badge.bad", timeout=20000)
    assert "Fehler" in account_row(page, PHONE_2FA).inner_text()
    assert "Telegram hat diese Sitzung beendet" in account_row(page, PHONE_2FA).inner_text()
    assert account_row(page, PHONE).locator(".badge.ok").count() == 1          # the other account is not affected
    panel.shot("04_account_error")
    ctl(scn, revoke=[])
    account_row(page, PHONE_2FA).locator("[data-act=login]").click()
    page.click("#modal [type=submit]")
    page.wait_for_selector("#modal input[name=code]")
    page.fill("#modal input[name=code]", "12345")
    page.click("#modal [type=submit]")
    page.wait_for_selector("#modal input[name=password]")
    page.fill("#modal input[name=password]", "secret")
    page.click("#modal [type=submit]")
    page.wait_for_selector("#modal", state="hidden")
    page.wait_for_selector(f"{ACC} tbody tr:has-text('{PHONE_2FA}') .badge.ok")
    wait_sync(api, PHONE_2FA)

    # === §13 dashboard before any work: 16 chats, all not processed =========================================
    panel.tab("dashboard", f"{DASH} .kpi")
    tiles = dash_tiles(page)
    assert tiles["Alle Chats"][0] == "16" and "2 Konten, 2 online" in tiles["Alle Chats"][1]
    assert tiles["Noch nicht bearbeitet"][0] == "16" and tiles["Bereits bearbeitet"][0] == "0" and tiles["Chats mit Fehlern"][0] == "0"
    assert tiles["Laufender Ablauf"][0] == "Keiner" and tiles["Letzter Durchlauf"][0] == "—"
    panel.shot("05_dashboard_empty")

    # === §2 chats: stored fields, live new chat, search, filter, date, selection =============================
    panel.tab("chats", f"{CHATS} tbody tr[data-id]")
    page.select_option(f"{CHATS} [data-f=account]", str(acc1["id"]))
    wait_text(page, f"{CHATS} [data-showing]", "von 8$")
    first = page.locator(f"{CHATS} tbody tr", has_text="User1").first.inner_text()
    assert "@user1" in first and "1001" in first and "Nachricht 1" in first and "Noch nicht bearbeitet" in first
    for emoji in ("🟢", "🔵", "✅", "❌", "⏸"):
        assert emoji in page.inner_text(f"{CHATS} .tg-chips")
    scn.incoming(id=NEW_ID, access_hash=77, first_name="Livia", last_name="Neu", username="livia",
                 text="Hallo, ich bin neu!", to=PHONE)
    page.wait_for_selector(f"{CHATS} tbody tr:first-child:has-text('Livia')", timeout=15000)      # no reload
    assert "Hallo, ich bin neu!" in page.inner_text(f"{CHATS} tbody tr:first-child")
    wait_text(page, f"{CHATS} [data-showing]", "von 9$")
    assert chats(api, account_id=acc1["id"], q="livia")["items"][0]["chat_status"] == "pending"
    panel.shot("06_chats_live")

    page.fill(f"{CHATS} [data-f=q]", "@user5")
    wait_text(page, f"{CHATS} [data-showing]", "^1–1 von 1$")
    page.check(f"{CHATS} tbody tr:first-child input[data-sel]")
    assert page.inner_text(f"{CHATS} [data-count]") == "1 Chat ausgewählt"
    page.fill(f"{CHATS} [data-f=q]", "")
    wait_text(page, f"{CHATS} [data-showing]", "von 9$")
    assert page.inner_text(f"{CHATS} [data-count]") == "1 Chat ausgewählt"          # kept while the filter changes
    page.fill(f"{CHATS} [data-f=from]", "2026-02-26")
    page.fill(f"{CHATS} [data-f=to]", "2026-02-28")
    page.dispatch_event(f"{CHATS} [data-f=to]", "change")
    wait_text(page, f"{CHATS} [data-showing]", "^1–3 von 3$")                       # user1..user3 by date
    page.click(f"{CHATS} [data-act=reset]")
    wait_text(page, f"{CHATS} [data-showing]", "von 9$")
    page.click(f"{CHATS} [data-act=clear]")
    page.click(f"{CHATS} [data-act=select-pending]")
    page.wait_for_function("() => document.querySelector('#tab-telegram-chats [data-count]').textContent === '9 Chats ausgewählt'")
    page.click(f"{CHATS} [data-act=clear]")

    # === §3-5 + §14: three saved workflows with a voice file, an image and text ===============================
    voice = (ogg_opus(3.0), "audio/ogg", "memo.ogg")
    image = (jpeg_bytes(3, (80, 60)), "image/jpeg", "bild.jpg")
    panel.tab("workflows", f"{WF} h1")
    page.wait_for_selector(f"{WF} .empty")
    wf1, wf2, wf3, wf4 = ("Workflow 1 – Neukontakt", "Workflow 2 – Follow-up", "Workflow 3 – Ohne Pause", "Schnelltest")
    build_workflow(panel, wf1, [("voice", voice, "60"), ("text", "Hallo, schön dich zu sehen!", "30"), ("image", image, "10"),
                                ("voice", voice, "0")])
    build_workflow(panel, wf2, [("text", "Wie geht es dir? <b>kein Markup</b>", "10"), ("image", image, (20, "s")),
                                ("voice", voice, "0")])
    build_workflow(panel, wf3, [("voice", voice, "0"), ("text", "Ohne Pause", "0"), ("image", image, "0"), ("voice", voice, "0")])
    build_workflow(panel, wf4, [("text", "Kurz und schnell", (5, "s")), ("image", image, (1, "s")), ("voice", voice, "0")])
    assert page.locator(f"{WF} .tg-wf-card").count() == 4
    panel.shot("08_workflow_list")
    saved = {w["name"]: [(s["type"], s["pause_after"]) for s in w["steps"]] for w in ok(api.get(f"{API}/workflows"))}
    assert saved[wf1] == [("voice", 60), ("text", 30), ("image", 10), ("voice", 0)]          # brief §14 workflow 1
    assert saved[wf2] == [("text", 10), ("image", 20), ("voice", 0)]                          # custom 20 s
    assert saved[wf3] == [("voice", 0), ("text", 0), ("image", 0), ("voice", 0)]
    assert saved[wf4] == [("text", 5), ("image", 1), ("voice", 0)]
    # edit one step of a saved workflow (§3): open Follow-up, change the pause of the first step to 60 s, move to 2 min, save
    page.click(f"{WF} .tg-wf-card:has-text('Follow-up')")
    page.wait_for_selector(f"{WF} .tg-step")
    card = page.locator(f"{WF} .tg-step").first
    card.locator("[data-pause]").select_option("custom")
    card.locator("[data-pause-n]").fill("2")
    card.locator("[data-pause-unit]").select_option("min")
    page.click(f"{WF} [data-act=save]")
    page.wait_for_selector("#toasts >> text=Ablauf gespeichert")
    assert [s["pause_after"] for s in next(w for w in ok(api.get(f"{API}/workflows")) if w["name"] == wf2)["steps"]] == [120, 20, 0]
    page.click(f"{WF} [data-act=back]")

    # === §6 + §7 + §8: select chats and start workflow 3 (no pauses) ==========================================
    panel.tab("runs", f"{RUNS} [data-run-act=start]")
    page.select_option(f"{RUNS} [data-run-account]", str(acc1["id"]))
    page.wait_for_selector(f"{RUNS} tbody tr[data-id]")
    page.select_option(f"{RUNS} select[data-form=workflow]", label=wf3)
    assert "4 Schritte" in page.inner_text(f"{RUNS} [data-wf-info]")
    page.fill(f"{RUNS} [data-f=from]", "2026-02-26")
    page.fill(f"{RUNS} [data-f=to]", "2026-02-28")
    page.dispatch_event(f"{RUNS} [data-f=to]", "change")
    wait_text(page, f"{RUNS} [data-showing]", "^1–3 von 3$")
    page.check(f"{RUNS} [data-all]")
    assert page.inner_text(f"{RUNS} [data-start-count]") == "3 Chats ausgewählt"
    panel.shot("09_run_form")
    page.click(f"{RUNS} [data-run-act=start]")
    summary = page.inner_text("#modal")
    assert wf3 in summary and "3 Chats ausgewählt" in summary
    page.click("#modal [data-go]")
    page.wait_for_selector(LIVE)
    wait_text(page, f"{LIVE} [data-badge]", "FERTIG", timeout=40000)
    run_a = runs(api)[0]
    assert (run_a["total"], run_a["success"], run_a["errors"], run_a["skipped"]) == (3, 3, 0, 0)
    assert "Bearbeitet 3 / 3" in counts_line(page).replace("\n", " ") or "3 / 3" in counts_line(page)
    assert page.inner_text(f"{LIVE} [data-pct]") == "100 %"
    panel.shot("10_run_a_done")
    sent_a = outbox(scn, PHONE)
    assert len(sent_a) == 12 and len(blocks(sent_a)) == 3                                     # chat after chat, no interleaving
    for chat_id in blocks(sent_a):
        mine = starts_of(sent_a, chat_id)
        assert [m["type"] for m in mine] == ["voice", "text", "image", "voice"]
        assert mine[-1]["t"] - mine[0]["t"] < 3                                               # 0 s = the next message goes out directly
    assert sorted(blocks(sent_a)) == [1001, 1002, 1003]

    # === §11 errors in some chats: workflow "Schnelltest" over all not processed chats =========================
    (scn.dir / "send_errors.json").write_text(json.dumps({"1004": {"error": "UserPrivacyRestrictedError"},
                                                          "1005": {"error": "UserIsBlockedError"}}), encoding="utf-8")
    page.click(f"{LIVE} [data-run-act=new]")
    page.wait_for_selector(f"{RUNS} [data-run-act=start]")
    page.select_option(f"{RUNS} select[data-form=workflow]", label=wf4)
    page.click(f"{RUNS} [data-run-act=preset][data-status=pending]")
    wait_text(page, f"{RUNS} [data-start-count]", "^6 Chats ausgewählt")                       # 9 minus the 3 worked on
    assert "ca. 36 s" in page.inner_text(f"{RUNS} [data-start-est]")                           # 6 chats x (5 + 1 s pauses)
    # the three chats of the first run are not offered by "all not processed"
    assert {c["telegram_id"] for c in chats(api, account_id=acc1["id"], status="pending")["items"]} == \
        {"1004", "1005", "1006", "1007", "1008", str(NEW_ID)}
    page.click(f"{RUNS} [data-run-act=start]")
    page.click("#modal [data-go]")
    page.wait_for_selector(LIVE)
    run_b = runs(api)[0]["id"]

    # §10 live status: all values on screen
    assert badge(page) == "AKTIV" and "Schnelltest" in page.inner_text(f"{LIVE} [data-wf]")
    wait_text(page, f"{LIVE} [data-count]", r"in \d+ Sekunden")
    chat_name = page.inner_text(f"{LIVE} [data-chat] b")
    assert chat_name in ("Livia Neu", "User4", "User5", "User6", "User7", "User8")
    assert "Schritt 1 von 3" in page.inner_text(f"{LIVE} [data-step]") and "Text" in page.inner_text(f"{LIVE} [data-step]")
    assert "Bild" in page.inner_text(f"{LIVE} [data-next]")
    assert "Läuft" in page.inner_text("[data-run-badge]")
    first_count = seconds(page)
    page.wait_for_timeout(2500)
    assert seconds(page) <= first_count - 2                                                    # the countdown ticks
    panel.shot("11_run_b_live")

    # §9 Pause freezes everything, Fortsetzen continues on the same spot
    page.click(f"{LIVE} [data-run-act=pause]")
    wait_text(page, f"{LIVE} [data-badge]", "PAUSIERT")
    where = (page.inner_text(f"{LIVE} [data-chat] b"), page.inner_text(f"{LIVE} [data-step]"))
    frozen, sent_at_pause = seconds(page), len(outbox(scn, PHONE))
    assert "pausiert" in page.inner_text(f"{LIVE} [data-count]") and "Pausiert" in page.inner_text("[data-run-badge]")
    assert next(c for c in chats(api, account_id=acc1["id"])["items"] if c["display_name"] == where[0])["chat_status"] == "paused"
    panel.shot("12_run_b_paused")
    page.wait_for_timeout(3000)
    assert seconds(page) == frozen and len(outbox(scn, PHONE)) == sent_at_pause              # nothing is sent while paused
    page.click(f"{LIVE} [data-run-act=resume]")
    wait_text(page, f"{LIVE} [data-badge]", "AKTIV")
    assert (page.inner_text(f"{LIVE} [data-chat] b"), page.inner_text(f"{LIVE} [data-step]")) == where
    assert next(c for c in chats(api, account_id=acc1["id"])["items"] if c["display_name"] == where[0])["chat_status"] == "in_progress"
    page.wait_for_timeout(1500)
    assert seconds(page) <= frozen - 1                                                          # the rest of the pause, not a new one
    wait_text(page, f"{LIVE} [data-step]", "Bild", timeout=20000)                              # the same chat moves on to its image
    assert page.inner_text(f"{LIVE} [data-chat] b") == where[0]

    # progress moves on; errors in two chats do not stop the run
    wait_until(lambda: runs(api)[0]["processed"] >= 2, timeout=60, msg="two chats to be processed")
    run_now = runs(api)[0]
    assert run_now["status"] == "running" and page.inner_text(f"{LIVE} [data-badge]").strip() == "AKTIV"
    assert re.search(r"[1-9]\d? %", page.inner_text(f"{LIVE} [data-pct]"))
    wait_text(page, f"{LIVE} [data-counts]", "Bearbeitet\\s+[2-9] / 6")
    page.screenshot(path=str(shots / "13_run_b_progress.png"), full_page=True)

    # §9 Stoppen: rest skipped, nothing stays "in progress"
    page.click(f"{LIVE} [data-run-act=stop]")
    wait_text(page, f"{LIVE} [data-badge]", "GESTOPPT")
    b = ok(api.get(f"{API}/runs/{run_b}"))
    items = ok(api.get(f"{API}/runs/{run_b}/chats", params={"limit": 100}))["items"]
    assert b["status"] == "stopped" and len(items) == 6
    by_status = {s: sum(1 for i in items if i["status"] == s) for s in ("done", "error", "skipped", "pending", "running")}
    assert by_status["pending"] == by_status["running"] == 0
    assert by_status["done"] == b["success"] and by_status["error"] == b["errors"] and by_status["skipped"] == b["skipped"] >= 1
    assert b["processed"] + b["skipped"] <= 6
    states = {c["chat_status"] for c in chats(api, account_id=acc1["id"])["items"]}
    assert "in_progress" not in states
    page.wait_for_function("() => document.querySelector('[data-run-badge]').textContent === ''")
    assert seconds(page) is None
    panel.shot("14_run_b_stopped")

    # §9 Neustart: a new run over the same workflow and the same six chats
    sent_before_c = len(outbox(scn, PHONE))                                                    # the stopped run sends nothing more
    page.click(f"{LIVE} [data-run-act=restart]")
    wait_text(page, f"{LIVE} [data-badge]", "AKTIV")
    run_c_row = runs(api)[0]
    run_c = run_c_row["id"]
    assert run_c != run_b and run_c_row["total"] == 6 and run_c_row["workflow_name"] == wf4

    # while it runs: dashboard live card and the history show it, the badge is in the sidebar
    panel.tab("dashboard", f"{DASH} [data-dash-live]")
    assert dash_tiles(page)["Laufender Ablauf"][0] == wf4
    assert re.search(r"\d+ %", dash_tiles(page)["Fortschritt"][0])
    panel.shot("15_dashboard_live")
    panel.tab("history", f"{HIST} [data-hist-rows] tr[data-run]")
    assert "AKTIV" in page.inner_text(f"{HIST} tr[data-run='{run_c}']")
    panel.tab("runs", LIVE)
    assert badge(page) == "AKTIV"
    wait_text(page, f"{LIVE} [data-badge]", "FERTIG", timeout=120000)

    # === results of the finished run ==========================================================================
    c = ok(api.get(f"{API}/runs/{run_c}"))
    assert (c["status"], c["total"], c["success"], c["errors"], c["skipped"], c["processed"]) == ("done", 6, 4, 2, 0, 6)
    assert page.inner_text(f"{LIVE} [data-pct]") == "100 %"
    live_counts = counts_line(page).replace("\n", " ")
    assert "6 / 6" in live_counts and re.search(r"Erfolgreich\s*4", live_counts) and re.search(r"Fehler\s*2", live_counts)
    listing = page.inner_text(f"{RUNS} [data-list]")
    assert "Datenschutz-Einstellungen" in listing and "blockiert" in listing
    page.click(f"{RUNS} [data-errors-btn]")
    page.wait_for_function("() => document.querySelectorAll('#tab-telegram-runs [data-list] tr').length === 2")
    page.click(f"{RUNS} [data-errors-btn]")
    panel.shot("16_run_c_done")
    sent_c = outbox(scn, PHONE)[sent_before_c:]
    ok_chats = [i for i in ok(api.get(f"{API}/runs/{run_c}/chats", params={"limit": 100}))["items"] if i["status"] == "done"]
    assert len(sent_c) == 12 and len(blocks(sent_c)) == 4                                      # 4 chats x 3 messages, one at a time
    for chat_id in blocks(sent_c):
        mine = starts_of(sent_c, chat_id)
        assert [m["type"] for m in mine] == ["text", "image", "voice"]
        assert 4.4 <= mine[1]["t"] - mine[0]["t"] <= 9 and 0.8 <= mine[2]["t"] - mine[1]["t"] <= 4    # the pauses are 5 s and 1 s
    assert len(ok_chats) == 4 and not {1004, 1005} & set(blocks(sent_c))                      # nothing was sent to the failed chats

    # chat statuses and counters afterwards
    final = {x["telegram_id"]: x for x in chats(api, account_id=acc1["id"])["items"]}
    assert {t: x["chat_status"] for t, x in final.items()} == {
        "1001": "done", "1002": "done", "1003": "done", "1004": "error", "1005": "error",
        "1006": "done", "1007": "done", "1008": "done", str(NEW_ID): "done"}
    assert "privacy" in final["1004"]["error_reason"] and "blocked" in final["1005"]["error_reason"]
    assert final["1001"]["messages_sent"] == 4 and final["1004"]["messages_sent"] == 0 and final["1001"]["last_processed_at"]
    sent_total = len(outbox(scn, PHONE))
    assert sum(x["messages_sent"] for x in final.values()) == sent_total
    other = chats(api, account_id=acc2["id"])
    assert other["total"] == 8 and {x["chat_status"] for x in other["items"]} == {"pending"}   # the other account was not touched
    panel.tab("chats", f"{CHATS} tbody tr[data-id]")
    page.select_option(f"{CHATS} [data-f=account]", str(acc1["id"]))
    wait_text(page, f"{CHATS} [data-chips]", "Noch nicht bearbeitet\\s*0")
    chips = re.sub(r"\s+", " ", page.inner_text(f"{CHATS} .tg-chips"))
    assert re.search(r"Noch nicht bearbeitet 0", chips) and re.search(r"Bearbeitet 7", chips) and re.search(r"Fehler 2", chips)
    page.click(f"{CHATS} .tg-chip[data-status=error]")
    wait_text(page, f"{CHATS} [data-showing]", "^1–2 von 2$")
    assert "Datenschutz" in page.inner_text(f"{CHATS} tbody") and "blockiert" in page.inner_text(f"{CHATS} tbody")
    panel.shot("17_chats_after")

    # === §13 dashboard after the work =========================================================================
    all_runs = runs(api)
    assert len(all_runs) == 3
    panel.tab("dashboard", f"{DASH} .kpi")
    page.select_option(f"{DASH} [data-dash-account]", str(acc1["id"]))
    wait_text(page, f"{DASH} .kpi-value", "^9$")
    tiles = dash_tiles(page)
    assert tiles["Alle Chats"][0] == "9" and tiles["Noch nicht bearbeitet"][0] == "0"
    assert tiles["Bereits bearbeitet"][0] == "7" and tiles["Chats mit Fehlern"][0] == "2"
    assert tiles["Laufender Ablauf"][0] == "Keiner"
    assert tiles["Erfolgreiche Sendungen"][0] == str(sum(r["success"] for r in all_runs))
    assert tiles["Fehlgeschlagene Sendungen"][0] == str(sum(r["errors"] for r in all_runs))
    assert "FERTIG" in tiles["Letzter Durchlauf"][1] and "4 erfolgreich" in tiles["Letzter Durchlauf"][1]
    assert tiles["Aktueller Chat"][0] == "—" and tiles["Fortschritt"][0] == "—"
    assert "Es läuft gerade kein Durchlauf" in page.inner_text(DASH)
    panel.shot("18_dashboard_after")
    page.select_option(f"{DASH} [data-dash-account]", str(acc2["id"]))
    wait_text(page, f"{DASH} .kpi-value", "^8$")
    assert dash_tiles(page)["Erfolgreiche Sendungen"][0] == "0"

    # === §12 history: runs, columns, per-chat audit, CSV ======================================================
    panel.tab("history", f"{HIST} [data-hist-rows] tr[data-run]")
    rows = page.locator(f"{HIST} [data-hist-rows] tr[data-run]")
    page.wait_for_function("() => document.querySelectorAll('#tab-telegram-history [data-hist-rows] tr[data-run]').length === 3")
    assert [rows.nth(i).get_attribute("data-run") for i in range(3)] == [str(run_c), str(run_b), str(run_a["id"])]
    for h in ("Start", "Ende", "Ablauf", "Gewählt", "Erfolgreich", "Fehler", "Abgebrochen", "Dauer"):
        assert h.lower() in page.inner_text(f"{HIST} thead").lower()
    cells_c = rows.nth(0).locator("td").all_inner_texts()
    assert cells_c[2].startswith(wf4) and cells_c[3:6] == ["6", "4", "2"] and cells_c[8] == "FERTIG" and re.search(r"\d+ s|Min", cells_c[7])
    cells_b = rows.nth(1).locator("td").all_inner_texts()
    assert cells_b[8] == "GESTOPPT" and cells_b[3] == "6" and cells_b[6] == str(b["skipped"])
    assert rows.nth(2).locator("td").all_inner_texts()[3:6] == ["3", "3", "0"] and wf3 in rows.nth(2).inner_text()
    assert re.search(r"\d\d\.\d\d\.", rows.nth(0).locator("td").nth(0).inner_text())          # start time is shown
    panel.shot("19_history_list")
    page.click(f"{HIST} tr[data-run='{run_c}']")
    page.wait_for_selector(f"{HIST} [data-detail-rows] tr")
    detail = page.locator(f"{HIST} [data-detail-rows] tr")
    assert detail.count() == 6
    texts = detail.all_inner_texts()
    assert sum("Fertig" in t for t in texts) == 4 and sum("Fehler" in t for t in texts) == 2
    assert all(re.search(r"\d\d:\d\d:\d\d", t) for t in texts)                                # when each chat was handled
    assert any("Datenschutz-Einstellungen" in t for t in texts) and any("Der Nutzer hat dieses Konto blockiert" in t for t in texts)
    assert sum("3 / 3" in t for t in texts) == 4
    panel.shot("20_history_detail")
    detail_csv = page.evaluate("href => fetch(href).then(r => r.text())", page.get_attribute(f"{HIST} [data-detail-head] a[download]", "href"))
    parsed = list(csv.reader(io.StringIO(detail_csv.lstrip("\ufeff"))))
    assert len(parsed) == 7 and "error_reason" in parsed[0]
    assert sum(1 for r in parsed[1:] if r[parsed[0].index("result")] == "error") == 2
    assert any("privacy settings" in r[parsed[0].index("error_reason")] for r in parsed[1:])
    page.click(f"{HIST} [data-hist-act=back]")
    page.wait_for_selector(f"{HIST} [data-hist-rows] tr[data-run]")
    export = page.get_attribute(f"{HIST} [data-hist-export]", "href")
    overall = list(csv.reader(io.StringIO(page.evaluate("href => fetch(href).then(r => r.text())", export).lstrip("\ufeff"))))
    assert len(overall) == 1 + 3 and {r[0] for r in overall[1:]} == {str(run_c), str(run_b), str(run_a["id"])}
    page.select_option(f"{HIST} [data-hf=status]", "stopped")
    page.wait_for_function("() => document.querySelectorAll('#tab-telegram-history [data-hist-rows] tr[data-run]').length === 1")
    page.click(f"{HIST} [data-hist-act=reset]")

    # a run that has been worked on stays untouched by cleaning up history (chat statuses stay)
    page.click(f"{HIST} tr[data-run='{run_a['id']}'] [data-hist-act=delete]")
    page.wait_for_function("() => document.querySelectorAll('#tab-telegram-history [data-hist-rows] tr[data-run]').length === 2")
    assert {x["chat_status"] for x in chats(api, account_id=acc1["id"], q="user1")["items"]} == {"done"}

    # === English: the same screens, no German left over =======================================================
    page.click("#top-user")
    page.click("#menu-lang")
    page.wait_for_selector(f"{HIST} :text('History')")
    panel.tab("dashboard", f"{DASH} .kpi")
    en = dash_tiles(page)
    assert {"All chats", "Not processed yet", "Already processed", "Chats with errors", "Running workflow",
            "Successful sends", "Failed sends", "Last run", "Active chat", "Progress"} <= set(en)
    panel.shot("21_dashboard_en")
    panel.tab("runs", f"{RUNS} [data-run-act=start], {LIVE}")
    assert not re.search(r"\b(Ablauf wählen|Chats ausgewählt|Konten)\b", page.inner_text(RUNS))

    # the phone layout keeps working after a whole day of work
    page.set_viewport_size({"width": 390, "height": 844})
    for name, sel in (("accounts", ACC), ("chats", CHATS), ("workflows", WF), ("runs", RUNS), ("history", HIST), ("dashboard", DASH)):
        page.evaluate(f"location.hash = '#telegram-{name}'")
        page.wait_for_selector(f"{sel} h1")
        page.wait_for_timeout(400)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), f"{name} overflows at phone width"
    panel.shot("22_phone")

    assert panel.unexpected() == [], panel.unexpected()
    assert len([p for p in panel.problems if p.startswith("HTTP")]) == 2, panel.problems          # exactly the wrong code and the wrong password
    panel.ctx.close()


def dash_tiles(page):
    """The Dashboard tiles as {label: (value, foot)}."""
    return page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('#tab-telegram-dashboard .kpi')].map(k =>
        [k.querySelector('.kpi-label').textContent.trim(), [k.querySelector('.kpi-value').textContent.trim(), k.querySelector('.kpi-foot').textContent.trim()]]))""")
