"""
Browser tests (real Chrome via Playwright) against the real server + fake Jaumo.
Any JS error, console error, failed request (>=400) or raw translation key fails the test.
"""

import re
import zipfile
from pathlib import Path

import pytest

from conftest import ADMIN_PASS, FAST_DELAYS, jpeg_bytes, ok, setup_ready, wait_runs_done, wait_until

CHROME = Path(r"C:/Program Files/Google/Chrome/Application/chrome.exe")
pytestmark = [pytest.mark.ui, pytest.mark.skipif(not CHROME.exists(), reason="Chrome not installed")]
pw_sync = pytest.importorskip("playwright.sync_api")

RAW_KEY = re.compile(r"\b(acc|kpi|st|state|nav|sec|top|filter|sort|new|edit|msg|bulk|pager|col|common|del|sys|brand|outdated)\.[a-zA-Z]+\b")
TABS = ["dashboard", "accounts", "configs", "photos", "proxies", "names", "rename", "about", "cities", "runs"]
SLOWISH = {k: [0.2, 0.3] for k in FAST_DELAYS}


@pytest.fixture(scope="module")
def browser():
    with pw_sync.sync_playwright() as p:
        b = p.chromium.launch(executable_path=str(CHROME))
        yield b
        b.close()


class Page:
    """Playwright page that records every problem the user could see."""

    def __init__(self, browser, app, viewport=(1440, 1000), lang="de", theme="dark"):
        self.ctx = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
        # first visit only — later reloads must keep what the user chose in the menu
        self.ctx.add_init_script(f"try{{if(!localStorage.getItem('lang')){{localStorage.setItem('lang','{lang}');"
                                 f"localStorage.setItem('theme','{theme}')}}}}catch(e){{}}")
        self.p = self.ctx.new_page()
        self.app = app
        self.problems = []
        self.p.on("pageerror", lambda e: self.problems.append(f"JS error: {e}"))
        self.p.on("console", lambda m: m.type == "error" and "favicon" not in m.text and self.problems.append(f"console: {m.text}"))
        self.p.on("response", lambda r: r.status >= 400 and self.problems.append(f"HTTP {r.status} {r.request.method} {r.url}"))
        self.p.on("dialog", lambda d: d.accept())

    def login(self, hash_="dashboard"):
        self.p.goto(f"{self.app.url}/#{hash_}")
        self.p.fill("input[name=username]", "admin")
        self.p.fill("input[name=password]", ADMIN_PASS)
        self.p.click("#login-form button")
        self.p.wait_for_selector("#app-view:not(.hidden)")
        self.p.wait_for_timeout(800)
        return self

    def tab(self, name):
        if self.p.viewport_size["width"] <= 900:
            self.p.click("#sb-toggle")
            self.p.wait_for_timeout(250)
        self.p.click(f'#tabs button[data-tab="{name}"]')
        self.p.wait_for_timeout(900)

    def assert_clean(self, where=""):
        text = self.p.inner_text("body")
        raw = sorted(set(RAW_KEY.findall(text)) and set(m.group(0) for m in RAW_KEY.finditer(text)))
        assert not raw, f"{where}: untranslated keys {raw}"
        assert not self.problems, f"{where}: {self.problems}"

    def close(self):
        self.ctx.close()


@pytest.fixture
def populated(app, jaumo):
    api = app.client()
    # first account: likes only + low threshold -> deterministically blocked
    cid = setup_ready(api, photos=10, max_swipes=6, messaging_enabled=True, like_ratio=1.0, block_threshold=2)
    ok(api.put("/api/settings", json={"bot": {"parallel_accounts": 2}}))
    jaumo.control(block_after_likes=2)
    blocked = wait_runs_done(api, ok(api.post("/api/runs", json={"config_id": cid, "count": 1}))["run_ids"])[0]
    assert blocked["status"] == "blocked", blocked
    jaumo.control(block_after_likes=0)
    conf = ok(api.get("/api/configs"))[0]
    ok(api.put(f"/api/configs/{cid}", json={"name": conf["name"], "apk_profile_id": conf["apk_profile_id"],
                                            "settings": {**conf["settings"], "like_ratio": 0.5, "block_threshold": 3}}))
    wait_runs_done(api, ok(api.post("/api/runs", json={"config_id": cid, "count": 3}))["run_ids"])
    return app, api, cid


