"""Browser walk-through of the Telegram Chats tab (Edge via Playwright) against the real server and the fake
Telethon client: selection, filters, live updates, sync, German / English, phone width.
Any JS error, console error or failed request fails the test."""

import json
import re
import time

import pytest

from conftest import ADMIN_PASS, ok, wait_until
from test_telegram_accounts import ENV, link
from test_telegram_chats import BASE, Scenario, accounts, chats, dlg

pw_sync = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.ui

T = "#tab-telegram-chats"


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
    """A server with 1,300 chats (the first four with tricky names) and a logged-in page."""
    scn = Scenario(tmp_path / "fake_tg")
    items = [dlg(i, i / 24) for i in range(1, 1301)]
    items[0].update(first_name="Jürgen", last_name="Müller", username="jm")
    items[1].update(first_name="Ünal", last_name="Weiß", username="ueber")
    items[2].update(first_name='<img src=x onerror="window.__xss=1">', last_name="<b>fett</b>",
                    last_message="<script>window.__xss=2</script>", username="xss")
    scn.dialogs(items)
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir))
    api = app.client()
    link(api)
    wait_until(lambda: accounts(api)["+4915100000001"]["sync"] is None, msg="import")
    assert chats(api, limit=1)["total"] == 1300

    pages = []

    def open_page(lang="de", viewport=(1400, 900)):
        ctx = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]}, locale="en-US")
        ctx.add_init_script(f"try{{localStorage.setItem('lang','{lang}')}}catch(e){{}}")
        page = ctx.new_page()
        problems = []
        page.on("pageerror", lambda e: problems.append(f"JS error: {e}"))
        page.on("console", lambda m: m.type == "error" and problems.append(f"console: {m.text}"))
        page.on("response", lambda r: r.status >= 400 and problems.append(f"HTTP {r.status} {r.url}"))
        page.on("dialog", lambda d: d.accept())
        page.goto(app.url + "/#telegram-chats")
        page.fill("input[name=username]", "admin")
        page.fill("input[name=password]", ADMIN_PASS)
        page.click("#login-form button[type=submit]")
        page.wait_for_selector(f"{T} tbody tr[data-id]")
        pages.append(ctx)
        return page, problems

    yield app, api, scn, open_page
    for ctx in pages:
        ctx.close()


def showing(page):
    return page.inner_text(f"{T} [data-showing]")


def wait_showing(page, pattern):
    page.wait_for_function("([sel, re]) => new RegExp(re).test(document.querySelector(sel).textContent)",
                           arg=[f"{T} [data-showing]", pattern])


