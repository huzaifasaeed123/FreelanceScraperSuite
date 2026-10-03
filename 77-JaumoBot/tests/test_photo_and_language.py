"""Photo rejection (reason from the existing photo requests only, rejected images never reused) and DE/EN pages."""

from bot.engine import BotRunner
from conftest import FAST_DELAYS, ok, setup_ready, wait_runs_done
from test_engine import APK, Recorder, photo  # noqa: F401 (fixture)
from test_ui import TABS, Page, browser  # noqa: F401 (fixture)


def _signup(jaumo, photo):
    rec = Recorder()
    r = BotRunner({"delays": FAST_DELAYS, "max_swipes": 2}, APK, photo, emit=rec)
    r.client.base_url = jaumo.base
    return r.run(), rec


# --- engine ------------------------------------------------------------------------------

def test_refused_upload_reason_without_extra_requests(jaumo, photo):
    jaumo.control(upload_status=422)
    res, rec = _signup(jaumo, photo)
    assert res == {"status": "failed",
                   "reason": "photo rejected: upload refused (HTTP 422): Image does not meet our guidelines"}, res
    assert rec.kinds("photo_problem") == [{"reason": "upload refused (HTTP 422): Image does not meet our guidelines",
                                           "rejected": True}]
    paths = [r["path"] for r in jaumo.state()["requests"]]
    assert paths.count("/v2/gallery/upload") == 1, "no retry"
    assert paths.index("/v2/gallery/upload") == len(paths) - 1, "nothing is requested after the refused upload"
    assert not any("zapping" in p for p in paths), "no likes without a photo"


def test_compliance_warning_is_a_rejection(jaumo, photo):
    jaumo.control(photo_warning=True)
    res, rec = _signup(jaumo, photo)
    assert rec.kinds("photo_problem") == [{"reason": "Jaumo warning: face not detected", "rejected": True}]
    assert res["reason"] == "photo rejected: Jaumo warning: face not detected"


# --- panel -------------------------------------------------------------------------------

def test_rejected_photo_is_marked_and_never_reused(app, api, jaumo):
    setup_ready(api, photos=2, max_swipes=1)
    ok(api.put("/api/settings", json={"identity": {"unique_names": True, "unique_photos": False}}))
    jaumo.control(upload_status=422)
    run = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]
    acc = ok(api.get(f"/api/accounts/{run['account_id']}"))
    assert acc["status"] == "photo_failed" and "upload refused (HTTP 422)" in acc["photo_error"]
    photos = {p["name"]: p for p in ok(api.get("/api/photos"))}
    bad = photos[run["photo"]]
    assert bad["status"] == "rejected" and "HTTP 422" in bad["rejected_reason"]
    kinds = [e["kind"] for e in ok(api.get(f"/api/accounts/{acc['id']}/events", params={"limit": 50}))]
    assert "photo_rejected" in kinds
    jaumo.control(upload_status=200)
    later = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 3}))["run_ids"])
    assert all(r["photo"] != run["photo"] for r in later), "a rejected photo is never given out again (reuse on)"
    ok(api.post(f"/api/photos/{run['photo']}/release"))
    assert {p["name"]: p for p in ok(api.get("/api/photos"))}[run["photo"]]["status"] != "rejected"


def test_photo_page_shows_rejection(browser, app, jaumo):
    api = app.client()
    setup_ready(api, photos=2, max_swipes=1)
    jaumo.control(photo_warning=True)
    run = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]
    pg = Page(browser, app).login("photos")
    try:
        pg.p.click('#photo-filter [data-filter="rejected"]')
        card = pg.p.locator(f'.photo-card[data-name="{run["photo"]}"]')
        assert "Abgelehnt" in card.inner_text() and "Jaumo-Warnung: face not detected" in card.inner_text()
        pg.p.goto(f"{app.url}/#account/{run['account_id']}")
        pg.p.wait_for_selector(".acc-about.bad")
        assert "Foto abgelehnt:" in pg.p.inner_text("#acc-hero")
        pg.assert_clean("photo rejection")
    finally:
        pg.close()


# --- languages ---------------------------------------------------------------------------

EN_MARKERS = ["Photo library", "Stop all", "Accounts created", "Add proxies", "Proxy list", "Created today",
              "Account status", "Infrastructure", "Accounts in progress", "Clean old logs", "Choose photos",
              "Select all available", "Upload photos", "Workers (parallel accounts)", "No proxies yet",
              "All accounts", "Sessions", "Load older activity", "Profile & device", "Delete account",
              "Account creation", "Signup details", "Swiping", "Messages", "Stats refresh"]
DE_MARKERS = ["Fotos hochladen", "Alle stoppen", "Erstellte Accounts", "Proxies hinzufügen", "Heute erstellt",
              "Infrastruktur", "Alte Logs löschen", "Alle Accounts", "Sitzungen", "Account löschen",
              "Konfiguration", "Nicknamen", "Städte", "Speichern", "Aktualisieren", "Swipen"]


def test_every_page_in_one_language(browser, app, jaumo):
    api = app.client()
    setup_ready(api, photos=3, max_swipes=2)
    acc = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]["account_id"]
    for lang, wrong in (("de", EN_MARKERS), ("en", DE_MARKERS)):
        pg = Page(browser, app, lang=lang).login("dashboard")
        try:
            pages = TABS + [f"account/{acc}"]
            for tab in pages:
                if tab.startswith("account/"):
                    pg.p.goto(f"{app.url}/#{tab}")
                    pg.p.wait_for_selector("#acc-hero .acc-title")
                else:
                    pg.tab(tab)
                pg.p.wait_for_timeout(300)
                text = pg.p.inner_text(f"#tab-{'account' if tab.startswith('account/') else tab}")
                found = [m for m in wrong if m in text]
                assert not found, f"{lang} page {tab} shows text of the other language: {found}"
            pg.assert_clean(f"pages in {lang}")
        finally:
            pg.close()
