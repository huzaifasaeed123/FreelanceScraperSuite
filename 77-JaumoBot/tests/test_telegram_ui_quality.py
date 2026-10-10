"""Telegram panel UI quality (Edge via Playwright, fake Telethon client, seeded data): every Telegram tab in German and
English, at 390 / 768 / 1300 px and in the dark and light theme, must fit the screen (no horizontal page overflow, nothing
poking out of its container), cope with empty / huge / hostile data, close its dialogs with Escape, leak no sockets or timers
when tabs are switched during a live run, survive a reload and browser back/forward, and keep the console clean.

Set TG_UI_SHOTS=<folder> to also write a screenshot of every checked page there."""

import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from conftest import ADMIN_PASS, ok, wait_until
from test_telegram_accounts import ENV
from test_telegram_chats import Scenario, dlg, link_synced
from test_telegram_runs import make_workflow, text_step

pw_sync = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.ui

API = "/api/telegram"
TABS = ["dashboard", "accounts", "chats", "workflows", "runs", "history"]
VIEWPORTS = {"phone": (390, 800), "tablet": (768, 900), "desktop": (1300, 900)}
SHOTS = os.environ.get("TG_UI_SHOTS")
LONG_NAME = ("Wolfeschlegelsteinhausenbergerdorff" * 4)[:80]   # as long as a workflow name may be, no break opportunity
LONG_CHAT_NAME = ("Wolfeschlegelsteinhausenbergerdorff" * 4)[:128]   # Telegram: 64 + 64 characters
LONG_TEXT = "Hallo, das ist ein sehr langer Text ohne Ende. " * 80 + "X" * 300      # 4,060 characters, the limit is 4,096
BIG = 5000

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

# Finds what does not fit: the page is wider than the window, or an element sticks out of the viewport (or is clipped by an
# ancestor that cannot scroll) while it is visible.
AUDIT = """
() => {
  const vw = document.documentElement.clientWidth, out = [];
  if (document.documentElement.scrollWidth > vw + 1) out.push(`page scrolls horizontally: ${document.documentElement.scrollWidth} > ${vw}`);
  if (document.body.scrollWidth > vw + 1) out.push(`body wider than window: ${document.body.scrollWidth} > ${vw}`);
  const root = document.querySelector('.tab:not(.hidden)') || document.body;
  const clipper = (el) => { for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
    const o = getComputedStyle(p).overflowX; if (o !== 'visible') return [p, o]; } return [null, 'visible']; };
  const label = (el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className && el.className.baseVal === undefined ? '.' + String(el.className).trim().split(/ +/).join('.') : '');
  for (const el of root.querySelectorAll('*')) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height || getComputedStyle(el).visibility === 'hidden') continue;
    const [box, mode] = clipper(el);
    if (r.right > vw + 1 || r.left < -1) {
      if (!box) out.push(`outside the window: ${label(el)} (${Math.round(r.left)}..${Math.round(r.right)} of ${vw}) "${(el.textContent || '').trim().slice(0, 40)}"`);
    }
    // a visible piece of text that an ancestor with overflow:hidden cuts off (truncating with an ellipsis is fine)
    if (box && (mode === 'hidden' || mode === 'clip') && getComputedStyle(el).textOverflow !== 'ellipsis' && getComputedStyle(box).textOverflow !== 'ellipsis'
        && [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) && r.right > box.getBoundingClientRect().right + 2)
      out.push(`text cut off by ${label(box)}: ${label(el)} "${(el.textContent || '').trim().slice(0, 40)}"`);
  }
  // content that sticks out of the card it belongs to (unless a scrolling container inside the card holds it)
  for (const el of root.querySelectorAll('.card *')) {
    const r = el.getBoundingClientRect(), card = el.closest('.card'), c = card.getBoundingClientRect();
    if (!r.width || !r.height || getComputedStyle(el).visibility === 'hidden' || !(el.textContent || '').trim()) continue;
    const [box] = clipper(el);
    if (r.right > c.right + 1 && !(box && card.contains(box) && /auto|scroll/.test(getComputedStyle(box).overflowX)) && out.length < 12)
      out.push(`sticks out of its card: ${label(el)} (right ${Math.round(r.right)} > ${Math.round(c.right)}) "${(el.textContent || '').trim().slice(0, 40)}"`);
  }
  for (const el of root.querySelectorAll('button, .btn, .badge, h1, h2, h3, label, th')) {
    if (el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).overflow !== 'visible' && getComputedStyle(el).textOverflow !== 'ellipsis')
      out.push(`text cut off in ${label(el)}: "${(el.textContent || '').trim().slice(0, 40)}"`);
  }
  return out.slice(0, 12);
}
"""


# --- seeding -----------------------------------------------------------------------------------------------------------

def sql(app, query, *args, many=None):
    with sqlite3.connect(app.storage / "db.sqlite", timeout=30) as c:
        if many is not None:
            c.executemany(query, many)
        else:
            return c.execute(query, args).fetchall()


def stamp(minutes_ago):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%d %H:%M:%S.%f")


def seed_big_chats(app, account_id, n=BIG):
    cols = ("account_id,telegram_id,access_hash,search_text,username,display_name,first_contact_at,last_contact_at,last_message,"
            "chat_status,messages_sent,last_processed_at,error_reason,notes,created_at")
    statuses = ["pending", "pending", "done", "error", "in_progress", "paused"]
    rows = []
    for i in range(n):
        name = f"Bulk Kontakt {i:05d}"
        rows.append((account_id, str(900000 + i), "1", name.casefold(), f"bulk{i}", name, stamp(60000 + i), stamp(i),
                     f"Nachricht {i}", statuses[i % len(statuses)], i % 5, stamp(i) if i % 3 == 0 else None,
                     "Telegram error: Flood" if i % 6 == 3 else "", "", stamp(60000)))
    sql(app, f"INSERT INTO tg_chat ({cols}) VALUES ({','.join('?' * 15)})", many=rows)