# --- every page, every language/theme/size ---------------------------------------------------

@pytest.mark.parametrize("lang,theme,size", [("de", "dark", (1440, 1000)), ("en", "light", (1440, 1000)),
                                             ("de", "dark", (1366, 768)), ("de", "light", (390, 844))],
                         ids=["de-dark", "en-light", "laptop", "mobile"])
def test_every_page_renders_without_errors(browser, populated, lang, theme, size):
    app, api, _ = populated
    pg = Page(browser, app, size, lang, theme).login()
    try:
        assert pg.p.evaluate("document.documentElement.dataset.theme") == theme
        for t in TABS:
            pg.tab(t)
            assert pg.p.is_visible(f"#tab-{t}"), t
            if size[0] <= 600:
                assert pg.p.evaluate("document.documentElement.scrollWidth") <= size[0] + 1, f"horizontal scroll on {t}"
            pg.assert_clean(t)
        # page content matches the API
        pg.tab("accounts")
        total = ok(api.get("/api/accounts"))["total"]
        assert pg.p.locator("#acc-tbody tr[data-acc]").count() == total
        assert pg.p.locator("#acc-summary .acc-kpi").count() == 5
        assert str(total) in pg.p.inner_text("#acc-summary")
        pg.tab("dashboard")
        assert pg.p.locator("#kpis .kpi").count() == 4
        pg.tab("photos")
        assert pg.p.locator("#photo-grid .photo-card").count() == 10
        pg.assert_clean("content")
    finally:
        pg.close()


# --- live updates ----------------------------------------------------------------------------

def test_accounts_page_updates_live(browser, populated, jaumo):
    app, api, cid = populated
    conf = ok(api.get("/api/configs"))[0]
    ok(api.put(f"/api/configs/{cid}", json={"name": conf["name"], "apk_profile_id": conf["apk_profile_id"],
                                            "settings": {**conf["settings"], "delays": SLOWISH, "max_swipes": 8}}))
    pg = Page(browser, app).login("accounts")
    try:
        before = pg.p.locator("#acc-tbody tr[data-acc]").count()
        rid = ok(api.post("/api/runs", json={"config_id": cid, "count": 1}))["run_ids"][0]
        pg.p.wait_for_selector("#acc-tbody .state-badge.working", timeout=15000)
        assert pg.p.locator("#acc-tbody tr[data-acc]").count() == before + 1
        wait_runs_done(api, [rid])
        pg.p.wait_for_function("!document.querySelector('#acc-tbody .state-badge.working')", timeout=15000)
        acc = ok(api.get(f"/api/runs/{rid}"))["account_id"]
        row = pg.p.locator(f'#acc-tbody tr[data-acc="{acc}"]')
        likes = ok(api.get(f"/api/accounts/{acc}"))["liked_count"]
        assert row.locator(".stat-tile.likes-out b").inner_text() == str(likes)
        assert "AKTIV" in row.inner_text()
        pg.assert_clean("live accounts")
    finally:
        pg.close()


def test_counters_are_pushed_without_reloading_the_list(browser, populated, jaumo):
    """Swipes reach the open accounts page via WebSocket; the list is not re-fetched for every like."""
    app, api, cid = populated
    conf = ok(api.get("/api/configs"))[0]
    slow = {**SLOWISH, "between_swipes": [0.5, 0.7]}
    ok(api.put(f"/api/configs/{cid}", json={"name": conf["name"], "apk_profile_id": conf["apk_profile_id"],
                                            "settings": {**conf["settings"], "delays": slow, "max_swipes": 10}}))
    pg = Page(browser, app).login("accounts")
    try:
        rid = ok(api.post("/api/runs", json={"config_id": cid, "count": 1}))["run_ids"][0]
        wait_until(lambda: ok(api.get(f"/api/runs/{rid}"))["account_id"], msg="account created")
        acc = ok(api.get(f"/api/runs/{rid}"))["account_id"]
        sel = f'#acc-tbody tr[data-acc="{acc}"]'
        pg.p.wait_for_selector(sel, timeout=15000)
        seen = []
        pg.p.on("request", lambda r: re.search(r"/api/accounts(\?|$)", r.url) and seen.append(r.url))
        pg.p.evaluate("""sel => { window.__swiped = () => { const r = document.querySelector(sel); if (!r) return 0;
            const n = (c) => Number(r.querySelector('.stat-tile.' + c + ' b').textContent.replace(/[^0-9]/g, '')) || 0;
            return n('likes-out') + n('dislikes'); }; }""", sel)
        pg.p.wait_for_function("window.__swiped() >= 4", timeout=30000)
        assert len(seen) <= 1, f"list re-fetched during swipes: {seen}"
        a = ok(api.get(f"/api/accounts/{acc}"))
        assert pg.p.evaluate("window.__swiped()") <= a["liked_count"] + a["disliked_count"]
        wait_runs_done(api, [rid])
        a = ok(api.get(f"/api/accounts/{acc}"))
        pg.p.wait_for_function(f"window.__swiped() === {a['liked_count'] + a['disliked_count']}", timeout=15000)
        pg.assert_clean("counter push")
    finally:
        pg.close()


