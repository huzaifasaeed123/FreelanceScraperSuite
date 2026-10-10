"""Telegram panel XSS check in the browser (Edge via Playwright): hostile text (HTML, script, quote and attribute
breakers) is planted in every place a stranger or an operator can write to - chat names, usernames, last messages,
notes, account labels, workflow names and step texts, error reasons, status messages - and every tab, dialog, the live
panel, the history and the live WebSocket updates are opened. Nothing may become an element or an attribute: every
payload carries data-xss, so one selector finds anything that was injected."""

import sqlite3

import pytest

from conftest import ADMIN_PASS, ok, wait_until
from test_telegram_accounts import ENV
from test_telegram_chats import Scenario, chats, dlg, link_synced
from test_telegram_history import add_run, on_day
from test_telegram_runs import chat_ids, make_workflow, start, text_step, wait_status
from test_telegram_runs_ui import browser  # noqa: F401  (pytest fixture, used by name)

pw_sync = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.ui

API = "/api/telegram"
IMG = '<img src=x data-xss="1" onerror="window.__xss=1">'
ATTR = '" data-xss="1" onfocus="window.__xss=1" autofocus x="'
ATTR2 = "' data-xss='1' onmouseover='window.__xss=1' x='"
CLOSE = '</td></tr></table></textarea></select></option></button></div><b data-xss="1">bold</b>'
SCRIPT = "<script>window.__xss=1</script><svg data-xss=1 onload=window.__xss=1>"
NAMES = [IMG, ATTR, ATTR2, CLOSE, SCRIPT]


@pytest.fixture
def ui(browser, make_app, tmp_path):  # noqa: F811
    scn = Scenario(tmp_path / "fake_tg")
    items = [dlg(i, i) for i in range(1, 6)]
    items[0].update(first_name=IMG, last_name=CLOSE, username=ATTR, last_message=SCRIPT)
    items[1].update(first_name=ATTR2, last_name=ATTR, username=ATTR2, last_message=IMG)
    items[2].update(first_name=SCRIPT, username=CLOSE, last_message=CLOSE)
    scn.dialogs(items)
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir), TELEGRAM_RETRY_WAIT="0.3")
    api = app.client()
    acc = link_synced(api)
    ids = chat_ids(api, acc, 1001, 1002, 1003, 1004, 1005)
    ok(api.patch(f"{API}/accounts/{acc['id']}", json={"label": IMG}))
    ok(api.patch(f"{API}/chats/{ids[0]}", json={"notes": CLOSE + ATTR, "chat_status": "error"}))
    ok(api.patch(f"{API}/chats/{ids[1]}", json={"notes": SCRIPT}))
    wf_hostile = make_workflow(api, [text_step(CLOSE, 0), text_step(ATTR, 0), text_step(IMG + SCRIPT, 0)], name=IMG)
    make_workflow(api, [text_step("hi", 0)], name=ATTR)
    wf_live = make_workflow(api, [text_step("langsam", 120), text_step("danach", 0)], name=ATTR2)
    with sqlite3.connect(app.storage / "db.sqlite") as c:
        c.execute("update tg_account set tg_username=?, status_msg=?", (ATTR, IMG))
        c.execute("update tg_chat set error_reason=?, chat_status='error' where id=?", (SCRIPT + IMG, ids[0]))
        c.execute("update tg_chat set error_reason=?, chat_status='error' where id=?", (ATTR2, ids[2]))
    add_run(app, acc["id"], [(ids[0], "error", IMG + ATTR), (ids[1], "done", ""), (ids[2], "error", CLOSE), (ids[3], "skipped", "")],
            status="error", ended=on_day(2), name=SCRIPT, workflow_id=wf_hostile["id"])
    add_run(app, acc["id"], [(ids[0], "done", ""), (ids[1], "error", ATTR2)], status="stopped", ended=on_day(1), name=ATTR)
    with sqlite3.connect(app.storage / "db.sqlite") as c:
        c.execute("update tg_run set status_msg=? where id=(select max(id) from tg_run)", (IMG,))
    live = start(api, acc, wf_live, [ids[0], ids[1]])
    wait_until(lambda: ok(api.get(f"{API}/runs/{live['id']}"))["chat"], msg="the run to be working on a chat")
    contexts = []

    def open_page(lang="de", viewport=(1400, 1000), hash_="#telegram-dashboard"):
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

    yield app, api, scn, acc, ids, live, open_page
    for ctx in contexts:
        ctx.close()


