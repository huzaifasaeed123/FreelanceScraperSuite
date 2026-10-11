"""Browser walk-through of the Telegram Versand tab (Edge via Playwright) against the real server and the fake Telethon
client: START form validation, the confirmation, the live panel (countdown ticks, freezes on pause), pause / resume /
stop / restart, the per-chat result list, reload during a run, tab switches that must not leak timers or sockets,
German and English, phone width. Any JS error, console error or failed request fails the test."""

import re

import pytest

from conftest import ADMIN_PASS, ok, wait_until
from test_telegram_accounts import ENV
from test_telegram_chats import Scenario, dlg, link_synced
from test_telegram_runs import make_workflow, text_step

pw_sync = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.ui

T = "#tab-telegram-runs"
API = "/api/telegram"
LIVE = f"{T} [data-live]"

# counts the sockets and intervals the page has open, so a leak shows up as a number
COUNTERS = """
window.__sockets = [];
const RealWS = window.WebSocket;
window.WebSocket = function (...a) { const w = new RealWS(...a); window.__sockets.push(w); return w; };
window.WebSocket.prototype = RealWS.prototype;
window.WebSocket.OPEN = RealWS.OPEN; window.WebSocket.CONNECTING = RealWS.CONNECTING;
window.__intervals = new Set();
const si = window.setInterval.bind(window), ci = window.clearInterval.bind(window);
window.setInterval = (...a) => { const id = si(...a); window.__intervals.add(id); return id; };
window.clearInterval = (id) => { window.__intervals.delete(id); ci(id); };
"""


@pytest.fixture(scope="module")
def browser():
    with pw_sync.sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="msedge")
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"Edge is not available: {e}")
        yield b
        b.close()


@pytest.fixture
def ui(browser, make_app, tmp_path):
    """A server with a linked account, four chats (one with a hostile name) and the workflow 'Neukontakt'."""
    scn = Scenario(tmp_path / "fake_tg")
    items = [dlg(i, i) for i in range(1, 5)]
    items[1].update(first_name='<img src=x onerror="window.__xss=1">', username="xss")
    scn.dialogs(items)
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir), TELEGRAM_RETRY_WAIT="0.3")
    api = app.client()
    acc = link_synced(api)
    wf = make_workflow(api, [text_step("eins", 8), text_step("zwei", 2), text_step("drei", 0)], name="Neukontakt")
    contexts = []

    def open_page(lang="de", viewport=(1400, 1000), hash_="#telegram-runs"):
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

    yield app, api, scn, acc, wf, open_page
    for ctx in contexts:
        ctx.close()


# --- helpers ---------------------------------------------------------------------------------------

def form_ready(page):
    page.wait_for_selector(f"{T} [data-run-act=start]")
    page.wait_for_selector(f"{T} tbody tr[data-id]")


def seconds(page):
    """The number in the countdown tile ('in 7 Sekunden' -> 7)."""
    m = re.search(r"\d+", page.inner_text(f"{LIVE} [data-count] .tg-count"))
    return int(m.group()) if m else None


def badge(page):
    return page.inner_text(f"{LIVE} [data-badge]").strip()


def choose_and_start(page, api, wf_name="Neukontakt"):
    form_ready(page)
    page.select_option(f"{T} select[data-form=workflow]", label=wf_name)
    page.click(f"{T} [data-run-act=preset][data-status=pending]")
    page.wait_for_function("() => /4 Chats/.test(document.querySelector('#tab-telegram-runs [data-start-count]').textContent)")
    page.click(f"{T} [data-run-act=start]")
    page.click("#modal [data-go]")
    page.wait_for_selector(LIVE)


def runs(api, **params):
    return ok(api.get(f"{API}/runs", params=params))["items"]


def open_intervals(page):
    return page.evaluate("window.__intervals.size")


def open_module_sockets(page):
    return page.evaluate("window.__sockets.filter(w => w.url.includes('/ws/modules/telegram') && w.readyState <= 1).length")


# --- the walk-through ---------------------------------------------------------------------------------

