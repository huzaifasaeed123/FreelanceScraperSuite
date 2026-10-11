"""Browser check of the main dashboard (the overview): one card per project with a few numbers - Telegram from its module,
WhatsApp as "coming soon", Jaumo from its own stats - and the former dashboard of Jaumo one click away under the Jaumo group.
Edge via Playwright against the real server and the fake Telethon client."""

import pytest

from conftest import ok
from test_telegram_history_ui import browser, ui  # noqa: F401  (pytest fixtures, used by name)

pw_sync = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.ui

OV = "#overview"


def card(page, key):
    return page.locator(f'{OV} [data-ov="{key}"]')


def numbers(loc):
    return loc.locator(".ov-metric b").all_inner_texts()


def test_the_overview_has_a_card_per_project_in_german(ui):
    app, api, scn, acc, x, open_page = ui
    page, problems = open_page("de", hash_="#dashboard")
    page.wait_for_selector(f"{OV} .ov-card")
    assert page.eval_on_selector_all(f"{OV} .ov-card", "e => e.map(c => c.dataset.ov)") == ["telegram", "whatsapp", "jaumo"]
    assert page.inner_text("#tab-dashboard h1") == "Übersicht" and "active" in page.get_attribute('#tabs [data-tab="dashboard"]', "class")

    tg = card(page, "telegram")
    assert "Telegram" in tg.inner_text() and "Aktiv" in tg.inner_text()
    assert tg.locator(".ov-metric span").all_inner_texts() == ["Offene Chats", "Gesendet", "Antworten"]
    mine = [str(m["value"]) for m in ok(api.get("/api/modules/summary"))[0]["metrics"]]
    assert numbers(tg) == mine == ["2", "2", "0"]                      # fixture: 2 chats not processed, 2 messages sent, no reply
    assert "Alle Telegram-Statistiken ansehen" in tg.inner_text()

    soon = card(page, "whatsapp")
    assert soon.evaluate("e => e.tagName") == "DIV" and soon.locator(".ov-metric").count() == 0     # not a link: nothing to open yet
    assert "Demnächst" in soon.inner_text() and "In Vorbereitung" in soon.inner_text()

    stats = ok(api.get("/api/stats"))
    jaumo = card(page, "jaumo")
    assert numbers(jaumo) == [str(stats["accounts_total"]), str(stats["liked"]), str(stats["matches"])]
    assert jaumo.locator(".ov-metric span").all_inner_texts() == ["Accounts", "Likes", "Matches"]
    assert "Alle Jaumo-Statistiken ansehen" in jaumo.inner_text()
    assert problems == [], problems


def test_the_cards_open_the_dashboards_of_the_projects(ui):
    app, api, scn, acc, x, open_page = ui
    page, problems = open_page("de", hash_="#dashboard")
    page.wait_for_selector(f"{OV} .ov-card")
    card(page, "telegram").click()
    page.wait_for_selector("#tab-telegram-dashboard .kpi")
    assert page.evaluate("location.hash") == "#telegram-dashboard"

    page.click('#tabs [data-tab="dashboard"]')                           # back to the overview
    page.wait_for_selector(f"{OV} .ov-card")
    card(page, "jaumo").click()
    page.wait_for_selector("#tab-jaumo #kpis .kpi")
    assert page.evaluate("location.hash") == "#jaumo" and page.locator("#tab-jaumo #kpis .kpi").count() == 4
    assert "Jaumo" in page.inner_text("#tab-jaumo h1")
    assert page.is_visible('#nav-jaumo [data-tab="jaumo"]')               # also reachable from the Jaumo menu
    assert not page.is_visible(f"{OV}")
    assert problems == [], problems


def test_the_overview_in_english_and_at_phone_width(ui):
    app, api, scn, acc, x, open_page = ui
    page, problems = open_page("en", hash_="#dashboard", viewport=(390, 900))
    page.wait_for_selector(f"{OV} .ov-card")
    assert page.inner_text("#tab-dashboard h1") == "Overview"
    text = page.inner_text(OV)
    for wanted in ("Open chats", "Sent", "Replies", "Coming soon", "View all Telegram statistics", "View all Jaumo statistics"):
        assert wanted in text, wanted
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert problems == [], problems


def test_the_overview_reload_keeps_the_page_and_follows_changes(ui):
    app, api, scn, acc, x, open_page = ui
    page, problems = open_page("de", hash_="#dashboard")
    page.wait_for_selector(f"{OV} .ov-card")
    assert numbers(card(page, "telegram"))[2] == "0"
    ok(api.post("/api/telegram/chats/bulk-status", json={"ids": x["a"][:1], "status": "pending"}))
    page.reload()
    page.wait_for_selector(f"{OV} .ov-card")
    assert numbers(card(page, "telegram"))[0] == "3"                      # one more chat is open now
    assert problems == [], problems