def clean(page, where):
    """Nothing hostile became markup or an attribute, and nothing ran."""
    page.wait_for_timeout(350)       # an injected <img onerror> fires asynchronously
    found = page.evaluate("""() => ({
        xss: window.__xss === undefined ? null : window.__xss,
        injected: [...document.querySelectorAll('[data-xss]')].map(e => e.outerHTML.slice(0, 120)),
        scripts: [...document.scripts].filter(s => s.textContent.includes('__xss')).length,
        handlers: [...document.querySelectorAll('[onerror],[onload],[onmouseover],[onfocus]')].map(e => e.outerHTML.slice(0, 120)),
    })""")
    assert found == {"xss": None, "injected": [], "scripts": 0, "handlers": []}, f"{where}: {found}"


def tab(page, name):
    page.click(f'#tabs [data-tab="telegram-{name}"]')
    page.wait_for_selector(f"#tab-telegram-{name}:not([hidden])")
    page.wait_for_timeout(300)


def shows(page, selector, fragment):
    """The hostile text is visible as plain text (the check would pass vacuously if the page showed nothing)."""
    assert fragment in page.inner_text(selector), f"{fragment!r} not visible in {selector}"


@pytest.mark.parametrize("lang", ["de", "en"])
def test_hostile_text_is_inert_on_every_tab(ui, lang):
    app, api, scn, acc, ids, live, open_page = ui
    page, problems = open_page(lang)
    page.wait_for_selector("#tab-telegram-dashboard .kpi")
    shows(page, "#tab-telegram-dashboard", "data-xss")           # the live card names the hostile chat
    clean(page, "dashboard")

    tab(page, "accounts")
    page.wait_for_selector("#tab-telegram-accounts tbody tr")
    shows(page, "#tab-telegram-accounts", "data-xss")
    clean(page, "accounts")
    page.click('#tab-telegram-accounts [data-act="rename"]')
    page.wait_for_selector("#modal input[name=label]")
    assert page.input_value("#modal input[name=label]") == IMG        # the attribute value survived exactly, nothing broke out
    clean(page, "rename account dialog")
    page.click("#modal [data-close-modal]")

    tab(page, "chats")
    page.wait_for_selector("#tab-telegram-chats tbody tr[data-id]")
    shows(page, "#tab-telegram-chats tbody", "data-xss")
    clean(page, "chats")
    page.fill("#tab-telegram-chats input[data-f=q]", ATTR)           # the search echo
    page.wait_for_timeout(700)
    clean(page, "chats search")
    page.fill("#tab-telegram-chats input[data-f=q]", "")
    page.wait_for_timeout(700)
    page.click("#tab-telegram-chats tbody tr[data-id] >> nth=0 >> [data-act=edit]")
    page.wait_for_selector("#modal textarea[name=notes]")
    clean(page, "chat edit dialog")
    assert page.input_value("#modal textarea[name=notes]") in (CLOSE + ATTR, SCRIPT, "")      # textarea text round-trips
    page.click("#modal [data-close-modal]")
    for status in ("error", "done"):
        page.click(f'#tab-telegram-chats .tg-chip[data-status="{status}"]')
        page.wait_for_timeout(500)
        clean(page, f"chats filter {status}")
        page.click(f'#tab-telegram-chats .tg-chip[data-status="{status}"]')

    # a stranger writes right now: the live row must be inert as well
    scn.incoming(id=9001, first_name=IMG, last_name=ATTR, username=ATTR2, text=SCRIPT)
    wait_until(lambda: any(c["telegram_id"] == "9001" for c in chats(api)["items"]), msg="live chat stored")
    page.wait_for_timeout(1200)
    clean(page, "chats after a live message")
    scn.incoming(id=1001, first_name=ATTR, text=CLOSE)         # an existing chat updates
    page.wait_for_timeout(1200)
    clean(page, "chats after a live update")

    tab(page, "workflows")
    page.wait_for_selector("#tab-telegram-workflows .tg-wf-card")
    shows(page, "#tab-telegram-workflows", "data-xss")
    clean(page, "workflows")
    page.click("#tab-telegram-workflows .tg-wf-card >> nth=0")
    page.wait_for_selector("#tab-telegram-workflows textarea")
    clean(page, "workflow editor")
    texts = page.eval_on_selector_all("#tab-telegram-workflows textarea", "els => els.map(e => e.value)")
    assert texts == [CLOSE, ATTR, IMG + SCRIPT]                      # stored text comes back byte for byte
    page.click('#tab-telegram-workflows [data-act="back"]')
    page.wait_for_selector("#tab-telegram-workflows .tg-wf-card")
    page.click('#tab-telegram-workflows .tg-wf-card >> nth=1 >> [data-act="rename"]')
    page.wait_for_selector("#modal input")
    clean(page, "workflow rename dialog")
    page.keyboard.press("Escape")
    page.evaluate("document.querySelector('#modal-close, #modal [data-close-modal]')?.click()")

    tab(page, "runs")
    page.wait_for_selector("#tab-telegram-runs [data-live]")
    shows(page, "#tab-telegram-runs", "data-xss")
    clean(page, "runs tab live panel")
    ok(api.post(f"{API}/runs/{live['id']}/stop"))
    wait_status(api, live["id"], "stopped")
    page.wait_for_timeout(800)
    clean(page, "runs tab after the stop")
    tab(page, "chats")
    tab(page, "runs")
    page.wait_for_selector("#tab-telegram-runs [data-run-act=start]")
    for i in range(3):                                          # the flow preview of every hostile workflow
        page.select_option("#tab-telegram-runs select[data-form=workflow]", index=i + 1)
        page.wait_for_timeout(250)
        clean(page, f"runs workflow preview {i}")
    page.click("#tab-telegram-runs [data-run-act=preset][data-status=error]")
    page.wait_for_timeout(300)
    shows(page, "#tab-telegram-runs", "data-xss")
    clean(page, "runs chat picker")

    tab(page, "history")
    page.wait_for_selector("#tab-telegram-history tbody tr")
    shows(page, "#tab-telegram-history", "data-xss")
    clean(page, "history list")
    page.click('#tab-telegram-history [data-hist-act="open"] >> nth=1')            # the oldest run: hostile chat names and reasons
    page.wait_for_timeout(600)
    shows(page, "#tab-telegram-history", "data-xss")
    clean(page, "history detail")
    page.click('#tab-telegram-history [data-hist-act="errors"]')
    page.wait_for_timeout(400)
    clean(page, "history detail errors only")
    page.click('#tab-telegram-history [data-hist-act="back"]')
    page.wait_for_timeout(300)
    page.click('#tab-telegram-history [data-hist-act="cleanup"]')
    page.wait_for_selector("#modal")
    clean(page, "history cleanup dialog")

    # the stored text is untouched: escaping happens on display only
    assert ok(api.get(f"{API}/accounts"))[0]["label"] == IMG
    assert not problems, problems


def test_hostile_account_label_in_toasts_and_the_sync_banner_is_inert(ui):
    """The sync banner and its toast name the account, whose label is hostile here."""
    app, api, scn, acc, ids, live, open_page = ui
    ok(api.post(f"{API}/runs/{live['id']}/stop"))
    page, problems = open_page("en", hash_="#telegram-chats")
    page.wait_for_selector("#tab-telegram-chats tbody tr[data-id]")
    page.click("#tab-telegram-chats [data-act=sync]")
    page.wait_for_selector("#toasts .toast")
    assert "data-xss" in page.inner_text("#toasts")              # shown as text
    clean(page, "sync toast")
    assert not problems, problems