def seed_history(app, account_id, workflow, n=40):
    """n finished runs (the first one with 1,248 chats and a hostile workflow name) plus per-chat rows for the first."""
    snap = json.dumps({"name": workflow["name"], "steps": workflow["steps"]})
    cols = ("account_id,workflow_id,workflow_name,workflow_snapshot,status,total_chats,processed,success,errors,"
            "current_step_index,on_error,retries,wait_kind,status_msg,auto_resume,peer_floods,created_at,started_at,finished_at")
    statuses = ["done", "stopped", "error", "done"]
    rows = []
    for i in range(n):
        total = 1248 if i == 0 else 3 + i
        errors = 17 if i == 0 else i % 3
        name = ('<img src=x onerror="window.__xss=1"> ' + LONG_NAME)[:80] if i == 0 else f"Ablauf {i % 4}"
        rows.append((account_id, workflow["id"], name, snap, statuses[i % 4], total, total, total - errors, errors, 0, "next", 3, "",
                     "", 0, 0, stamp(60 * i + 90), stamp(60 * i + 89), stamp(60 * i + 1)))
    sql(app, f"INSERT INTO tg_run ({cols}) VALUES ({','.join('?' * 19)})", many=rows)
    run_id = sql(app, "SELECT min(id) FROM tg_run")[0][0]
    chat_ids = [r[0] for r in sql(app, "SELECT id FROM tg_chat WHERE account_id=? ORDER BY id LIMIT 1248", account_id)]
    rows = [(run_id, cid, pos, "error" if pos % 70 == 5 else "done", 3, "The user's privacy settings do not allow this message"
             if pos % 70 == 5 else "", stamp(500), stamp(499)) for pos, cid in enumerate(chat_ids)]
    sql(app, "INSERT INTO tg_run_chat (run_id,chat_id,position,status,steps_done,error_reason,started_at,processed_at) "
             "VALUES (?,?,?,?,?,?,?,?)", many=rows)
    return run_id


# --- fixtures ----------------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def browser():
    with pw_sync.sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="msedge")
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"Edge is not available: {e}")
        yield b
        b.close()


class Panel:
    """One browser page logged into the panel, with every problem it sees collected in `problems`."""

    def __init__(self, browser, app, lang="de", theme="dark", viewport=(1300, 900), hash_="", expected=()):
        self.app = app
        self.ctx = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]}, locale="en-US")
        self.ctx.add_init_script(f"try{{localStorage.setItem('lang','{lang}');localStorage.setItem('theme','{theme}')}}catch(e){{}}")
        self.ctx.add_init_script(COUNTERS)
        self.page = self.ctx.new_page()
        self.problems = []
        self.expected = tuple(expected)         # URL fragments whose 4xx answers are part of the test
        p = self.page
        p.on("pageerror", lambda e: self.problems.append(f"JS error: {e}"))
        p.on("console", lambda m: m.type == "error" and not self._expected(m.text) and self.problems.append(f"console: {m.text}"))
        p.on("response", lambda r: r.status >= 400 and not self._expected(r.url) and self.problems.append(f"HTTP {r.status} {r.url}"))
        self.dialogs, self.accept = [], True      # confirm() texts seen; answered with OK unless a test says otherwise
        p.on("dialog", lambda d: (self.dialogs.append(d.message), d.accept() if self.accept else d.dismiss()))
        p.goto(app.url + "/" + hash_)
        p.fill("input[name=username]", "admin")
        p.fill("input[name=password]", ADMIN_PASS)
        p.click("#login-form button[type=submit]")
        p.wait_for_selector("#app-view:not(.hidden)")

    def _expected(self, text):
        return any(e in text for e in self.expected)

    def goto_tab(self, tab, ready=None):
        self.page.evaluate(f"location.hash = '#telegram-{tab}'")
        self.page.wait_for_selector(f"#tab-telegram-{tab}:not(.hidden) .page-head", timeout=15000)
        if ready:
            self.page.wait_for_selector(ready, timeout=15000)
        self.page.wait_for_timeout(250)

    def sockets(self):
        return self.page.evaluate("window.__sockets.filter(w => w.url.includes('/ws/modules/telegram') && w.readyState <= 1).length")

    def intervals(self):
        return self.page.evaluate("window.__intervals.size")

    def audit(self, name):
        found = self.page.evaluate(AUDIT)
        if SHOTS:
            Path(SHOTS).mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(Path(SHOTS) / f"{name}.png"))
        return [f"{name}: {f}" for f in found]

    def close(self):
        self.ctx.close()


@pytest.fixture
def seeded(make_app, tmp_path):
    """A server with two accounts, ~60 linked chats (long and hostile names), 5,000 more chats, workflows (one with a
    4,060-character text and 30 steps) and 40 finished runs."""
    scn = Scenario(tmp_path / "fake_tg")
    items = [dlg(i, i % 30) for i in range(1, 61)]
    items[0].update(first_name='<img src=x onerror="window.__xss=1">', last_name="<b>fett</b>", username="xss")
    items[1].update(first_name=LONG_CHAT_NAME, last_name="", username="u" * 32, last_message=LONG_TEXT)
    items[2].update(first_name="Jürgen Größmann", last_name="Äöü", last_message="Schöne Grüße 😀 aus Köln")
    scn.dialogs(items)
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir), TELEGRAM_RETRY_WAIT="0.3")
    api = app.client()
    acc = link_synced(api)
    ok(api.patch(f"{API}/accounts/{acc['id']}", json={"label": ("Vertrieb " + LONG_NAME)[:60]}))
    seed_big_chats(app, acc["id"])
    short = make_workflow(api, [text_step("Hallo!", 10), text_step("Zweite Nachricht", 30), text_step("Tschüss", 0)], name="Neukontakt")
    make_workflow(api, [text_step(LONG_TEXT, 5)], name=LONG_NAME)
    make_workflow(api, [text_step(f"Schritt {i} mit etwas Text", i % 7) for i in range(30)], name="Dreißig Schritte")
    run_id = seed_history(app, acc["id"], short)
    panels = []

    def open_panel(**kw):
        panel = Panel(browser_of[0], app, **kw)
        panels.append(panel)
        return panel

    browser_of = [None]
    yield app, api, acc, scn, short, run_id, open_panel, browser_of
    for p in panels:
        p.close()


