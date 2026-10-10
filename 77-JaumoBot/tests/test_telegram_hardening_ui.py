"""Browser walk-through of the Telegram hardening features (Edge via Playwright) against the real server and the fake client:
the limits notice and the auto-resume option in the Versand form, a run that pauses when the connection drops and goes on by
itself, the account list during a reconnect and after a revoked session ("Anmelden"), the PeerFlood banner and the unused files
dialog. German and English; any JS error, console error or failed request fails the test."""

import json

import pytest

from conftest import ADMIN_PASS, jpeg_bytes, ok, wait_until
from test_telegram_accounts import ENV, PHONE
from test_telegram_chats import Scenario, dlg, link_synced
from test_telegram_hardening import FAST, ctl
from test_telegram_runs import make_workflow, outbox, text_step, upload, wait_sent
from test_telegram_runs_ui import LIVE, T, choose_and_start, form_ready

pw_sync = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.ui
API = "/api/telegram"
ROW = "#tab-telegram-accounts tbody tr"


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
    scn = Scenario(tmp_path / "fake_tg")
    scn.dialogs([dlg(i, i) for i in range(1, 5)])
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir), TELEGRAM_AUTH_PROBE="0.4", **FAST)
    api = app.client()
    acc = link_synced(api)
    contexts = []

    def open_page(lang="de", hash_="#telegram-runs", viewport=(1400, 1000)):
        ctx = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]}, locale="en-US")
        ctx.add_init_script(f"try{{localStorage.setItem('lang','{lang}')}}catch(e){{}}")
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

    yield app, api, scn, acc, open_page
    for ctx in contexts:
        ctx.close()


def test_limits_notice_and_auto_resume_option_in_the_start_form(ui):
    app, api, scn, acc, open_page = ui
    make_workflow(api, [text_step("eins", 0), text_step("zwei", 0)], name="Ohne Pause")
    make_workflow(api, [text_step("eins", 5), text_step("zwei", 0)], name="Mit Pause")
    page, problems = open_page()
    form_ready(page)
    notice = page.inner_text(f"{T} .tg-risk")
    assert "Automatisierte Erstnachrichten" in notice and "Pausen größer als 0 Sekunden" in notice and "FloodWait" in notice
    assert page.is_checked(f"{T} input[data-form=autoResume]") is False
    page.select_option(f"{T} select[data-form=workflow]", label="Ohne Pause")
    assert "ohne Pause" in page.inner_text(f"{T} .tg-risk")                      # a workflow without pauses is called out
    page.select_option(f"{T} select[data-form=workflow]", label="Mit Pause")
    assert "ohne Pause" not in page.inner_text(f"{T} .tg-risk")
    # the notice does not block anything: the run starts, with the option the operator chose
    page.check(f"{T} input[data-form=autoResume]")
    page.click(f"{T} [data-run-act=preset][data-status=pending]")
    page.wait_for_function("() => /4 Chats/.test(document.querySelector('#tab-telegram-runs [data-start-count]').textContent)")
    page.click(f"{T} [data-run-act=start]")
    assert "automatisch fortsetzen" in page.inner_text("#modal")
    page.click("#modal [data-go]")
    page.wait_for_selector(LIVE)
    runs = ok(api.get(f"{API}/runs"))["items"]
    assert runs[0]["auto_resume"] is True
    ok(api.post(f"{API}/runs/{runs[0]['id']}/stop"))
    assert problems == []

    page.click("#top-user")
    page.click("#menu-lang")
    page.click('#tabs [data-tab="telegram-runs"]')
    form_ready(page)
    assert "Automated first-contact messages from personal accounts" in page.inner_text(f"{T} .tg-risk")
    assert "Resume automatically" in page.inner_text(T)
    assert problems == []


def test_connection_drop_during_a_run_is_visible_everywhere_and_the_run_goes_on_by_itself(ui):
    app, api, scn, acc, open_page = ui
    make_workflow(api, [text_step("eins", 3), text_step("zwei", 0)], name="Neukontakt")
    page, problems = open_page()
    form_ready(page)
    page.check(f"{T} input[data-form=autoResume]")
    choose_and_start(page, api)
    wait_sent(scn, 1)
    ctl(scn, down=[PHONE])
    page.wait_for_function("() => /PAUSIERT/.test(document.querySelector('#tab-telegram-runs [data-badge]').textContent)")
    note = page.inner_text(f"{LIVE} [data-note]")
    assert "Verbindung zu Telegram verloren" in note and "automatisch fortgesetzt" in note
    page.click('#tabs [data-tab="telegram-accounts"]')
    page.wait_for_selector(ROW)
    page.wait_for_function("() => /Verbindet/.test(document.querySelector('#tab-telegram-accounts tbody tr').textContent)")
    assert "Telegram ist nicht erreichbar" in page.inner_text(ROW) or "Verbindung zu Telegram verloren" in page.inner_text(ROW)
    assert page.locator(f"{ROW} [data-act=disconnect]").count() == 1          # the retries can be stopped
    page.click('#tabs [data-tab="telegram-dashboard"]')
    page.wait_for_selector("#tab-telegram-dashboard [data-dash-live]")
    assert "Verbindung zu Telegram verloren" in page.inner_text("#tab-telegram-dashboard [data-dash-live]")
    ctl(scn, down=[])
    wait_until(lambda: ok(api.get(f"{API}/runs"))["items"][0]["status"] == "done", timeout=40, msg="the run to finish by itself")
    assert [m["content"] for m in outbox(scn)].count("eins") == 4
    assert problems == []