def test_account_page_shows_live_session(browser, populated, jaumo):
    app, api, cid = populated
    conf = ok(api.get("/api/configs"))[0]
    ok(api.put(f"/api/configs/{cid}", json={"name": conf["name"], "apk_profile_id": conf["apk_profile_id"],
                                            "settings": {**conf["settings"], "delays": SLOWISH, "max_swipes": 30}}))
    rid = ok(api.post("/api/runs", json={"config_id": cid, "count": 1}))["run_ids"][0]
    acc = wait_until(lambda: ok(api.get(f"/api/runs/{rid}"))["account_id"], msg="account")
    pg = Page(browser, app).login(f"account/{acc}")
    try:
        pg.p.wait_for_selector(".live-card", timeout=10000)
        n0 = pg.p.locator("#acc-timeline .tl-item").count()
        pg.p.wait_for_function(f"document.querySelectorAll('#acc-timeline .tl-item').length > {n0 + 2}", timeout=20000)
        assert pg.p.locator("#acc-live-log div").count() > 0
        wait_runs_done(api, [rid])
        pg.p.wait_for_selector(".live-card", state="detached", timeout=15000)
        a = ok(api.get(f"/api/accounts/{acc}"))
        kpis = pg.p.locator("#acc-kpis .kpi .kpi-value")
        assert kpis.nth(0).inner_text() == "–", "likes received: unknown until a stats refresh"
        assert kpis.nth(4).inner_text() == str(a["liked_count"]), "likes sent"
        events = ok(api.get(f"/api/accounts/{acc}/events", params={"limit": 1000}))
        assert pg.p.locator("#acc-timeline .tl-item").count() == min(len(events), 200)
        pg.assert_clean("account page")
    finally:
        pg.close()


# --- actions ----------------------------------------------------------------------------------

def test_account_actions_edit_menu_delete(browser, populated):
    app, api, _ = populated
    pg = Page(browser, app).login("accounts")
    try:
        first = pg.p.locator("#acc-tbody tr[data-acc]").first
        acc_id = int(first.get_attribute("data-acc"))
        first.locator("[data-view]").click()
        pg.p.wait_for_selector("#acc-kpis .kpi")
        assert pg.p.evaluate("location.hash") == f"#account/{acc_id}"
        pg.p.click(".back-link")
        pg.p.wait_for_selector("#acc-tbody tr[data-acc]")
        pg.p.locator(f'#acc-tbody tr[data-acc="{acc_id}"] [data-edit]').click()
        pg.p.fill("#acc-edit-form textarea[name=notes]", "checked by test")
        pg.p.click("#acc-edit-form button.primary")
        pg.p.wait_for_timeout(800)
        assert ok(api.get(f"/api/accounts/{acc_id}"))["notes"] == "checked by test"
        pg.p.locator(f'#acc-tbody tr[data-acc="{acc_id}"] [data-more]').click()
        assert pg.p.is_visible(".menu")
        pg.p.click('.menu [data-act="delete"]')
        pg.p.wait_for_timeout(1000)
        assert api.get(f"/api/accounts/{acc_id}").status_code == 404
        assert pg.p.locator(f'#acc-tbody tr[data-acc="{acc_id}"]').count() == 0
        pg.problems = [x for x in pg.problems if f"/api/accounts/{acc_id}" not in x]   # the 404 above is ours
        pg.assert_clean("actions")
    finally:
        pg.close()


