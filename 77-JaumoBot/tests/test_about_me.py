"""Profile text ("Über mich"): engine request flow (APK EditAboutMe), panel reservation, Profiltexte page."""

from bot.engine import BotRunner
from conftest import FAST_DELAYS, ok, setup_ready, wait_runs_done
from test_engine import APK, Recorder, photo  # noqa: F401 (fixture)
from test_ui import Page, browser  # noqa: F401 (fixture)

TEXT = "Ich liebe Kaffee, Wandern & gute Gespräche ☕️ — schreib mir!"


def _run(jaumo, photo, about, **settings):
    rec = Recorder()
    r = BotRunner({"delays": FAST_DELAYS, "max_swipes": 2, **settings}, APK, photo, emit=rec, about=about)
    r.client.base_url = jaumo.base
    return r.run(), rec


# --- engine ------------------------------------------------------------------------------

def test_text_is_set_like_the_app_after_the_photo(jaumo, photo):
    res, rec = _run(jaumo, photo, TEXT)
    st = jaumo.state()
    assert res["status"] == "done", res
    assert [a["form"] for a in st["about"]] == [{"data": TEXT}], "PUT me/data/aboutme with data=<text>"
    assert st["about"][0]["content_type"] == "application/x-www-form-urlencoded"
    assert {"about_me": TEXT, "about_me_error": ""} in rec.kinds("account_update")
    paths = [r["path"] for r in st["requests"]]
    assert paths.index("/v2/me/data") < paths.index("/v2/me/data/aboutme"), "aboutme link is read from MeData"
    assert max(i for i, p in enumerate(paths) if p.startswith("/v2/gallery")) < paths.index("/v2/me/data/aboutme"), \
        "text comes after the photo"
    assert paths.index("/v2/me/data/aboutme") < min(i for i, p in enumerate(paths) if "zapping" in p), "and before swiping"
    assert st["bad_signatures"] == [] and st["bad_headers"] == []
    assert "about" in rec.steps()


def test_rejected_text_does_not_stop_the_account(jaumo, photo):
    jaumo.control(about_status=422)
    res, rec = _run(jaumo, photo, TEXT)
    assert res["status"] == "done", "swiping still happens"
    assert {"about_me_error": "not set (HTTP 422)"} in rec.kinds("account_update")
    assert not any("about_me" in u and u.get("about_me") for u in rec.kinds("account_update"))


def test_no_text_no_request(jaumo, photo):
    res, rec = _run(jaumo, photo, None)
    assert res["status"] == "done" and jaumo.state()["about"] == []
    assert not any(r["path"] in ("/v2/me/data", "/v2/me/data/aboutme") for r in jaumo.state()["requests"])


# --- panel -------------------------------------------------------------------------------

def test_texts_are_reserved_like_names(app, api, jaumo):
    setup_ready(api, photos=4, max_swipes=1)
    ok(api.put("/api/config", json={"settings": {"about_enabled": True, "about_pool": ["Text A", "Text B", "text a"]}}))
    c = ok(api.get("/api/config"))
    assert (c["about_total"], c["about_unused"]) == (2, 2), "duplicates (case-insensitive) count once"
    runs = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 2}))["run_ids"])
    texts = sorted(ok(api.get(f"/api/accounts/{r['account_id']}"))["about_me"] for r in runs)
    assert texts == ["Text A", "Text B"], "each account gets its own text"
    assert sorted(f["form"]["data"] for f in jaumo.state()["about"]) == ["Text A", "Text B"]
    assert ok(api.get("/api/config"))["about_unused"] == 0

    check = ok(api.post("/api/runs/check", json={"count": 1}))
    assert [p["code"] for p in check["problems"]] == ["about"] and check["problems"][0]["page"] == "about"
    r = api.post("/api/runs", json={"count": 1})
    assert r.status_code == 422 and "profile texts" in r.json()["detail"]

    ok(api.put("/api/config", json={"settings": {"about_unique": False}}))
    assert ok(api.post("/api/runs/check", json={"count": 2}))["ok"], "reuse allowed -> texts may repeat"
    assert ok(api.get("/api/about/usage")) == {"text a": 1, "text b": 1}


def test_validation(app, api):
    r = api.put("/api/config", json={"settings": {"about_enabled": True, "about_pool": ["  ", ""]}})
    assert r.status_code == 422 and "profile text" in r.json()["detail"]
    assert ok(api.get("/api/config"))["settings"]["about_enabled"] is False, "off by default (as before)"


def test_profile_texts_page(browser, app, jaumo):
    api = app.client()
    setup_ready(api, photos=2, max_swipes=1)
    pg = Page(browser, app).login("about")
    try:
        pg.p.wait_for_selector("#about-form")
        nav = pg.p.locator("#nav-jaumo .sb-sub button").evaluate_all("els => els.map(e => e.dataset.tab)")
        assert nav.index("names") + 1 == nav.index("about") < nav.index("cities"), "placed as in the client's mockup"
        pg.p.check("#about-form input[name=about_enabled]")
        pg.p.fill("#about-form textarea[name=about_pool]", "Erster Text\nZweiter Text")
        pg.p.wait_for_function("document.querySelector('#about-usage').textContent.includes('2')")
        pg.p.click("#about-form button[type=submit]")
        pg.p.wait_for_function("document.querySelectorAll('#about-usage .name-chip').length === 2")
        s = ok(api.get("/api/config"))["settings"]
        assert s["about_enabled"] and s["about_pool"] == ["Erster Text", "Zweiter Text"] and s["max_swipes"] == 1
        acc = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]["account_id"]
        pg.p.goto(f"{app.url}/#account/{acc}")
        pg.p.wait_for_selector(".acc-about")
        assert pg.p.inner_text(".acc-about") in ("Über mich Text: Erster Text", "Über mich Text: Zweiter Text")
        pg.assert_clean("profile texts")
    finally:
        pg.close()


def test_result_under_status_and_about_label(browser, app, jaumo):
    api = app.client()
    setup_ready(api, photos=2, max_swipes=3)
    ok(api.put("/api/config", json={"settings": {"about_enabled": True, "about_pool": ["Hallo Welt"]}}))
    acc = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]["account_id"]
    a = ok(api.get(f"/api/accounts/{acc}"))
    assert a["last_result"]["status"] == "done" and a["last_result"]["reason"] == "max swipes reached (3)"
    pg = Page(browser, app).login("accounts")
    try:
        row = pg.p.locator(f'#acc-tbody tr[data-acc="{acc}"]')
        assert row.locator(".state-reason").inner_text() == "Fertig: Max. Swipes erreicht (3)"
        pg.p.goto(f"{app.url}/#account/{acc}")
        pg.p.wait_for_selector(".acc-result")
        assert "Fertig: Max. Swipes erreicht (3)" in pg.p.inner_text(".acc-result")
        assert pg.p.inner_text(".acc-about").startswith("Über mich Text:") and "Hallo Welt" in pg.p.inner_text(".acc-about")
        pg.assert_clean("result + about label")
    finally:
        pg.close()