@pytest.fixture
def S(seeded, browser):
    app, api, acc, scn, wf, run_id, open_panel, browser_of = seeded
    browser_of[0] = browser

    class Ctx:
        pass
    c = Ctx()
    c.app, c.api, c.acc, c.scn, c.wf, c.run_id, c.open = app, api, acc, scn, wf, run_id, open_panel
    return c


# --- the layout matrix -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("size", list(VIEWPORTS))
def test_every_tab_fits_the_screen_in_both_languages_and_themes(S, size):
    problems = []
    for lang in ("de", "en"):
        for theme in ("dark", "light"):
            panel = S.open(lang=lang, theme=theme, viewport=VIEWPORTS[size])
            for tab in TABS:
                panel.goto_tab(tab)
                problems += panel.audit(f"{size}_{lang}_{theme}_{tab}")
            problems += panel.problems
            panel.close()
    assert not problems, "\n".join(problems)


# Tables may scroll sideways on a phone, but on a desktop window every column of every table must be visible without it.
SCROLLERS = """
() => [...document.querySelectorAll('.tab:not(.hidden) table')].map((t) => {
  let p = t.parentElement; while (p && p.scrollWidth <= p.clientWidth + 1 && !/auto|scroll/.test(getComputedStyle(p).overflowX)) p = p.parentElement;
  return p && p.scrollWidth > p.clientWidth + 1 ? `${t.className}: ${p.scrollWidth} wide in ${p.clientWidth}` : null;
}).filter(Boolean)
"""


@pytest.mark.parametrize("lang", ["de", "en"])
def test_no_table_needs_sideways_scrolling_on_a_desktop(S, lang):
    ok(S.api.patch(f"{API}/accounts/{S.acc['id']}", json={"label": "Vertrieb 1"}))      # ordinary names: nothing long to blame
    sql(S.app, "UPDATE tg_run SET workflow_name = 'Neukontakt'")
    panel = S.open(lang=lang, viewport=VIEWPORTS["desktop"])
    problems = []
    for tab in TABS:
        panel.goto_tab(tab)
        problems += [f"{tab}: {f}" for f in panel.page.evaluate(SCROLLERS)]
    assert not problems, "\n".join(problems)


# --- helpers for the interactive tests -----------------------------------------------------------------------------------

def pending_ids(S, n):
    """Database ids of the first n synced (not bulk) chats."""
    items = ok(S.api.get(f"{API}/chats", params={"account_id": S.acc["id"], "limit": 100, "q": "User"}))["items"]
    return [c["id"] for c in items][:n]


def start_run(S, workflow=None, n=3):
    return ok(S.api.post(f"{API}/runs", json={"account_id": S.acc["id"], "workflow_id": (workflow or S.wf)["id"],
                                              "chat_ids": pending_ids(S, n)}))


def tab_text(panel, tab):
    return panel.page.inner_text(f"#tab-telegram-{tab}")


# --- empty states ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("size", ["phone", "desktop"])
def test_empty_panel_shows_helpful_empty_states(make_app, browser, size):
    app = make_app(**ENV)
    problems = []
    for lang in ("de", "en"):
        panel = Panel(browser, app, lang=lang, viewport=VIEWPORTS[size])
        for tab in TABS:
            panel.goto_tab(tab)
            problems += panel.audit(f"empty_{size}_{lang}_{tab}")
            text = tab_text(panel, tab)
            assert not re.search(r"undefined|NaN|\[object", text), f"{tab}/{lang}: placeholder text leaks: {text!r}"
            if tab in ("accounts", "chats", "runs"):
                assert panel.page.locator(f"#tab-telegram-{tab} .empty").count() == 1, f"{tab}/{lang}: no empty state"
                assert ("Noch kein Konto" if lang == "de" else "No account linked") in text
            if tab == "workflows":
                assert ("Noch kein Ablauf" if lang == "de" else "No workflow saved") in text
            if tab == "history":
                assert ("Keine Durchläufe" if lang == "de" else "No runs") in text
        problems += panel.problems
        panel.close()
    assert not problems, "\n".join(problems)


# --- long and hostile data -----------------------------------------------------------------------------------------------

# Is the element fully inside the part of its scrolling container that is on screen (no sideways scrolling needed to reach it)?
REACHABLE = """
(sel) => {
  const el = document.querySelector(sel); if (!el) return 'missing';
  let box = el.parentElement; while (box && !/auto|scroll/.test(getComputedStyle(box).overflowX)) box = box.parentElement;
  const r = el.getBoundingClientRect(), c = (box || document.documentElement).getBoundingClientRect();
  return r.right <= Math.min(c.right, document.documentElement.clientWidth) + 1 ? null : `ends at x=${Math.round(r.right)}, the visible area ends at x=${Math.round(c.right)}`;
}
"""


def test_long_names_do_not_push_the_row_actions_out_of_reach(S):
    """A 60-character account label and an 80-character workflow name (both allowed) must wrap or shorten, so the buttons and
    the status column stay visible on a desktop without scrolling sideways."""
    panel = S.open(viewport=VIEWPORTS["desktop"])
    panel.goto_tab("accounts", ready="#tab-telegram-accounts tbody tr")
    problems = []
    gone = panel.page.evaluate(REACHABLE, "#tab-telegram-accounts [data-act=rename]")
    if gone:
        problems.append(f"accounts: the rename button {gone}")
    panel.goto_tab("history", ready="#tab-telegram-history tbody tr[data-run]")
    gone = panel.page.evaluate(REACHABLE, "#tab-telegram-history tbody tr td:nth-child(9)")
    if gone:
        problems.append(f"history: the status column {gone}")
    assert not problems, "\n".join(problems)