def test_a_revoked_session_shows_an_error_and_offers_to_log_in_again(ui):
    app, api, scn, acc, open_page = ui
    page, problems = open_page(hash_="#telegram-accounts")
    page.wait_for_selector(f"{ROW} .badge.ok")
    ctl(scn, revoke=[PHONE])
    page.wait_for_selector(f"{ROW} .badge.bad", timeout=15000)                   # pushed live, no reload
    text = page.inner_text(ROW)
    assert "Fehler" in text and "Telegram hat diese Sitzung beendet" in text
    assert page.locator(f"{ROW} [data-act=login]").inner_text().strip() == "Anmelden"
    assert page.locator(f"{ROW} [data-act=connect]").count() == 0
    assert "fake:" not in page.content()
    ctl(scn, revoke=[])
    page.click(f"{ROW} [data-act=login]")
    page.wait_for_selector("#modal input[name=phone]")
    assert page.input_value("#modal input[name=phone]") == PHONE
    page.click("#modal [type=submit]")
    page.wait_for_selector("#modal input[name=code]")
    page.fill("#modal input[name=code]", "12345")
    page.click("#modal [type=submit]")
    page.wait_for_selector("#modal", state="hidden")
    page.wait_for_selector(f"{ROW} .badge.ok")
    assert problems == []


def test_a_revoked_session_during_a_run_links_to_the_login_and_peer_flood_is_shown(ui):
    app, api, scn, acc, open_page = ui
    make_workflow(api, [text_step("eins", 3), text_step("zwei", 0)], name="Neukontakt")
    (scn.dir / "send_errors.json").write_text(json.dumps({"1001": {"error": "PeerFloodError"}}))
    page, problems = open_page()
    choose_and_start(page, api)
    page.wait_for_selector(f"{LIVE} .tg-flood:not(.hidden)")                     # first chat: PeerFlood
    flood = page.inner_text(f"{LIVE} .tg-flood")
    assert "PeerFlood" in flood and "1 Chat" in flood
    page.wait_for_selector("#toasts :text('PeerFlood')")
    ctl(scn, revoke=[PHONE])
    page.wait_for_function("() => /PAUSIERT/.test(document.querySelector('#tab-telegram-runs [data-badge]').textContent)", timeout=15000)
    link = page.locator(f"{LIVE} [data-note] a")
    assert "neu anmelden" in link.inner_text() and link.get_attribute("href") == "#telegram-accounts"
    page.click("#top-user")
    page.click("#menu-lang")
    page.wait_for_selector(f"{LIVE} .tg-flood")
    assert "limited this account" in page.inner_text(f"{LIVE} .tg-flood")
    assert "Log in again" in page.inner_text(f"{LIVE} [data-note] a")
    assert problems == []


def test_unused_files_dialog_lists_and_deletes_them(ui):
    app, api, scn, acc, open_page = ui
    used = upload(api, "used.jpg", jpeg_bytes(1, (40, 40)))
    spare = upload(api, "spare.png", jpeg_bytes(2, (40, 40), "PNG"))
    make_workflow(api, [{"type": "image", "file": used, "pause_after": 0}], name="Bild")
    page, problems = open_page(hash_="#telegram-workflows")
    page.click("[data-act=cleanup]")
    page.wait_for_selector("#modal .tg-unused")
    listing = page.inner_text("#modal")
    assert spare in listing and used not in listing and "1 Datei" in listing
    page.click("#modal [data-clean]")
    page.wait_for_selector("#modal", state="hidden")
    assert "1 Datei gelöscht" in page.inner_text("#toasts")
    assert [m["name"] for m in ok(api.get(f"{API}/media"))] == [used]
    page.click("[data-act=cleanup]")
    page.wait_for_selector("#modal .empty")
    assert "Keine ungenutzten Dateien" in page.inner_text("#modal")
    page.click("#modal [data-close-modal]")
    assert problems == []