def test_german_walkthrough(ui):
    app, api, scn, open_page = ui
    page, problems = open_page("de")
    assert page.inner_text(f"{T} h1") == "Chats"
    assert page.inner_text(f"{T} [data-count]") == "0 Chats ausgewählt"
    chips = page.inner_text(f"{T} .tg-chips")
    for emoji in ("🟢", "🔵", "✅", "❌", "⏸"):
        assert emoji in chips
    assert "Noch nicht bearbeitet" in chips and "1.300" in chips       # German number format
    assert showing(page) == "1–50 von 1.300"
    assert page.evaluate("window.__xss") is None and page.locator(f"{T} tbody img").count() == 0   # names are escaped
    assert "<img src=x" in page.inner_text(f"{T} tbody")

    # select the page, then everything that matches
    page.check(f"{T} [data-all]")
    assert page.inner_text(f"{T} [data-count]") == "50 Chats ausgewählt"
    assert "Alle 1.300 passenden Chats auswählen" in page.inner_text(f"{T} [data-banner]")
    page.click(f'{T} [data-act="select-matching"]')
    page.wait_for_function("document.querySelector('#tab-telegram-chats [data-count]').textContent === '1.300 Chats ausgewählt'")
    assert "Alle 1.300 passenden Chats sind ausgewählt" in page.inner_text(f"{T} [data-banner]")

    # the selection survives paging and filter changes
    page.click(f'{T} button[data-pg="1"]')
    wait_showing(page, "^51")
    assert page.locator(f"{T} tbody input[data-sel]:checked").count() == 50
    page.click(f'{T} .tg-chip[data-status="done"]')
    wait_showing(page, "^0–0 von 0")
    assert page.inner_text(f"{T} [data-count]") == "1.300 Chats ausgewählt"
    page.click(f'{T} .tg-chip[data-status="done"]')
    wait_showing(page, "von 1.300$")
    page.click(f'{T} [data-act="clear"]')
    assert page.inner_text(f"{T} [data-count]") == "0 Chats ausgewählt"

    # search: case-insensitive, umlauts, @username
    page.fill(f'{T} [data-f="q"]', "ÜNAL")
    wait_showing(page, "^1–1 von 1$")
    assert "Ünal Weiß" in page.inner_text(f"{T} tbody")
    page.fill(f'{T} [data-f="q"]', "@JM")
    wait_showing(page, "^1–1 von 1$")
    page.wait_for_selector(f"{T} tbody tr:has-text('Jürgen Müller')")
    page.fill(f'{T} [data-f="q"]', "")
    wait_showing(page, "von 1.300$")

    # bulk status for two rows, then the status chip shows exactly them
    page.check(f"{T} tbody tr:nth-child(1) input[data-sel]")
    page.check(f"{T} tbody tr:nth-child(2) input[data-sel]")
    assert page.inner_text(f"{T} [data-count]") == "2 Chats ausgewählt"
    page.select_option(f"{T} [data-bulk]", "done")
    page.click(f'{T} [data-act="bulk-status"]')
    page.wait_for_selector("#toasts >> text=2 Chats aktualisiert")
    assert ok(api.get("/api/telegram/chats/summary"))["by_status"]["done"] == 2
    page.click(f'{T} .tg-chip[data-status="done"]')
    wait_showing(page, "von 2$")
    assert page.locator(f"{T} .tg-st").all_inner_texts() == ["✅ Bearbeitet"] * 2

    # edit one chat
    page.click(f'{T} tbody tr:nth-child(1) [data-act="edit"]')
    page.select_option("#modal select[name=status]", "error")
    page.fill("#modal textarea[name=notes]", "Rückruf morgen")
    page.click("#modal [type=submit]")
    page.wait_for_selector("#modal", state="hidden")
    page.click(f'{T} [data-act="reset"]')
    wait_showing(page, "von 1.300$")
    assert [c["notes"] for c in chats(api, status="error")["items"]] == ["Rückruf morgen"]

    # sorting by a header
    page.click(f'{T} [data-sort="display_name"]')
    page.wait_for_function("document.querySelector('#tab-telegram-chats [data-sort=display_name]').textContent.includes('▼')")
    page.click(f'{T} [data-sort="display_name"]')
    page.wait_for_function("document.querySelector('#tab-telegram-chats [data-sort=display_name]').textContent.includes('▲')")

    # a new incoming message appears without reloading
    scn.incoming(id=555001, access_hash=1, first_name="Livia", last_name="Neu", username="livia", text="live!",
                 date=BASE.isoformat())
    page.click(f'{T} [data-sort="last_contact_at"]')
    page.wait_for_selector(f"{T} tbody tr:first-child:has-text('Livia')", timeout=10000)
    assert "live!" in page.inner_text(f"{T} tbody tr:first-child")

    # sync button: a new dialog shows up
    items = json.loads((scn.dir / "dialogs.json").read_text(encoding="utf-8"))
    items.append(dlg(9000, 0, first_name="Nachzügler", username="late"))
    scn.dialogs(items)
    page.click(f'{T} [data-act="sync"]')
    page.wait_for_selector("#toasts >> text=Chats synchronisiert", timeout=30000)
    page.fill(f'{T} [data-f="q"]', "Nachzügler")
    wait_showing(page, "^1–1 von 1$")
    assert "Nachzügler" in page.inner_text(f"{T} tbody")
    assert not problems, problems


def test_english_and_phone(ui):
    _, _, _, open_page = ui
    page, problems = open_page("en")
    assert page.inner_text(f"{T} [data-count]") == "0 chats selected"
    assert "Not processed yet" in page.inner_text(f"{T} .tg-chips") and "1,300" in page.inner_text(f"{T} .tg-chips")
    assert showing(page) == "1–50 of 1,300"
    page.check(f"{T} [data-all]")
    assert "Select all 1,300 matching chats" in page.inner_text(f"{T} [data-banner]")
    assert page.inner_text(f"{T} [data-count]") == "50 chats selected"
    assert not re.search(r"\b(Chats ausgewählt|Alle Konten)\b", page.inner_text(T))

    page.set_viewport_size({"width": 390, "height": 800})
    time.sleep(0.4)
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    assert page.is_visible(f"{T} [data-count]") and page.is_visible(f'{T} [data-f="q"]')
    assert not problems, problems


def test_no_account_shows_a_hint(browser, make_app):
    app = make_app(**ENV)
    ctx = browser.new_context(viewport={"width": 1200, "height": 800})
    ctx.add_init_script("try{localStorage.setItem('lang','de')}catch(e){}")
    page = ctx.new_page()
    page.goto(app.url + "/#telegram-chats")
    page.fill("input[name=username]", "admin")
    page.fill("input[name=password]", ADMIN_PASS)
    page.click("#login-form button[type=submit]")
    page.wait_for_selector(f"{T} .empty")
    assert "Noch kein Konto verbunden" in page.inner_text(T)
    ctx.close()


def test_the_first_contact_date_is_shown_in_every_row(ui):
    app, api, scn, open_page = ui
    page, problems = open_page("de")
    row = chats(api, sort="last_contact_at", order="desc", limit=1)["items"][0]
    cell = page.locator(f'{T} tbody tr[data-id="{row["id"]}"] [title="Erster Kontakt"]')
    expected = page.evaluate("(iso) => window.PanelKit.fmtDate(iso)", row["first_contact_at"])
    assert expected and cell.inner_text() == expected
    assert "erster kontakt" in page.inner_text(f"{T} thead").lower()     # the header is set in capitals
    assert not problems, problems