def test_hostile_and_unusual_text_is_shown_as_text_everywhere(S):
    panel = S.open(viewport=VIEWPORTS["desktop"])
    panel.goto_tab("chats", ready="#tab-telegram-chats tbody tr")
    panel.page.fill("#tab-telegram-chats input[data-f=q]", "xss")
    panel.page.wait_for_function("document.querySelectorAll('#tab-telegram-chats tbody tr').length === 1")
    text = tab_text(panel, "chats")
    assert "<img src=x" in text and "<b>fett</b>" in text
    panel.goto_tab("history", ready="#tab-telegram-history tbody tr[data-run]")
    assert "<img src=x" in tab_text(panel, "history")
    panel.page.click("#tab-telegram-history tbody tr[data-run]")
    panel.page.wait_for_selector("#tab-telegram-history [data-detail-rows] tr")
    assert "<img src=x" in tab_text(panel, "history")
    for tab in ("dashboard", "accounts", "workflows", "runs"):
        panel.goto_tab(tab)
    assert panel.page.evaluate("window.__xss") is None, "a hostile name was run as HTML"
    assert panel.page.locator("img[src='x']").count() == 0
    assert not panel.problems, panel.problems


def test_numbers_use_the_thousands_separator_of_the_language(S):
    for lang, total, big, thousands in (("de", "5.060", "1.248", "1.728"), ("en", "5,060", "1,248", "1,728")):
        panel = S.open(lang=lang, viewport=VIEWPORTS["desktop"])
        panel.goto_tab("dashboard", ready="#tab-telegram-dashboard .kpi-value")
        text = tab_text(panel, "dashboard")
        assert total in text and thousands in text, f"{lang}: {text!r}"
        panel.goto_tab("history", ready="#tab-telegram-history tbody tr[data-run]")
        assert big in tab_text(panel, "history")
        panel.goto_tab("chats", ready="#tab-telegram-chats tbody tr")
        assert thousands in tab_text(panel, "chats")                  # the "not processed yet" chip
        panel.close()


def test_five_thousand_chats_page_and_select_without_freezing(S):
    panel = S.open(viewport=VIEWPORTS["desktop"])
    page = panel.page
    panel.goto_tab("chats", ready="#tab-telegram-chats tbody tr")
    assert page.locator("#tab-telegram-chats tbody tr").count() <= 200, "the table must page, not draw 5,000 rows"
    assert re.search(r"5\.060", page.inner_text("#tab-telegram-chats [data-showing]"))
    page.select_option("#tab-telegram-chats select[data-per]", "200")
    page.wait_for_function("document.querySelectorAll('#tab-telegram-chats tbody tr').length === 200")
    page.click("#tab-telegram-chats [data-pg='1']")
    page.wait_for_function("/201/.test(document.querySelector('#tab-telegram-chats [data-showing]').textContent)")
    # selecting all unprocessed chats spans every page and is counted with the separator
    page.click("#tab-telegram-chats [data-act=select-pending]")
    page.wait_for_function("/1\\.728 Chats/.test(document.querySelector('#tab-telegram-chats .tg-bar').textContent)", timeout=15000)
    assert not panel.problems, panel.problems


# --- dialogs: Escape and focus --------------------------------------------------------------------------------------------

def dialog_openers(panel):
    """(name, tab, how to open it) for every Telegram dialog that can be opened without side effects."""
    p = panel.page
    return [
        ("link account", "accounts", lambda: p.click("#tab-telegram-accounts [data-act=add]")),
        ("rename account", "accounts", lambda: p.click("#tab-telegram-accounts tbody [data-act=rename]")),
        ("edit chat", "chats", lambda: p.click("#tab-telegram-chats tbody tr [data-act=edit]")),
        ("rename workflow", "workflows", lambda: p.click("#tab-telegram-workflows .tg-wf-card [data-act=rename]")),
        ("unused files", "workflows", lambda: p.click("#tab-telegram-workflows [data-act=cleanup]")),
        ("clean up runs", "history", lambda: p.click("#tab-telegram-history [data-hist-act=cleanup]")),
    ]


def test_every_dialog_closes_with_escape_and_takes_the_focus(S):
    panel = S.open(viewport=VIEWPORTS["desktop"])
    p = panel.page
    ready = {"accounts": "tbody tr", "chats": "tbody tr[data-id]", "workflows": ".tg-wf-card", "history": "tbody tr[data-run]"}
    problems = []
    for name, tab, opener in dialog_openers(panel):
        panel.goto_tab(tab, ready=f"#tab-telegram-{tab} {ready[tab]}")
        opener()
        try:
            p.wait_for_selector("#modal:not(.hidden)", timeout=5000)
        except Exception:  # noqa: BLE001
            problems.append(f"{name}: the dialog did not open")
            continue
        if not p.evaluate("!!document.activeElement && !!document.activeElement.closest('#modal') && document.activeElement.id !== 'modal-close'"):
            problems.append(f"{name}: keyboard focus is not on a field of the dialog (on {p.evaluate('document.activeElement.outerHTML.slice(0, 60)')})")
        p.keyboard.press("Escape")
        if not p.evaluate("document.querySelector('#modal').classList.contains('hidden')"):
            problems.append(f"{name}: Escape did not close the dialog")
            p.click("#modal-close")
        assert p.evaluate("document.querySelector('#modal-body').innerHTML === ''"), f"{name}: the dialog content stays behind"
    assert not problems, "\n".join(problems)
    assert not panel.problems, panel.problems


def test_start_confirmation_closes_with_escape_and_starts_nothing(S):
    panel = S.open(viewport=VIEWPORTS["desktop"])
    p = panel.page
    panel.goto_tab("runs", ready="#tab-telegram-runs tbody tr[data-id]")
    p.select_option("#tab-telegram-runs select[data-form=workflow]", label="Neukontakt")
    p.click("#tab-telegram-runs [data-run-act=preset][data-status=pending]")
    p.wait_for_function("/Chats/.test(document.querySelector('#tab-telegram-runs [data-start-count]').textContent) && !/^0 /.test(document.querySelector('#tab-telegram-runs [data-start-count]').textContent)")
    p.click("#tab-telegram-runs [data-run-act=start]")
    p.wait_for_selector("#modal:not(.hidden) [data-go]")
    assert p.evaluate("!!document.activeElement.closest('#modal')"), "focus is not inside the confirmation dialog"
    p.keyboard.press("Escape")
    p.wait_for_selector("#modal", state="hidden")
    p.wait_for_timeout(500)
    assert ok(S.api.get(f"{API}/runs", params={"status": "queued,running,paused"}))["total"] == 0
    assert not panel.problems, panel.problems