def test_new_accounts_dialog_parallel_and_sequential(browser, populated):
    app, api, _ = populated
    pg = Page(browser, app).login("accounts")
    try:
        pg.p.click("#acc-new")
        pg.p.wait_for_selector("#new-acc-form")
        pg.p.fill("#new-acc-form input[name=count]", "2")
        pg.p.check('#new-acc-form input[name=mode][value=par]')
        pg.p.fill("#new-acc-form input[name=workers]", "3")
        pg.p.click("#new-acc-form button.primary")
        pg.p.wait_for_timeout(1000)
        assert ok(api.get("/api/settings"))["bot"]["parallel_accounts"] == 3
        runs = ok(api.get("/api/runs", params={"kind": "signup"}))["items"]
        assert sum(r["status"] in ("queued", "running", "done") for r in runs[:2]) == 2
        wait_runs_done(api, [r["id"] for r in runs[:2]])
        pg.p.click("#acc-new")
        pg.p.wait_for_selector("#new-acc-form")
        pg.p.check('#new-acc-form input[name=mode][value=seq]')
        pg.p.click("#new-acc-form button.primary")
        pg.p.wait_for_timeout(1000)
        assert ok(api.get("/api/settings"))["bot"]["parallel_accounts"] == 1
        pg.assert_clean("new accounts")
    finally:
        pg.close()


def test_new_accounts_dialog_explains_why_it_cannot_start(browser, app):
    api = app.client()
    setup_ready(api, photos=0)
    pg = Page(browser, app).login("accounts")
    try:
        pg.p.click("#acc-new")
        pg.p.wait_for_selector("#new-problems:not(.hidden)")
        assert pg.p.is_disabled("#new-submit")
        assert "Nicht genug freie Fotos" in pg.p.inner_text("#new-problems")
        pg.p.click('#new-problems a[href="#photos"]')
        pg.p.wait_for_selector("#tab-photos:not(.hidden)")
        assert not pg.p.is_visible("#new-acc-form")
        files = [("files", (f"p{i}.jpg", jpeg_bytes(i), "image/jpeg")) for i in range(2)]
        ok(api.post("/api/photos", files=files))
        pg.tab("accounts")
        pg.p.click("#acc-new")
        pg.p.wait_for_selector("#new-submit:not([disabled])")
        pg.p.fill("#new-acc-form input[name=count]", "3")
        pg.p.wait_for_selector("#new-problems:not(.hidden)")
        assert pg.p.is_disabled("#new-submit"), "3 accounts but only 2 unused photos"
        pg.p.click("#new-acc-form [data-step='-1']")
        pg.p.wait_for_selector("#new-submit:not([disabled])")
        pg.assert_clean("new account check")
    finally:
        pg.close()


def test_dashboard_setup_checklist(browser, app):
    api = app.client()
    pg = Page(browser, app).login("dashboard")
    try:
        pg.p.wait_for_selector("#setup-check:not(.hidden)")
        todo = pg.p.locator("#setup-check li.todo").evaluate_all("els => els.map(e => e.dataset.setup)")
        assert set(todo) >= {"apk", "photos"}
        setup_ready(api, photos=2)
        pg.tab("photos")
        pg.tab("dashboard")
        pg.p.wait_for_selector("#setup-check.hidden", state="attached")
        pg.assert_clean("setup checklist")
    finally:
        pg.close()


def _main_settings(api):
    return ok(api.get("/api/config"))["settings"]