def test_start_watch_pause_resume_stop_restart(ui):
    app, api, scn, acc, wf, open_page = ui
    (scn.dir / "send_errors.json").write_text('{"1003": {"error": "UserPrivacyRestrictedError"}}', encoding="utf-8")
    page, problems = open_page()
    form_ready(page)

    # START form: every missing piece is named before anything starts
    page.click(f"{T} [data-run-act=start]")
    assert "Ablauf" in page.inner_text(f"{T} [data-start-error]")
    page.select_option(f"{T} select[data-form=workflow]", label="Neukontakt")
    assert "Pausen pro Chat: 10 s" in page.inner_text(f"{T} [data-wf-info]")
    page.click(f"{T} [data-run-act=start]")
    assert "mindestens einen Chat" in page.inner_text(f"{T} [data-start-error]")
    assert page.inner_text(f"{T} [data-start-count]") == "0 Chats ausgewählt"
    assert runs(api) == []

    # presets and the counter; the estimate counts the pauses (10 s per chat, none after the last one)
    page.click(f"{T} [data-run-act=preset][data-status=pending]")
    page.wait_for_function("() => /^4 Chats/.test(document.querySelector('#tab-telegram-runs [data-start-count]').textContent)")
    assert "ca. 40 s" in page.inner_text(f"{T} [data-start-est]")
    page.click(f"{T} .tg-bar [data-act=clear]")
    assert page.inner_text(f"{T} [data-start-count]") == "0 Chats ausgewählt"
    page.click(f"{T} [data-run-act=preset][data-status=pending]")
    page.wait_for_function("() => /^4 Chats/.test(document.querySelector('#tab-telegram-runs [data-start-count]').textContent)")

    # the confirmation shows what will happen; cancelling starts nothing
    page.click(f"{T} [data-run-act=start]")
    summary = page.inner_text("#modal")
    assert "Neukontakt" in summary and "4 Chats ausgewählt" in summary and "ca. 40 s" in summary
    page.click("#modal [data-close-modal]")
    assert runs(api) == []
    page.click(f"{T} [data-run-act=start]")
    page.click("#modal [data-go]")

    # live panel: status, current chat and step, next step, ticking countdown, progress
    page.wait_for_selector(LIVE)
    assert badge(page) == "AKTIV"
    page.wait_for_function("() => /User1/.test(document.querySelector('#tab-telegram-runs [data-chat]').textContent)")
    assert "@user1" in page.inner_text(f"{LIVE} [data-chat]")
    page.wait_for_function("() => /in \\d+ Sekunden/.test(document.querySelector('#tab-telegram-runs [data-count]').textContent)")
    assert "Text" in page.inner_text(f"{LIVE} [data-step]") and "Schritt 1 von 3" in page.inner_text(f"{LIVE} [data-step]")
    assert "Text" in page.inner_text(f"{LIVE} [data-next]")
    assert "Läuft" in page.inner_text("[data-run-badge]")
    first = seconds(page)
    page.wait_for_timeout(3000)
    assert seconds(page) <= first - 2
    assert page.inner_text(f"{LIVE} [data-pct]") == "0 %"

    # tab switches neither stop the countdown nor leave timers or sockets behind
    base_intervals, base_sockets = open_intervals(page), open_module_sockets(page)
    assert base_sockets == 1
    for _ in range(3):
        page.click("#tabs button[data-tab=telegram-chats]")
        page.wait_for_selector("#tab-telegram-chats tbody tr[data-id]")
        assert open_intervals(page) == base_intervals - 1 and open_module_sockets(page) == 1
        page.click("#tabs button[data-tab=telegram-runs]")
        page.wait_for_selector(LIVE)
    assert open_intervals(page) == base_intervals and open_module_sockets(page) == 1
    assert badge(page) == "AKTIV" and seconds(page) is not None

    # Pause freezes the countdown, Fortsetzen continues from the same value
    page.click(f"{LIVE} [data-run-act=pause]")
    page.wait_for_function("() => document.querySelector('#tab-telegram-runs [data-badge]').textContent.trim() === 'PAUSIERT'")
    frozen = seconds(page)
    assert "pausiert" in page.inner_text(f"{LIVE} [data-count]")
    assert "Pausiert" in page.inner_text("[data-run-badge]")
    page.wait_for_timeout(3000)
    assert seconds(page) == frozen
    assert runs(api)[0]["status"] == "paused"
    page.click(f"{LIVE} [data-run-act=resume]")
    page.wait_for_function("() => document.querySelector('#tab-telegram-runs [data-badge]').textContent.trim() === 'AKTIV'")
    page.wait_for_timeout(3000)
    assert seconds(page) <= frozen - 2

    # progress moves on to chat 2 (hostile name is shown as text), then chat 3 fails and is listed with its reason
    page.wait_for_function("() => /^[1-9]/.test(document.querySelector('#tab-telegram-runs [data-pct]').textContent) || "
                           "/Bearbeitet 1 /.test(document.querySelector('#tab-telegram-runs [data-counts]').textContent)", timeout=60000)
    wait_until(lambda: runs(api)[0]["errors"] == 1, timeout=60, msg="chat 3 to fail")
    page.wait_for_selector(f"{LIVE} .bad b:text-is('1')")
    page.wait_for_function("() => /Datenschutz/.test(document.querySelector('#tab-telegram-runs [data-list]').textContent)")
    row = page.locator(f"{T} [data-list] tr", has_text="User3")
    assert "Datenschutz" in row.inner_text() and "Fehler" in row.inner_text()
    assert page.evaluate("window.__xss") is None
    assert "<img" in page.inner_text(f"{T} [data-list]")
    page.click(f"{T} [data-errors-btn]")
    page.wait_for_function("() => document.querySelectorAll('#tab-telegram-runs [data-list] tr').length === 1")
    page.click(f"{T} [data-errors-btn]")
    page.wait_for_function("() => document.querySelectorAll('#tab-telegram-runs [data-list] tr').length === 4")
    assert page.locator(f"{T} [data-list] tr.tg-cur").count() == 1

    # Stoppen (confirmed): GESTOPPT, the chats not reached are skipped, the badge is gone
    page.click(f"{LIVE} [data-run-act=stop]")
    page.wait_for_function("() => document.querySelector('#tab-telegram-runs [data-badge]').textContent.trim() === 'GESTOPPT'")
    assert runs(api)[0]["status"] == "stopped"
    page.wait_for_function("() => document.querySelector('[data-run-badge]').textContent === ''")
    page.wait_for_function("() => /Übersprungen/.test(document.querySelector('#tab-telegram-runs [data-list]').textContent)")
    assert page.locator(f"{LIVE} [data-run-act=restart]").count() == 1 and page.locator(f"{LIVE} [data-run-act=pause]").count() == 0
    assert seconds(page) is None

    # Neustart: a new run over the same chats
    old_id = runs(api)[0]["id"]
    page.click(f"{LIVE} [data-run-act=restart]")
    page.wait_for_function("() => document.querySelector('#tab-telegram-runs [data-badge]').textContent.trim() === 'AKTIV'")
    new = runs(api)[0]
    assert new["id"] != old_id and new["total"] == 4 and new["status"] == "running"
    page.click(f"{LIVE} [data-run-act=stop]")
    page.wait_for_function("() => document.querySelector('#tab-telegram-runs [data-badge]').textContent.trim() === 'GESTOPPT'")

    # Neuer Durchlauf goes back to the start form
    page.click(f"{LIVE} [data-run-act=new]")
    form_ready(page)
    assert open_intervals(page) == base_intervals and open_module_sockets(page) == 1
    assert problems == []