def test_tab_key_stays_inside_an_open_dialog(S):
    panel = S.open(viewport=VIEWPORTS["desktop"])
    p = panel.page
    panel.goto_tab("accounts", ready="#tab-telegram-accounts tbody tr")
    p.click("#tab-telegram-accounts [data-act=add]")
    p.wait_for_selector("#modal input[name=phone]")
    escaped = []
    for _ in range(25):
        p.keyboard.press("Tab")
        if not p.evaluate("!!document.activeElement.closest('#modal')"):
            escaped.append(p.evaluate("document.activeElement.outerHTML.slice(0, 70)"))
    assert not escaped, f"Tab moved the focus behind the dialog {len(escaped)} times, e.g. onto {escaped[0]}"


# --- workflow editor: keyboard instead of drag and drop, layout with 30 steps and a 4,060-character text ----------------------

def open_card(panel, name):
    p = panel.page
    panel.goto_tab("workflows", ready="#tab-telegram-workflows .tg-wf-card")
    card = p.locator("#tab-telegram-workflows .tg-wf-card", has=p.locator("b", has_text=name)).first
    card.focus()
    p.keyboard.press("Enter")
    p.wait_for_selector("#tab-telegram-workflows .tg-editor")


def test_steps_can_be_reordered_and_saved_with_the_keyboard_only(S):
    panel = S.open(viewport=VIEWPORTS["desktop"])
    p = panel.page
    open_card(panel, "Dreißig Schritte")
    assert p.locator("#tab-telegram-workflows .tg-step").count() == 30
    first = p.locator("#tab-telegram-workflows .tg-step").nth(0)
    first.locator("[data-act=down]").focus()
    p.keyboard.press("Enter")
    p.keyboard.press("Enter")                    # the focus follows the moved step, so the second press moves it on
    texts = p.eval_on_selector_all("#tab-telegram-workflows .tg-step textarea", "els => els.slice(0, 4).map(e => e.value)")
    assert texts[0].startswith("Schritt 1 ") and texts[1].startswith("Schritt 2 ") and texts[2].startswith("Schritt 0 "), texts
    assert p.evaluate("document.activeElement.dataset.act") in ("down", "up")
    assert p.evaluate("document.activeElement.closest('.tg-step').dataset.i") == "2", "the focus did not follow the moved step"
    assert p.locator("#tab-telegram-workflows [data-dirty]:not(.hidden)").count() == 1, "no 'unsaved changes' hint"
    p.focus("#tab-telegram-workflows [data-act=save]")
    p.keyboard.press("Enter")
    wf = wait_until(lambda: next(w for w in ok(S.api.get(f"{API}/workflows")) if w["name"] == "Dreißig Schritte")
                    if ok(S.api.get(f"{API}/workflows")) else None, msg="saved workflow")
    assert [s["content"][:10] for s in wf["steps"][:3]] == ["Schritt 1 ", "Schritt 2 ", "Schritt 0 "]
    assert not panel.problems, panel.problems


def test_add_menu_works_by_keyboard_and_escape_returns_the_focus(S):
    panel = S.open(viewport=VIEWPORTS["desktop"])
    p = panel.page
    open_card(panel, "Neukontakt")
    p.focus("#tab-telegram-workflows [data-act=add-toggle]")
    p.keyboard.press("Enter")
    p.wait_for_selector("#tab-telegram-workflows .tg-menu")
    assert p.evaluate("document.activeElement.hasAttribute('data-add')"), "the menu does not take the focus"
    p.keyboard.press("Escape")
    assert p.locator("#tab-telegram-workflows .tg-menu").count() == 0
    assert p.evaluate("document.activeElement.dataset.act") == "add-toggle"
    p.keyboard.press("Enter")
    p.keyboard.press("Enter")                   # first menu entry: a text step
    assert p.locator("#tab-telegram-workflows .tg-step").count() == 4
    assert p.evaluate("document.activeElement.tagName") == "TEXTAREA", "the new step does not take the focus"


def test_leaving_the_editor_with_unsaved_changes_asks_first(S):
    panel = S.open(viewport=VIEWPORTS["desktop"])
    p = panel.page
    open_card(panel, "Neukontakt")
    p.fill("#tab-telegram-workflows .tg-step textarea >> nth=0", "geändert")
    panel.accept = False
    p.click("#tab-telegram-workflows [data-act=back]")
    assert panel.dialogs, "no confirmation although the workflow was changed"
    assert p.locator("#tab-telegram-workflows .tg-editor").count() == 1, "the editor closed although the operator said no"
    # moving to another tab with changes is not silently lost either
    panel.accept = True
    p.click("#tab-telegram-workflows [data-act=back]")
    p.wait_for_selector("#tab-telegram-workflows .tg-wf-card")


@pytest.mark.parametrize("size", list(VIEWPORTS))
def test_editor_fits_with_thirty_steps_and_a_very_long_text(S, size):
    problems = []
    for lang in ("de", "en"):
        panel = S.open(lang=lang, viewport=VIEWPORTS[size])
        for name in ("Dreißig Schritte", LONG_NAME):
            open_card(panel, name)
            problems += panel.audit(f"editor_{size}_{lang}_{name[:6]}")
            panel.page.click("#tab-telegram-workflows [data-act=back]")
        problems += panel.problems
        panel.close()
    assert not problems, "\n".join(problems)


# --- a live run: sockets, timers, reload, navigation ---------------------------------------------------------------------

LIVE = "#tab-telegram-runs [data-live]"