def test_jaumo_menu_group(browser, app):
    pg = Page(browser, app).login("dashboard")
    try:
        subs = pg.p.locator("#nav-jaumo .sb-sub button").evaluate_all("els => els.map(e => e.dataset.tab)")
        assert subs == ["configs", "photos", "proxies", "names", "rename", "about", "cities", "runs"], "order as in the client's mockup"
        assert pg.p.locator("#tabs button[data-tab=settings]").count() == 0, "no separate settings page"
        pg.p.click("#nav-jaumo-toggle")
        assert not pg.p.is_visible("#nav-jaumo .sb-sub"), "arrow folds the sub-menu"
        assert pg.p.evaluate("location.hash") == "#dashboard", "the arrow does not navigate"
        pg.p.reload()
        pg.p.wait_for_selector("#app-view:not(.hidden)")
        assert not pg.p.is_visible("#nav-jaumo .sb-sub"), "folded state is remembered"
        pg.p.click("#tabs button[data-tab=accounts]")
        pg.p.wait_for_selector("#nav-jaumo .sb-sub", state="visible")
        assert "active" in pg.p.get_attribute("#tabs button[data-tab=accounts]", "class")
        pg.tab("cities")
        assert "active" in pg.p.get_attribute("#nav-jaumo button[data-tab=cities]", "class")
        pg.assert_clean("menu")
    finally:
        pg.close()


def test_config_page_saves_its_fields_and_keeps_the_rest(browser, app):
    api = app.client()
    setup_ready(api, photos=1)
    before = _main_settings(api)
    pg = Page(browser, app).login("configs")
    try:
        pg.p.wait_for_selector("#cfg-form")
        assert "Konfiguration" in pg.p.inner_text("#tab-configs h1")
        assert pg.p.locator("#config-body #apk-card, #config-body .cfg-card").count() >= 5
        assert "Gespeichertes Profil" in pg.p.inner_text("#config-body"), "no env vars in tests -> stored profile"
        assert pg.p.locator("#cfg-form details.adv").count() == 3
        assert pg.p.locator("#cfg-form details.adv[open]").count() == 0, "advanced sections start closed"
        assert not pg.p.is_visible("#cfg-form textarea[name=devices]")
        assert pg.p.locator("#cfg-form textarea[name=locations]").count() == 0, "cities have their own page"
        pg.p.click("#cfg-form details[data-adv=delays] summary")
        pg.p.fill("#cfg-form input[name=d_between_swipes_1]", "9")
        # an invalid value in a closed section opens it so the browser can point at the field
        pg.p.fill("#cfg-form input[name=d_after_signup_0]", "-1")
        pg.p.click("#cfg-form details[data-adv=delays] summary")
        pg.p.click("#cfg-form button[type=submit]")
        pg.p.wait_for_selector("#cfg-form details[data-adv=delays][open]")
        pg.p.fill("#cfg-form input[name=d_after_signup_0]", str(before["delays"]["after_signup"][0]))
        pg.p.fill("#cfg-form input[name=max_swipes]", "7")
        pg.p.click("#cfg-workers [data-step='1']")
        pg.p.click("#cfg-form button[type=submit]")
        wait_until(lambda: _main_settings(api)["max_swipes"] == 7, msg="saved")
        after = _main_settings(api)
        assert after["delays"]["between_swipes"][1] == 9
        for k in ("devices", "relationship_search", "looking_for_gender", "locations", "name_pool", "name_source"):
            assert after[k] == before[k], f"{k} kept"
        assert ok(api.get("/api/settings"))["bot"]["parallel_accounts"] == 2
        pg.assert_clean("config page")
    finally:
        pg.close()


def test_names_page(browser, app):
    api = app.client()
    setup_ready(api, photos=1)
    pg = Page(browser, app).login("names")
    try:
        pg.p.wait_for_selector("#names-form")
        assert not pg.p.is_visible("#names-form textarea[name=name_pool]"), "auto names: no list to edit"
        pg.p.check("#names-form input[name=name_source][value=custom]")
        pg.p.fill("#names-form textarea[name=name_pool]", "Lena\nMia\nLena")
        pg.p.wait_for_function("document.querySelector('#name-usage').textContent.includes('2')")
        pg.p.uncheck("#names-form input[name=unique_names]")
        pg.p.click("#names-form button[type=submit]")
        wait_until(lambda: _main_settings(api)["name_source"] == "custom", msg="saved")
        s = _main_settings(api)
        assert s["name_pool"] == ["Lena", "Mia", "Lena"] and s["max_swipes"] == 6, "only the name fields change"
        assert ok(api.get("/api/settings"))["identity"] == {"unique_names": False, "unique_photos": True}
        pg.assert_clean("names page")
    finally:
        pg.close()