def test_reload_during_a_run_recovers_the_panel(ui):
    app, api, scn, acc, wf, open_page = ui
    ids = [c["id"] for c in ok(api.get(f"{API}/chats", params={"limit": 10}))["items"]]
    run = ok(api.post(f"{API}/runs", json={"account_id": acc["id"], "workflow_id": wf["id"], "chat_ids": ids}))
    page, problems = open_page(hash_="#dashboard")
    page.wait_for_selector("[data-run-badge]:not(:empty)")           # the badge shows on every page, not just in Versand
    assert "Läuft" in page.inner_text("[data-run-badge]")
    page.click("#tabs button[data-tab=telegram-runs]")
    page.wait_for_selector(LIVE)
    assert badge(page) == "AKTIV" and page.locator(f"{T} [data-run-act=start]").count() == 0
    page.wait_for_function("() => /in \\d+ Sekunden/.test(document.querySelector('#tab-telegram-runs [data-count]').textContent)")
    page.reload()
    page.wait_for_selector(LIVE)
    assert badge(page) == "AKTIV"
    page.wait_for_function("() => /User/.test(document.querySelector('#tab-telegram-runs [data-chat]').textContent)")
    assert seconds(page) is not None

    # a paused run is recovered paused, with the frozen countdown
    ok(api.post(f"{API}/runs/{run['id']}/pause"))
    page.reload()
    page.wait_for_selector(LIVE)
    assert badge(page) == "PAUSIERT" and "pausiert" in page.inner_text(f"{LIVE} [data-count]")
    frozen = seconds(page)
    page.wait_for_timeout(1500)
    assert seconds(page) == frozen

    # a run started from elsewhere (here: the API) replaces the open start form
    ok(api.post(f"{API}/runs/{run['id']}/stop"))
    page.wait_for_function("() => document.querySelector('#tab-telegram-runs [data-badge]').textContent.trim() === 'GESTOPPT'")
    page.reload()
    form_ready(page)                         # finished: the reload leads to the start form again
    ok(api.post(f"{API}/runs", json={"account_id": acc["id"], "workflow_id": wf["id"], "chat_ids": ids[:1]}))
    page.wait_for_selector(LIVE)
    assert badge(page) == "AKTIV"

    # the socket dropping must not lose the state: events missed meanwhile are re-read on reconnect
    page.evaluate("window.__sockets.forEach(w => w.close())")
    ok(api.post(f"{API}/runs/{runs(api)[0]['id']}/pause"))
    page.wait_for_function("() => document.querySelector('#tab-telegram-runs [data-badge]').textContent.trim() === 'PAUSIERT'", timeout=15000)
    assert problems == []