def test_tab_switching_during_a_live_run_leaks_no_sockets_or_timers(S):
    start_run(S)
    panel = S.open(viewport=VIEWPORTS["desktop"])
    p = panel.page
    panel.goto_tab("runs", ready=LIVE)
    assert panel.sockets() == 1
    base_intervals = panel.intervals()
    for _ in range(3):
        for tab in TABS:
            panel.goto_tab(tab)
        panel.goto_tab("runs", ready=LIVE)
    assert panel.sockets() == 1, "a tab switch left an extra module socket open"
    assert p.evaluate("window.__sockets.length") <= 2, "tab switches opened new sockets"
    assert panel.intervals() == base_intervals, f"timers piled up: {base_intervals} -> {panel.intervals()}"
    # on a tab without a live view the run's countdown timer is gone
    panel.goto_tab("chats", ready="#tab-telegram-chats tbody tr")
    assert panel.intervals() < base_intervals
    assert not panel.problems, panel.problems


def test_the_dashboard_follows_a_live_run_without_a_reload(S):
    quick = make_workflow(S.api, [text_step("a", 1), text_step("b", 1)], name="Schnell")
    panel = S.open(viewport=VIEWPORTS["desktop"])
    panel.goto_tab("dashboard", ready="#tab-telegram-dashboard .kpi-value")
    start_run(S, quick, n=3)
    panel.page.wait_for_function("/Schnell/.test(document.querySelector('#tab-telegram-dashboard').innerText)", timeout=15000)
    panel.page.wait_for_function("/Keiner|None/.test(document.querySelector('#tab-telegram-dashboard').innerText) === false", timeout=5000)
    panel.page.wait_for_function("document.querySelector('#tab-telegram-dashboard').innerText.includes('Schnell') && "
                                 "/FERTIG|FINISHED/.test(document.querySelector('#tab-telegram-dashboard').innerText)", timeout=40000)
    assert not panel.problems, panel.problems


def test_reloading_the_page_during_a_run_brings_the_live_panel_back(S):
    run = start_run(S)
    panel = S.open(viewport=VIEWPORTS["desktop"], hash_="#telegram-runs")
    p = panel.page
    p.wait_for_selector(LIVE)
    p.wait_for_function("/in \\d+ (Sekunde|Sekunden)|in \\d+ (s|min)|sendet/.test(document.querySelector('#tab-telegram-runs [data-count]').textContent)")
    for _ in range(2):
        p.reload()
        p.wait_for_selector(LIVE, timeout=15000)
        assert f"Neukontakt" in p.inner_text(f"{LIVE} [data-wf]")
        assert p.inner_text(f"{LIVE} [data-badge]").strip() in ("AKTIV", "PAUSIERT")
        assert re.search(r"/ 3", p.inner_text(f"{LIVE} [data-counts]"))
        assert panel.sockets() == 1
    ok(S.api.post(f"{API}/runs/{run['id']}/stop"))
    p.wait_for_function("document.querySelector('#tab-telegram-runs [data-badge]').textContent.trim() === 'GESTOPPT'", timeout=15000)
    assert not panel.problems, panel.problems


def test_back_and_forward_follow_the_hash_routes(S):
    panel = S.open(viewport=VIEWPORTS["desktop"], hash_="#telegram-accounts")
    p = panel.page
    p.wait_for_selector("#tab-telegram-accounts:not(.hidden) tbody tr")
    path = ["chats", "workflows", "runs", "history", "dashboard"]
    for tab in path:
        p.evaluate(f"location.hash = '#telegram-{tab}'")
        p.wait_for_selector(f"#tab-telegram-{tab}:not(.hidden) .page-head")

    def visible_tabs():
        return p.evaluate("[...document.querySelectorAll('.tab:not(.hidden)')].map(e => e.id)")

    for tab in reversed(["accounts"] + path[:-1]):
        p.go_back()
        p.wait_for_selector(f"#tab-telegram-{tab}:not(.hidden) .page-head")
        assert visible_tabs() == [f"tab-telegram-{tab}"], (tab, visible_tabs())
        assert p.url.endswith(f"#telegram-{tab}")
        assert p.evaluate(f"document.querySelector('#tabs [data-tab=\"telegram-{tab}\"]').classList.contains('active')"), f"{tab}: sidebar item not highlighted"
    for tab in path[:3]:
        p.go_forward()
        p.wait_for_selector(f"#tab-telegram-{tab}:not(.hidden) .page-head")
        assert visible_tabs() == [f"tab-telegram-{tab}"]
    # a hash that does not exist falls back to a real page instead of a blank screen
    p.evaluate("location.hash = '#telegram-nonsense'")
    p.wait_for_timeout(500)
    assert p.evaluate("document.querySelectorAll('.tab:not(.hidden)').length") == 1
    assert not panel.problems, panel.problems


def test_sidebar_clicks_keep_the_address_so_a_reload_returns_to_the_same_tab(S):
    panel = S.open(viewport=VIEWPORTS["desktop"])
    p = panel.page
    for tab in ("history", "workflows", "chats"):
        p.click(f"#tabs [data-tab='telegram-{tab}']")
        p.wait_for_selector(f"#tab-telegram-{tab}:not(.hidden) .page-head")
        assert p.url.endswith(f"#telegram-{tab}")
        p.reload()
        p.wait_for_selector(f"#tab-telegram-{tab}:not(.hidden) .page-head", timeout=15000)
        assert p.evaluate("document.querySelectorAll('.tab:not(.hidden)').length") == 1
    assert not panel.problems, panel.problems


# --- errors and loading ---------------------------------------------------------------------------------------------------