def test_cities_page(browser, app):
    api = app.client()
    setup_ready(api, photos=1)
    pg = Page(browser, app).login("cities")
    try:
        pg.p.wait_for_selector("#cities-form")
        n = len(_main_settings(api)["locations"])
        assert str(n) in pg.p.inner_text("#city-preview")
        pg.p.fill("#cities-form textarea[name=locations]", "Berlin,52.52,13.405,20\nKaputt,abc")
        pg.p.wait_for_selector("#city-preview .error")
        pg.p.click("#cities-form button[type=submit]")
        pg.p.wait_for_function("document.querySelector('#cities-error').textContent.length > 0")
        assert len(_main_settings(api)["locations"]) == n, "invalid list is not saved"
        pg.p.fill("#cities-form textarea[name=locations]", "Berlin,52.52,13.405,20\nLeipzig,51.3397,12.3731")
        pg.p.fill("#cities-form input[name=location_radius_km]", "5")
        pg.p.click("#cities-form button[type=submit]")
        wait_until(lambda: len(_main_settings(api)["locations"]) == 2, msg="saved")
        s = _main_settings(api)
        assert s["location_radius_km"] == 5 and s["locations"][0]["radius_km"] == 20 and s["locations"][1]["radius_km"] is None
        pg.assert_clean("cities page")
    finally:
        pg.close()


def test_filters_search_paging(browser, populated):
    app, api, _ = populated
    pg = Page(browser, app).login("accounts")
    try:
        pg.p.select_option("#flt-state", "blocked")
        pg.p.wait_for_timeout(800)
        assert pg.p.locator("#acc-tbody tr[data-acc]").count() == ok(api.get("/api/accounts", params={"state": "blocked"}))["total"] >= 1
        pg.p.select_option("#flt-state", "")
        name = ok(api.get("/api/accounts"))["items"][0]["name"]
        pg.p.fill("#acc-search", name)
        pg.p.wait_for_timeout(900)
        assert name in pg.p.locator("#acc-tbody tr[data-acc]").first.inner_text()
        pg.p.fill("#acc-search", "")
        pg.p.select_option("#acc-per", "12")
        pg.p.click("#flt-toggle")
        pg.p.select_option("#flt-sort", "likes")
        pg.p.click("#flt-apply")
        pg.p.wait_for_timeout(800)
        vals = [int(x) for x in pg.p.locator("#acc-tbody .stat-tile.likes-out b").all_inner_texts()]
        assert vals == sorted(vals, reverse=True)
        pg.assert_clean("filters")
    finally:
        pg.close()


def test_photo_upload_and_delete_in_browser(browser, app, tmp_path):
    zpath = tmp_path / "pics.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        for i in range(4):
            z.writestr(f"p/{i}.png", jpeg_bytes(200 + i, fmt="PNG"))
        z.writestr("p/dup.png", jpeg_bytes(200, fmt="PNG"))
    pg = Page(browser, app).login("photos")
    try:
        pg.p.set_input_files("#photo-zip", str(zpath))
        pg.p.wait_for_function("document.querySelector('#upload-panel').innerText.includes('100%') || document.querySelectorAll('#photo-grid .photo-card').length >= 4", timeout=30000)
        pg.p.wait_for_timeout(800)
        assert pg.p.locator("#photo-grid .photo-card").count() == 4
        pg.p.click("#photo-select-all")
        pg.p.click("#photo-bulk-delete")
        pg.p.wait_for_timeout(1000)
        assert pg.p.locator("#photo-grid .photo-card").count() == 0
        pg.assert_clean("photos")
    finally:
        pg.close()


def test_language_and_theme_switch_persist(browser, app):
    pg = Page(browser, app, lang="de", theme="dark").login("accounts")
    try:
        assert "Neuer Account" in pg.p.inner_text("#acc-new")
        pg.p.click("#top-user")
        pg.p.click("#menu-lang")
        pg.p.wait_for_timeout(500)
        assert "New account" in pg.p.inner_text("#acc-new")
        pg.p.click("#top-user")
        pg.p.click("#menu-theme")
        pg.p.reload()
        pg.p.wait_for_selector("#app-view:not(.hidden)")
        pg.p.wait_for_timeout(600)
        assert "New account" in pg.p.inner_text("#acc-new")
        assert pg.p.evaluate("document.documentElement.dataset.theme") == "light"
        pg.assert_clean("switches")
    finally:
        pg.close()
