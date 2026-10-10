"""Browser walk-through of the Telegram Dashboard and Verlauf tabs (Edge via Playwright) against the real server and the
fake Telethon client: every number of the Dashboard, the live card following a run over the WebSocket, the chart, the
filters, detail view, CSV links, cleanup and delete of the Verlauf tab, German and English, phone width.
Any JS error, console error or failed request fails the test."""

import re

import pytest

from conftest import ADMIN_PASS, ok, wait_until
from test_telegram_accounts import ENV
from test_telegram_chats import Scenario, chats, dlg, link_synced
from test_telegram_history import add_account, add_chat, add_run, age, on_day
from test_telegram_runs import make_workflow, text_step
from test_telegram_runs_ui import COUNTERS, browser  # noqa: F401  (browser: pytest fixture, used by name)

pw_sync = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.ui

API = "/api/telegram"
DASH = "#tab-telegram-dashboard"
HIST = "#tab-telegram-history"
HOSTILE = '<img src=x onerror="window.__xss=1">'


@pytest.fixture
def ui(browser, make_app, tmp_path):  # noqa: F811
    """Account A with four chats (one with a hostile name) and the crafted runs
    R1 done (2 ok, 1 error: blocked) two days ago, R2 stopped (1 ok, 2 aborted) yesterday, plus account B with R3 (1 ok)."""
    scn = Scenario(tmp_path / "fake_tg")
    items = [dlg(i, i) for i in range(1, 5)]
    items[1].update(first_name=HOSTILE, username="xss")
    scn.dialogs(items)
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir), TELEGRAM_RETRY_WAIT="0.3")
    api = app.client()
    acc = link_synced(api)
    a = [c["id"] for c in sorted(chats(api, account_id=acc["id"])["items"], key=lambda c: c["telegram_id"])]
    ok(api.post(f"{API}/chats/bulk-status", json={"ids": a[:2], "status": "done"}))
    ok(api.post(f"{API}/chats/bulk-status", json={"ids": [a[2]], "status": "error"}))
    b_acc = add_account(app)
    b = [add_chat(app, b_acc, 1, "done", 2), add_chat(app, b_acc, 2)]
    r1 = add_run(app, acc["id"], [(a[0], "done", ""), (a[1], "done", ""), (a[2], "error", "The user has blocked this account")],
                 ended=on_day(2), seconds=95, name="Neukontakt")
    r2 = add_run(app, acc["id"], [(a[3], "done", ""), (a[0], "skipped", ""), (a[1], "skipped", "")], status="stopped",
                 ended=on_day(1), seconds=30, name="Follow-up")
    r3 = add_run(app, b_acc, [(b[0], "done", "")], ended=on_day(0), seconds=5, name="Neukontakt")
    contexts = []

    def open_page(lang="de", viewport=(1400, 1000), hash_="#telegram-dashboard"):
        ctx = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]}, locale="en-US")
        ctx.add_init_script(f"try{{localStorage.setItem('lang','{lang}')}}catch(e){{}}")
        ctx.add_init_script(COUNTERS)
        page = ctx.new_page()
        problems = []
        page.on("pageerror", lambda e: problems.append(f"JS error: {e}"))
        page.on("console", lambda m: m.type == "error" and problems.append(f"console: {m.text}"))
        page.on("response", lambda r: r.status >= 400 and problems.append(f"HTTP {r.status} {r.url}"))
        page.on("dialog", lambda d: d.accept())
        page.goto(app.url + "/" + hash_)
        page.fill("input[name=username]", "admin")
        page.fill("input[name=password]", ADMIN_PASS)
        page.click("#login-form button[type=submit]")
        contexts.append(ctx)
        return page, problems

    yield app, api, scn, acc, {"runs": (r1, r2, r3), "a": a, "b_acc": b_acc}, open_page
    for ctx in contexts:
        ctx.close()