def test_a_rejected_action_shows_a_readable_message_in_both_languages(make_app, browser):
    app = make_app(**ENV)
    api = app.client()
    make_workflow(api, [text_step("x")], name="Eins")
    make_workflow(api, [text_step("y")], name="Zwei")
    for lang, expected in (("de", "Ein Ablauf mit diesem Namen existiert bereits"), ("en", "A workflow with this name already exists")):
        panel = Panel(browser, app, lang=lang, expected=("status of 4", "/api/telegram/workflows/"), hash_="#telegram-workflows")
        p = panel.page
        p.wait_for_selector("#tab-telegram-workflows .tg-wf-card")
        p.locator("#tab-telegram-workflows .tg-wf-card", has=p.locator("b", has_text="Zwei")).locator("[data-act=rename]").click()
        p.fill("#tg-wf-rename input[name=name]", "Eins")
        p.click("#tg-wf-rename [type=submit]")
        p.wait_for_function("document.querySelector('#tg-wf-rename .error').textContent.length > 0")
        assert p.inner_text("#tg-wf-rename .error") == expected
        p.keyboard.press("Escape")
        assert panel.problems == []
        panel.close()


def test_an_unreachable_server_gives_a_message_not_a_blank_tab(S):
    panel = S.open(viewport=VIEWPORTS["desktop"], expected=("ERR_FAILED", "Failed to load resource", "Failed to fetch"))
    p = panel.page
    panel.goto_tab("dashboard")
    p.route("**/api/telegram/chats*", lambda r: r.abort())
    p.route("**/api/telegram/runs*", lambda r: r.abort())
    for tab in ("chats", "history"):
        p.evaluate(f"location.hash = '#telegram-{tab}'")
        p.wait_for_timeout(1500)
        assert not [e for e in panel.problems if e.startswith("JS error")], panel.problems
        shown = p.evaluate("[document.querySelector('#toasts').innerText, document.querySelector('.tab:not(.hidden)').innerText].join(' ')")
        assert re.search(r"fehl|error|erreicht|reach|failed|nicht|unavailable|Fehler", shown, re.I), f"{tab}: the failure is not shown: {shown!r}"
        assert p.evaluate("document.querySelector('.tab:not(.hidden)').innerText.trim().length") > 0


def test_a_slow_server_shows_something_while_a_tab_loads(S):
    panel = S.open(viewport=VIEWPORTS["desktop"])
    p = panel.page
    held = []
    p.route("**/api/telegram/**", lambda r: held.append(r))
    blank = []
    for tab in TABS:
        if tab == "dashboard":
            continue
        p.evaluate(f"location.hash = '#telegram-{tab}'")
        p.wait_for_timeout(700)
        if not p.evaluate(f"document.querySelector('#tab-telegram-{tab}').innerText.trim().length"):
            blank.append(tab)
    p.unroute("**/api/telegram/**")
    for r in held:
        try:
            r.continue_()
        except Exception:  # noqa: BLE001 — a request of an abandoned tab
            pass
    assert not blank, f"tabs that stay completely blank while the server is slow: {blank}"


# --- language and theme switching on the spot ----------------------------------------------------------------------------------

GERMAN = re.compile(r"\b(Konto|Konten|Ablauf|Abläufe|Schritte?|Fehler|Abbrechen|Speichern|Löschen|Alle|Noch|Durchlauf|Durchläufe|Zurück|Weiter|"
                    r"ausgewählt|Auswahl|Suchen|Nachricht|Bearbeitet|Fertig)\b")
ENGLISH = re.compile(r"\b(Cancel|Save|Delete|Loading|Previous|Next|Selected|successful|Workflows?|Accounts?|Search|Select|Edit|Steps?|Errors?)\b")
SEEDED = re.compile(r"Dreißig Schritte|Schritt \d+ mit etwas Text|Neukontakt|Ablauf \d|Nachricht \d+|Vertrieb|Bulk Kontakt \d+|Zweite Nachricht|"
                    r"Hallo[^\n]*|Tschüss|Wolfeschlegel\w*|Langer Text|Jürgen|Größmann|Schöne Grüße[^\n]*|Kontakt|Telegram error: Flood|<[^>\n]+>|fett|User\d+|hello \d+")


def test_switching_language_on_the_spot_translates_every_tab(S):
    start_run(S)
    panel = S.open(lang="de", viewport=VIEWPORTS["desktop"])
    p = panel.page
    problems = []
    for tab in TABS:
        panel.goto_tab(tab)
        p.wait_for_timeout(500)
        if tab == "history":
            p.click("#tab-telegram-history tbody tr[data-run]")
            p.wait_for_selector("#tab-telegram-history [data-detail-rows] tr")
        leftovers = lambda text, rx: sorted(set(rx.findall(SEEDED.sub(" ", text))))   # noqa: E731
        german = leftovers(tab_text(panel, tab), ENGLISH)
        if german:
            problems.append(f"German {tab}: English words {german}")
        p.click("#top-user")
        p.click("#menu-lang")
        p.wait_for_timeout(900)
        english = leftovers(tab_text(panel, tab), GERMAN)
        if english:
            problems.append(f"English {tab}: German words {english}")
        p.click("#top-user")
        p.click("#menu-lang")                                    # back to German for the next tab
        p.wait_for_timeout(300)
    assert not problems, "\n".join(problems)
    assert not panel.problems, panel.problems


# luminance contrast of every visible text node against what is behind it
CONTRAST = """
() => {
  const cv = document.createElement('canvas').getContext('2d', { willReadFrequently: true });
  const rgba = (c) => { cv.clearRect(0, 0, 1, 1); cv.fillStyle = '#000'; cv.fillStyle = c; cv.fillRect(0, 0, 1, 1); const d = cv.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2], d[3] / 255]; };
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const behind = (el) => { const layers = []; for (let n = el; n; n = n.parentElement) { const c = rgba(getComputedStyle(n).backgroundColor); if (c[3] > 0) layers.push(c); if (c[3] >= 1) break; }
    let base = [255, 255, 255]; if (!layers.length || layers[layers.length - 1][3] < 1) base = rgba(getComputedStyle(document.body).backgroundColor).slice(0, 3);
    for (const c of layers.reverse()) base = base.map((v, i) => c[i] * c[3] + v * (1 - c[3])); return base; };
  const out = [], seen = new Set();
  for (const el of document.querySelectorAll('.tab:not(.hidden) *')) {
    if (![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
    const st = getComputedStyle(el), r = el.getBoundingClientRect();
    if (!r.width || !r.height || st.visibility === 'hidden' || st.opacity === '0' || el.closest('[disabled]')) continue;
    const fg = rgba(st.color), bg = behind(el), f = fg.slice(0, 3).map((v, i) => v * fg[3] + bg[i] * (1 - fg[3]));
    const [a, b] = [lum(f), lum(bg)], ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    const key = el.tagName + '.' + el.className + st.color + st.backgroundColor;
    if (ratio < 3 && !seen.has(key)) { seen.add(key); out.push(`${ratio.toFixed(2)} ${el.tagName.toLowerCase()}.${String(el.className).trim()} "${el.textContent.trim().slice(0, 30)}"`); }
  }
  return out.slice(0, 10);
}
"""


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_text_is_readable_in_both_themes(S, theme):
    start_run(S)
    panel = S.open(theme=theme, viewport=VIEWPORTS["desktop"])
    problems = []
    for tab in TABS:
        panel.goto_tab(tab)
        panel.page.wait_for_timeout(400)
        problems += [f"{theme} {tab}: contrast {f}" for f in panel.page.evaluate(CONTRAST)]
    assert not problems, "\n".join(problems)


