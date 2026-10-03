"""Nickname change: engine request (APK EditUsername), after signup, later for existing accounts, never reused."""

import time

from bot.engine import BotRunner, RenameRunner
from conftest import FAST_DELAYS, ok, setup_ready, wait_runs_done, wait_until
from test_engine import APK, Recorder, _account_from_signup, photo  # noqa: F401 (fixture)
from test_ui import Page, browser  # noqa: F401 (fixture)


# --- engine ------------------------------------------------------------------------------

def test_rename_after_signup_like_the_app(jaumo, photo):
    rec = Recorder()
    r = BotRunner({"delays": FAST_DELAYS, "max_swipes": 2}, APK, photo, emit=rec, name="Anna", rename_to="Lea")
    r.client.base_url = jaumo.base
    assert r.run()["status"] == "done"
    st = jaumo.state()
    assert [u["form"] for u in st["usernames"]] == [{"username": "Lea"}], "PUT links.username with username=<name>"
    assert st["usernames"][0]["content_type"] == "application/x-www-form-urlencoded"
    assert rec.kinds("renamed") == [{"old": "Anna", "new": "Lea"}]
    paths = [x["path"] for x in st["requests"]]
    assert max(i for i, p in enumerate(paths) if p.startswith("/v2/gallery")) < paths.index("/v2/me/username") \
        < min(i for i, p in enumerate(paths) if "zapping" in p), "after the photo, before swiping"
    assert st["bad_signatures"] == [] and st["bad_headers"] == []
    assert "rename" in rec.steps()


def test_rejected_name_keeps_the_account_going(jaumo, photo):
    jaumo.control(username_status=422)
    rec = Recorder()
    r = BotRunner({"delays": FAST_DELAYS, "max_swipes": 2}, APK, photo, emit=rec, name="Anna", rename_to="Lea")
    r.client.base_url = jaumo.base
    assert r.run()["status"] == "done", "swiping still happens"
    assert rec.kinds("renamed") == [] and {"rename_error": "Lea: not accepted (HTTP 422)"} in rec.kinds("account_update")


def test_rename_later_reuses_a_valid_login(jaumo, photo):
    acc = {**_account_from_signup(jaumo, photo), "token_expires_at": time.time() + 3000}
    n = len(jaumo.state()["requests"])
    rec = Recorder()
    r = RenameRunner({"delays": FAST_DELAYS}, APK, acc, "Mira", emit=rec)
    r.client.base_url = jaumo.base
    assert r.run() == {"status": "done", "reason": "renamed to Mira"}
    new = jaumo.state()["requests"][n:]
    assert [x["path"] for x in new] == ["/v2/", "/v2/me/username"], "2 requests, no new login"
    assert {x["device"] for x in new} == {acc["device_id"]}, "same device as at signup"
    assert rec.kinds("renamed") == [{"old": acc["name"], "new": "Mira"}]


# --- panel -------------------------------------------------------------------------------

def test_rename_right_after_signup_and_never_reused(app, api, jaumo):
    setup_ready(api, photos=4, max_swipes=1)
    ok(api.put("/api/config", json={"settings": {"rename_after_signup": True, "rename_pool": ["Neu A", "Neu B"]}}))
    assert ok(api.get("/api/config"))["rename_unused"] == 2
    runs = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 2}))["run_ids"])
    accs = [ok(api.get(f"/api/accounts/{r['account_id']}")) for r in runs]
    assert sorted(a["name"] for a in accs) == ["Neu A", "Neu B"]
    assert all(a["name_history"] == [r["requested_name"]] for a, r in zip(accs, runs)), "first name kept as history"
    kinds = [e["kind"] for e in ok(api.get(f"/api/accounts/{accs[0]['id']}/events", params={"limit": 500}))]
    assert "renamed" in kinds
    check = ok(api.post("/api/runs/check", json={"count": 1}))
    assert [p["code"] for p in check["problems"]] == ["rename"] and check["problems"][0]["page"] == "rename"
    # the registration name an account had before is never given out again
    r = api.post("/api/runs", json={"count": 1, "names": [runs[0]["requested_name"]]})
    assert r.status_code == 422 and "already used" in r.json()["detail"]


def test_rename_later_for_selected_accounts(app, api, jaumo):
    setup_ready(api, photos=3, max_swipes=1)
    runs = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 2}))["run_ids"])
    a1, a2 = runs[0]["account_id"], runs[1]["account_id"]
    r = api.post("/api/accounts/rename", json={"account_ids": [a1]})
    assert r.status_code == 422 and "empty" in r.json()["detail"], "no list yet"
    ok(api.put("/api/config", json={"settings": {"rename_pool": ["Später Eins"]}}))
    assert ok(api.get("/api/config"))["settings"]["rename_after_signup"] is False, "later only"
    ok(api.put("/api/config", json={"settings": {"max_swipes": 0, "delays": {**FAST_DELAYS, "between_swipes": [0.4, 0.4]}}}))
    busy = ok(api.post(f"/api/accounts/{a2}/swipe"))["run_ids"][0]
    wait_until(lambda: ok(api.get(f"/api/runs/{busy}"))["status"] == "running", msg="a2 swiping")
    res = ok(api.post("/api/accounts/rename", json={"account_ids": [a1, a2]}))
    assert len(res["run_ids"]) == 1 and res["skipped"][0]["reason"] == "already working"
    run = wait_runs_done(api, res["run_ids"])[0]
    assert run["kind"] == "rename" and run["status"] == "done" and run["reason"] == "renamed to Später Eins"
    a = ok(api.get(f"/api/accounts/{a1}"))
    assert a["name"] == "Später Eins" and a["name_history"] == [runs[0]["requested_name"]]
    assert api.post("/api/accounts/rename", json={"account_ids": [a1]}).status_code == 422, "list used up (unique)"
    ok(api.post(f"/api/runs/{busy}/stop"))
    wait_runs_done(api, [busy])


def test_nicknames_page_and_rename_button(browser, app, jaumo):
    api = app.client()
    setup_ready(api, photos=2, max_swipes=1)
    acc = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]["account_id"]
    pg = Page(browser, app).login("rename")
    try:
        pg.p.wait_for_selector("#rename-form")
        nav = pg.p.locator("#nav-jaumo .sb-sub button").evaluate_all("els => els.map(e => e.dataset.tab)")
        assert nav.index("names") + 1 == nav.index("rename") == nav.index("about") - 1, "order as in the mockup"
        pg.p.fill("#rename-form textarea[name=rename_pool]", "Klara\nPaula")
        pg.p.click("#rename-form button[type=submit]")
        pg.p.wait_for_function("document.querySelectorAll('#rename-usage .name-chip').length === 2")
        assert ok(api.get("/api/config"))["settings"]["rename_pool"] == ["Klara", "Paula"]
        pg.tab("accounts")
        pg.p.locator(f'#acc-tbody tr[data-acc="{acc}"] [data-more]').click()
        pg.p.click(".menu [data-act=rename]")
        wait_until(lambda: ok(api.get(f"/api/accounts/{acc}"))["name"] in ("Klara", "Paula"), msg="renamed")
        pg.p.goto(f"{app.url}/#account/{acc}")
        pg.p.wait_for_selector(".acc-formerly")
        assert pg.p.inner_text(".acc-formerly").startswith("früher:")
        pg.assert_clean("nickname change")
    finally:
        pg.close()