def tiles(page):
    """The Dashboard tiles as {label: (value, foot)}."""
    return page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('#tab-telegram-dashboard .kpi')].map(k =>
        [k.querySelector('.kpi-label').textContent.trim(), [k.querySelector('.kpi-value').textContent.trim(), k.querySelector('.kpi-foot').textContent.trim()]]))""")


def dash_ready(page):
    page.wait_for_selector(f"{DASH} .kpi")


def hist_rows(page):
    page.wait_for_selector(f"{HIST} [data-hist-rows] tr")
    return page.locator(f"{HIST} [data-hist-rows] tr[data-run]").count()


def no_overflow(page):
    return page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


# --- Dashboard ---------------------------------------------------------------------------------------------

def test_dashboard_shows_every_number_in_german(ui):
    app, api, scn, acc, x, open_page = ui
    page, problems = open_page()
    dash_ready(page)
    t = tiles(page)
    assert t["Alle Chats"][0] == "6" and "2 Konten, 1 online" in t["Alle Chats"][1]
    assert t["Noch nicht bearbeitet"][0] == "2" and t["Bereits bearbeitet"][0] == "3" and t["Chats mit Fehlern"][0] == "1"
    assert t["Laufender Ablauf"][0] == "Keiner"
    assert t["Erfolgreiche Sendungen"][0] == "4" and t["Fehlgeschlagene Sendungen"][0] == "1"
    assert t["Letzter Durchlauf"][0] != "—" and "FERTIG" in t["Letzter Durchlauf"][1] and "1 erfolgreich" in t["Letzter Durchlauf"][1]
    assert t["Aktueller Chat"][0] == "—" and t["Fortschritt"][0] == "—"
    assert "Es läuft gerade kein Durchlauf" in page.inner_text(DASH)
    assert "Neukontakt" in page.inner_text(f"{DASH} .tg-sum")
    assert "5 s" in page.inner_text(f"{DASH} .tg-sum")

    # chart: one stacked column per day with data (successful, plus failed on the day of R1)
    assert page.locator(f"{DASH} [data-dash-chart] .bar").count() == 4 and page.locator(f"{DASH} [data-dash-chart] .bar-fail").count() == 1
    assert page.locator(f"{DASH} [data-dash-chart] .col").count() == 14
    page.hover(f"{DASH} [data-dash-chart] .col:last-child")
    assert "Erfolgreich" in page.inner_text("#chart-tip") and page.is_visible("#chart-tip")
    page.select_option(f"{DASH} [data-dash-days]", "7")
    page.wait_for_function("() => document.querySelectorAll('#tab-telegram-dashboard [data-dash-chart] .col').length === 7")
    assert no_overflow(page) and problems == []


def test_dashboard_in_english_and_per_account(ui):
    app, api, scn, acc, x, open_page = ui
    page, problems = open_page(lang="en")
    dash_ready(page)
    t = tiles(page)
    assert t["All chats"][0] == "6" and t["Successful sends"][0] == "4" and t["Running workflow"][0] == "None"
    assert "2 accounts, 1 online" in t["All chats"][1] and "FINISHED" in t["Last run"][1]
    assert "No run is active right now" in page.inner_text(DASH)

    page.select_option(f"{DASH} [data-dash-account]", str(acc["id"]))
    page.wait_for_function("() => document.querySelector('#tab-telegram-dashboard .kpi-value').textContent.trim() === '4'")
    t = tiles(page)
    assert (t["Successful sends"][0], t["Failed sends"][0], t["Already processed"][0]) == ("3", "1", "2")
    assert "STOPPED" in t["Last run"][1] and "2 aborted" in t["Last run"][1]
    page.select_option(f"{DASH} [data-dash-account]", str(x["b_acc"]))
    page.wait_for_function("() => document.querySelector('#tab-telegram-dashboard .kpi-value').textContent.trim() === '2'")
    assert tiles(page)["Successful sends"][0] == "1"
    page.select_option(f"{DASH} [data-dash-account]", "")
    page.wait_for_function("() => document.querySelector('#tab-telegram-dashboard .kpi-value').textContent.trim() === '6'")
    assert problems == []


def test_live_card_follows_a_run_over_the_websocket(ui):
    app, api, scn, acc, x, open_page = ui
    page, problems = open_page()
    dash_ready(page)
    wf = make_workflow(api, [text_step("eins", 30), text_step("zwei", 0)], name="Langsam")
    ids = [c["id"] for c in chats(api, account_id=acc["id"], status="pending")["items"]]
    assert page.locator(f"{DASH} [data-dash-live]").count() == 0
    run = ok(api.post(f"{API}/runs", json={"account_id": acc["id"], "workflow_id": wf["id"], "chat_ids": ids}))

    page.wait_for_selector(f"{DASH} [data-dash-live]")      # no reload: the event brought it
    live = f"{DASH} [data-dash-live]"
    assert "Langsam" in page.inner_text(live) and f"#{run['id']}" in page.inner_text(live) and "AKTIV" in page.inner_text(live)
    page.wait_for_function("() => /User4/.test(document.querySelector('#tab-telegram-dashboard [data-dash-live]').textContent)")
    page.wait_for_function("() => document.querySelectorAll('#tab-telegram-dashboard .kpi-value')[4].textContent.trim() === 'Langsam'")
    t = tiles(page)
    assert "Durchlauf #" in t["Laufender Ablauf"][1] and t["Aktueller Chat"][0] == "User4" and t["Fortschritt"][0] == "0 %"
    assert "Schritt 1/2" in t["Aktueller Chat"][1]

    ok(api.post(f"{API}/runs/{run['id']}/stop"))
    page.wait_for_function("() => /Es läuft gerade kein Durchlauf/.test(document.querySelector('#tab-telegram-dashboard').textContent)")
    page.wait_for_function("() => /GESTOPPT/.test(document.querySelector('#tab-telegram-dashboard').textContent)")
    t = tiles(page)
    assert t["Laufender Ablauf"][0] == "Keiner" and "GESTOPPT" in t["Letzter Durchlauf"][1]
    assert problems == []


def test_leaving_the_tabs_leaves_no_second_socket(ui):
    app, api, scn, acc, x, open_page = ui
    page, problems = open_page()
    dash_ready(page)
    for _ in range(3):
        page.click("#tabs button[data-tab=telegram-history]")
        hist_rows(page)
        page.click("#tabs button[data-tab=telegram-dashboard]")
        dash_ready(page)
    assert page.evaluate("window.__sockets.filter(w => w.url.includes('/ws/modules/telegram') && w.readyState <= 1).length") == 1
    assert problems == []


# --- Verlauf -----------------------------------------------------------------------------------------------

def test_history_list_columns_filters_and_detail(ui):
    app, api, scn, acc, x, open_page = ui
    r1, r2, r3 = x["runs"]
    page, problems = open_page(hash_="#telegram-history")
    assert hist_rows(page) == 3
    rows = page.locator(f"{HIST} [data-hist-rows] tr[data-run]")
    assert [rows.nth(i).get_attribute("data-run") for i in range(3)] == [str(r3), str(r2), str(r1)]      # newest first
    cells = rows.nth(2).locator("td").all_inner_texts()
    assert cells[2].startswith("Neukontakt") and cells[3:9] == ["3", "2", "1", "0", "1 Min 35 s", "FERTIG"]
    assert rows.nth(1).locator("td").all_inner_texts()[3:9] == ["3", "1", "0", "2", "30 s", "GESTOPPT"]
    for h in ("Start", "Ende", "Ablauf", "Gewählt", "Erfolgreich", "Fehler", "Abgebrochen", "Dauer", "Status"):
        assert h.lower() in page.inner_text(f"{HIST} thead").lower()

    # filters
    page.select_option(f"{HIST} [data-hf=status]", "stopped")
    page.wait_for_function("() => document.querySelectorAll('#tab-telegram-history [data-hist-rows] tr[data-run]').length === 1")
    page.select_option(f"{HIST} [data-hf=status]", "")
    page.select_option(f"{HIST} [data-hf=account]", str(x["b_acc"]))
    page.wait_for_function("id => document.querySelector('#tab-telegram-history [data-hist-rows] tr[data-run]')?.dataset.run === id", arg=str(r3))
    assert hist_rows(page) == 1
    page.click(f"{HIST} [data-hist-act=reset]")
    assert hist_rows(page) == 3
    page.fill(f"{HIST} [data-hf=from]", on_day(1).date().isoformat())
    page.fill(f"{HIST} [data-hf=to]", on_day(1).date().isoformat())
    page.dispatch_event(f"{HIST} [data-hf=to]", "change")
    page.wait_for_function("id => document.querySelector('#tab-telegram-history [data-hist-rows] tr[data-run]')?.dataset.run === id", arg=str(r2))
    assert hist_rows(page) == 1
    page.click(f"{HIST} [data-hist-act=reset]")
    page.select_option(f"{HIST} [data-hf=workflow]", index=0)
    assert hist_rows(page) == 3

    # the CSV button follows the filters and serves the file
    page.select_option(f"{HIST} [data-hf=status]", "done")
    page.wait_for_function("() => document.querySelectorAll('#tab-telegram-history [data-hist-rows] tr[data-run]').length === 2")
    href = page.get_attribute(f"{HIST} [data-hist-export]", "href")
    assert href.startswith("/api/telegram/runs/export.csv") and "status=done" in href
    body = page.evaluate("href => fetch(href).then(r => r.text())", href)
    assert body.startswith("run_id,account") and body.count("\r\n") == 3       # header + R3 + R1 (fetch drops the byte order mark)
    page.click(f"{HIST} [data-hist-act=reset]")

    # detail: summary, every chat with time, result and reason; hostile name stays text
    page.click(f"{HIST} tr[data-run='{r1}']")
    page.wait_for_selector(f"{HIST} [data-detail-rows] tr")
    head = page.inner_text(f"{HIST} [data-detail-head]")
    assert "Neukontakt" in head and f"#{r1}" in head and "FERTIG" in head and "1 Min 35 s" in head
    detail = page.locator(f"{HIST} [data-detail-rows] tr")
    assert detail.count() == 3
    texts = detail.all_inner_texts()
    assert HOSTILE in texts[1] and page.locator(f"{HIST} img").count() == 0 and page.evaluate("window.__xss") is None
    assert "Fertig" in texts[0] and "Fehler" in texts[2] and "Der Nutzer hat dieses Konto blockiert" in texts[2]
    assert re.search(r"\d\d:\d\d:\d\d", texts[0])
    page.click(f"{HIST} [data-errors-btn]")
    page.wait_for_function("() => document.querySelectorAll('#tab-telegram-history [data-detail-rows] tr').length === 1")
    assert "Alle Chats zeigen" in page.inner_text(f"{HIST} [data-errors-btn]")
    page.click(f"{HIST} [data-errors-btn]")
    page.wait_for_function("() => document.querySelectorAll('#tab-telegram-history [data-detail-rows] tr').length === 3")
    csv = page.evaluate("href => fetch(href).then(r => r.text())", page.get_attribute(f"{HIST} [data-detail-head] a[download]", "href"))
    assert "The user has blocked this account" in csv
    page.click(f"{HIST} [data-hist-act=back]")
    assert hist_rows(page) == 3 and page.locator(f"{HIST} [data-detail-head]").count() == 0
    assert no_overflow(page) and problems == []


def test_history_delete_and_cleanup_keep_the_chats(ui):
    app, api, scn, acc, x, open_page = ui
    r1, r2, r3 = x["runs"]
    age(app, r1, 40), age(app, r2, 20), age(app, r3, 0.2)
    chats_before = {c["id"]: c["chat_status"] for c in chats(api)["items"]}
    page, problems = open_page(hash_="#telegram-history")
    assert hist_rows(page) == 3

    # delete one run from the list (confirm is accepted by the page handler)
    page.click(f"{HIST} tr[data-run='{r2}'] [data-hist-act=delete]")
    page.wait_for_function("() => document.querySelectorAll('#tab-telegram-history [data-hist-rows] tr[data-run]').length === 2")
    assert [r["id"] for r in ok(api.get(f"{API}/runs"))["items"]] == [r3, r1]

    # cleanup dialog: invalid input is refused, then runs older than 30 days go
    page.click(f"{HIST} [data-hist-act=cleanup]")
    page.fill("#modal input[name=days]", "30")
    assert "Durchläufe" in page.inner_text("#modal") and "Die Chats behalten ihren Status" in page.inner_text("#modal")
    page.click("#modal [type=submit]")
    page.wait_for_function("() => document.querySelectorAll('#tab-telegram-history [data-hist-rows] tr[data-run]').length === 1")
    page.wait_for_selector("#modal.hidden", state="attached")
    assert [r["id"] for r in ok(api.get(f"{API}/runs"))["items"]] == [r3]
    assert {c["id"]: c["chat_status"] for c in chats(api)["items"]} == chats_before

    # delete from the detail view goes back to an (almost) empty list
    page.click(f"{HIST} tr[data-run='{r3}']")
    page.wait_for_selector(f"{HIST} [data-detail-head]")
    page.click(f"{HIST} [data-detail-head] [data-hist-act=delete]")
    page.wait_for_selector(f"{HIST} .empty")
    assert "Keine Durchläufe" in page.inner_text(HIST)
    assert ok(api.get(f"{API}/runs"))["total"] == 0 and {c["id"]: c["chat_status"] for c in chats(api)["items"]} == chats_before
    page.click("#tabs button[data-tab=telegram-dashboard]")
    dash_ready(page)
    assert tiles(page)["Alle Chats"][0] == "6" and tiles(page)["Letzter Durchlauf"][0] == "—"
    assert problems == []


def test_a_running_run_is_listed_live_and_cannot_be_deleted(ui):
    app, api, scn, acc, x, open_page = ui
    page, problems = open_page(hash_="#telegram-history")
    assert hist_rows(page) == 3
    wf = make_workflow(api, [text_step("eins", 30), text_step("zwei", 0)], name="Langsam")
    ids = [c["id"] for c in chats(api, account_id=acc["id"], status="pending")["items"]]
    run = ok(api.post(f"{API}/runs", json={"account_id": acc["id"], "workflow_id": wf["id"], "chat_ids": ids}))
    page.wait_for_selector(f"{HIST} tr[data-run='{run['id']}']")
    row = f"{HIST} tr[data-run='{run['id']}']"
    assert "AKTIV" in page.inner_text(row) and page.locator(f"{row} [data-hist-act=delete]").count() == 0
    page.click(row)
    page.wait_for_selector(f"{HIST} [data-detail-rows] tr")
    assert page.locator(f"{HIST} [data-detail-head] [data-hist-act=delete]").count() == 0
    ok(api.post(f"{API}/runs/{run['id']}/stop"))
    page.wait_for_function("() => /GESTOPPT/.test(document.querySelector('#tab-telegram-history [data-detail-head]').textContent)")
    page.wait_for_selector(f"{HIST} [data-detail-head] [data-hist-act=delete]")
    assert problems == []


def test_history_in_english_and_at_phone_width(ui):
    app, api, scn, acc, x, open_page = ui
    page, problems = open_page(lang="en", hash_="#telegram-history")
    assert hist_rows(page) == 3
    text = page.inner_text(HIST)
    for s in ("History", "All workflows", "All statuses", "Export CSV", "Clean up old runs", "Aborted", "FINISHED", "STOPPED"):
        assert s in text, s
    page.click(f"{HIST} tr[data-run='{x['runs'][0]}']")
    page.wait_for_selector(f"{HIST} [data-detail-rows] tr")
    text = page.inner_text(HIST)
    assert "Back to history" in text and "Result per chat" in text and "The user has blocked this account" in text
    assert "Show errors only" in text and "Delete run" in text
    page.close()

    phone, problems2 = open_page(viewport=(390, 844), hash_="#telegram-history")
    assert hist_rows(phone) == 3 and no_overflow(phone)
    phone.click(f"{HIST} tr[data-run='{x['runs'][0]}']")
    phone.wait_for_selector(f"{HIST} [data-detail-rows] tr")
    assert no_overflow(phone)
    phone.evaluate("location.hash = '#telegram-dashboard'")
    dash_ready(phone)
    assert no_overflow(phone)
    assert problems == [] and problems2 == []