def test_theme_switch_repaints_a_loaded_tab_in_place(S):
    panel = S.open(theme="dark", viewport=VIEWPORTS["desktop"])
    p = panel.page
    panel.goto_tab("history", ready="#tab-telegram-history tbody tr[data-run]")
    dark = p.evaluate("getComputedStyle(document.querySelector('#tab-telegram-history .card')).backgroundColor")
    p.click("#top-user")
    p.click("#menu-theme")
    p.wait_for_timeout(300)
    assert p.evaluate("document.documentElement.dataset.theme") == "light"
    assert p.evaluate("getComputedStyle(document.querySelector('#tab-telegram-history .card')).backgroundColor") != dark
    assert panel.audit("theme_switch_history") == []
    assert not panel.problems, panel.problems


# --- the screens a run goes through, at every width ----------------------------------------------------------------------

@pytest.mark.parametrize("size", list(VIEWPORTS))
def test_start_form_live_panel_and_details_fit_at_every_width(S, size):
    long_flow = next(w for w in ok(S.api.get(f"{API}/workflows")) if w["name"] == LONG_NAME)
    problems = []
    for lang in ("de", "en"):
        panel = S.open(lang=lang, viewport=VIEWPORTS[size])
        p = panel.page
        # 1. the start form with the 4,060-character workflow chosen and chats selected
        panel.goto_tab("runs", ready="#tab-telegram-runs tbody tr[data-id]")
        p.select_option("#tab-telegram-runs select[data-form=workflow]", value=str(long_flow["id"]))
        p.click("#tab-telegram-runs [data-run-act=preset][data-status=pending]")
        p.wait_for_function("!/^0 /.test(document.querySelector('#tab-telegram-runs [data-start-count]').textContent)")
        problems += panel.audit(f"form_{size}_{lang}")
        p.click("#tab-telegram-runs [data-run-act=start]")
        p.wait_for_selector("#modal:not(.hidden) [data-go]")
        problems += panel.audit(f"confirm_{size}_{lang}")
        p.keyboard.press("Escape")
        # 2. the live panel, running and paused, with the hostile chat first
        run = start_run(S, long_flow, n=3)
        p.reload()
        p.wait_for_selector(LIVE, timeout=15000)
        p.wait_for_timeout(600)
        problems += panel.audit(f"live_{size}_{lang}")
        ok(S.api.post(f"{API}/runs/{run['id']}/pause"))
        p.wait_for_function("/PAUS/.test(document.querySelector('#tab-telegram-runs [data-badge]').textContent)", timeout=15000)
        problems += panel.audit(f"paused_{size}_{lang}")
        ok(S.api.post(f"{API}/runs/{run['id']}/resume"))
        # 3. the run's details in the history, with 1,248 chats and a 100-row page
        panel.goto_tab("history", ready="#tab-telegram-history tbody tr[data-run]")
        p.click("#tab-telegram-history tbody tr[data-run]:has-text('1.248'), #tab-telegram-history tbody tr[data-run]:has-text('1,248')")
        p.wait_for_selector("#tab-telegram-history [data-detail-rows] tr")
        assert p.locator("#tab-telegram-history [data-detail-rows] tr").count() == 100
        problems += panel.audit(f"detail_{size}_{lang}")
        p.click("#tab-telegram-history [data-hist-act=errors]")
        p.wait_for_function("document.querySelectorAll('#tab-telegram-history [data-detail-rows] tr').length === 18")      # 1248 // 70 + 1 failed chats
        problems += panel.audit(f"detail_errors_{size}_{lang}")
        problems += panel.problems
        panel.close()
        ok(S.api.post(f"{API}/runs/{run['id']}/stop"))
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("size", list(VIEWPORTS))
def test_account_dialog_and_chat_dialog_fit_at_every_width(S, size):
    problems = []
    panel = S.open(viewport=VIEWPORTS[size])
    p = panel.page
    panel.goto_tab("accounts", ready="#tab-telegram-accounts tbody tr")
    p.click("#tab-telegram-accounts [data-act=add]")
    p.wait_for_selector("#modal input[name=phone]")
    problems += panel.audit(f"wizard_{size}")
    p.keyboard.press("Escape")
    panel.goto_tab("chats", ready="#tab-telegram-chats tbody tr[data-id]")
    p.click("#tab-telegram-chats tbody tr [data-act=edit]")
    p.wait_for_selector("#modal:not(.hidden) textarea, #modal:not(.hidden) select")
    problems += panel.audit(f"chat_edit_{size}")
    p.keyboard.press("Escape")
    problems += panel.problems
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("lang,expected", [("de", "1 Konto, 1 online"), ("en", "1 account, 1 online")])
def test_the_dashboard_uses_the_singular_for_one_account(S, lang, expected):
    panel = S.open(lang=lang, viewport=VIEWPORTS["desktop"])
    panel.goto_tab("dashboard", ready="#tab-telegram-dashboard .kpi-value")
    assert expected in tab_text(panel, "dashboard")