def test_form_validation_offline_account_and_english(ui):
    app, api, scn, acc, wf, open_page = ui
    page, problems = open_page(lang="en")
    form_ready(page)
    assert "Which workflow" in page.inner_text(T)
    page.select_option(f"{T} select[data-form=workflow]", label="Neukontakt")
    page.click(f"{T} [data-run-act=preset][data-status=pending]")
    page.wait_for_function("() => /^4 chats/.test(document.querySelector('#tab-telegram-runs [data-start-count]').textContent)")
    assert "Estimated duration: about 40 s" in page.inner_text(f"{T} [data-start-est]")

    # retry option shows its number of attempts and appears in the summary
    page.select_option(f"{T} select[data-form=onError]", "retry")
    page.fill(f"{T} input[data-form=retries]", "2")
    page.click(f"{T} [data-run-act=start]")
    assert "retry the step up to 2 times" in page.inner_text("#modal")
    assert "Start sending?" in page.inner_text("#modal-title")
    page.click("#modal [data-close-modal]")

    # an account that is not online cannot start: warning in the form, message on START, nothing is created
    ok(api.post(f"{API}/accounts/{acc['id']}/disconnect"))
    page.wait_for_selector(f"{T} .tg-warn")
    assert "not online" in page.inner_text(f"{T} .tg-warn")
    assert "Offline" in page.inner_text(f"{T} [data-run-account]")
    page.click(f"{T} [data-run-act=start]")
    assert "not online" in page.inner_text(f"{T} [data-start-error]")
    assert page.locator("#modal:not(.hidden)").count() == 0
    assert runs(api) == []

    assert problems == []


def test_phone_width_german_and_no_overflow(ui):
    app, api, scn, acc, wf, open_page = ui
    page, problems = open_page(viewport=(390, 844))
    form_ready(page)
    page.select_option(f"{T} select[data-form=workflow]", label="Neukontakt")
    page.click(f"{T} [data-run-act=preset][data-status=pending]")
    page.wait_for_function("() => /^4 Chats/.test(document.querySelector('#tab-telegram-runs [data-start-count]').textContent)")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.click(f"{T} [data-run-act=start]")
    page.click("#modal [data-go]")
    page.wait_for_selector(LIVE)
    page.wait_for_function("() => /User1/.test(document.querySelector('#tab-telegram-runs [data-chat]').textContent)")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    for sel in ("[data-run-act=pause]", "[data-run-act=stop]"):
        assert page.locator(f"{LIVE} {sel}").bounding_box()["x"] + page.locator(f"{LIVE} {sel}").bounding_box()["width"] <= 390
    assert problems == []


def test_the_retry_option_is_chosen_in_the_form_shown_in_the_confirmation_and_sent_to_the_run(ui):
    app, api, scn, acc, wf, open_page = ui
    page, problems = open_page("de")
    form_ready(page)
    assert not page.is_visible(f"{T} [data-retries]")
    page.select_option(f"{T} select[data-form=workflow]", label="Neukontakt")
    page.click(f"{T} [data-run-act=preset][data-status=pending]")
    page.select_option(f"{T} select[data-form=onError]", "retry")
    page.fill(f"{T} input[data-form=retries]", "2")
    page.click(f"{T} [data-run-act=start]")
    assert "Schritt bis zu 2× erneut versuchen, dann nächster Chat" in page.inner_text("#modal")
    page.click("#modal [data-go]")
    page.wait_for_selector(LIVE)
    started = runs(api)[0]
    assert (started["on_error"], started["retries"]) == ("retry", 2)
    ok(api.post(f"{API}/runs/{started['id']}/stop"))
    assert not problems, problems


def test_the_open_the_chat_option_is_on_by_default_shown_in_the_summary_and_sent_to_the_run(ui):
    """The client wants the contact's message to show as read before the workflow starts."""
    app, api, scn, acc, wf, open_page = ui
    page, problems = open_page("de")
    form_ready(page)
    box = f"{T} input[data-form=markRead]"
    assert page.is_checked(box)
    assert "Chat vor dem Ablauf öffnen" in page.inner_text(T) and "zwei Haken" in page.inner_text(T)
    page.select_option(f"{T} select[data-form=workflow]", label="Neukontakt")
    page.click(f"{T} [data-run-act=preset][data-status=pending]")
    page.click(f"{T} [data-run-act=start]")
    assert "Nachrichten des Kontakts vorher als gelesen markieren" in page.inner_text("#modal")
    page.click("#modal [data-close-modal]")

    page.uncheck(box)                                                # switched off: sent as such and named in the summary
    page.click(f"{T} [data-run-act=start]")
    assert "nein, direkt senden" in page.inner_text("#modal")
    page.click("#modal [data-go]")
    page.wait_for_selector(LIVE)
    started = runs(api)[0]
    assert started["mark_read"] is False
    ok(api.post(f"{API}/runs/{started['id']}/stop"))
    assert not problems, problems
