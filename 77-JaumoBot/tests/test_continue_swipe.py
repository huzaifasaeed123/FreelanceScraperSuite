"""Continue swiping with an existing account: engine (no signup / photo / location) and panel (stop -> continue)."""

from bot.engine import SwipeRunner
from conftest import FAST_DELAYS, ok, setup_ready, wait_runs_done, wait_until
from test_engine import APK, Recorder, _account_from_signup, photo  # noqa: F401 (fixture)
from test_ui import SLOWISH, Page, browser  # noqa: F401 (fixture)


# --- engine ------------------------------------------------------------------------------

def _swipe(jaumo, account, **settings):
    rec = Recorder()
    r = SwipeRunner({"delays": FAST_DELAYS, **settings}, APK, account, emit=rec)
    r.client.base_url = jaumo.base
    return r.run(), rec


def test_runner_swipes_with_the_stored_identity_only(jaumo, photo):
    acc = _account_from_signup(jaumo, photo)
    st = jaumo.state()
    before = (len(st["registrations"]), len(st["uploads"]), len(st["likes"]) + len(st["dislikes"]))
    n_requests = len(st["requests"])
    res, rec = _swipe(jaumo, acc, max_swipes=5)
    st = jaumo.state()
    assert res["status"] == "done" and "max swipes" in res["reason"], res
    assert len(rec.kinds("swipe")) == 5
    assert (len(st["registrations"]), len(st["uploads"])) == before[:2], "no new signup, no photo upload"
    assert len(st["likes"]) + len(st["dislikes"]) == before[2] + 5
    new = st["requests"][n_requests:]
    assert {r["device"] for r in new if r["device"]} == {acc["device_id"]}, "same device as at signup"
    assert not any("location" in r["path"] for r in new), "location is not changed"
    assert st["bad_signatures"] == [] and st["bad_headers"] == []


def test_runner_reports_an_unusable_login(jaumo, photo):
    acc = _account_from_signup(jaumo, photo)
    acc["access_token"], acc["refresh_token"] = "", ""
    res, rec = _swipe(jaumo, acc, max_swipes=2)
    assert res["status"] == "failed" and "token" in res["reason"] and rec.kinds("swipe") == []


# --- panel -------------------------------------------------------------------------------

def test_stop_then_continue_swiping(app, api, jaumo):
    cid = setup_ready(api, photos=2, max_swipes=0, delays={**FAST_DELAYS, "between_swipes": [0.3, 0.3]})
    rid = ok(api.post("/api/runs", json={"config_id": cid, "count": 1}))["run_ids"][0]
    wait_until(lambda: ok(api.get(f"/api/runs/{rid}"))["swipes"] >= 2, msg="swiping")
    ok(api.post(f"/api/runs/{rid}/stop"))
    run = wait_runs_done(api, [rid])[0]
    acc_id = run["account_id"]
    a = ok(api.get(f"/api/accounts/{acc_id}"))
    assert a["status"] == "active" and a["has_token"], "a stopped account keeps everything to continue"
    swiped = a["liked_count"] + a["disliked_count"]

    ok(api.put("/api/config", json={"settings": {"max_swipes": 4}}))
    res = ok(api.post(f"/api/accounts/{acc_id}/swipe"))
    r2 = wait_runs_done(api, res["run_ids"])[0]
    assert r2["kind"] == "swipe" and r2["status"] == "done" and r2["account_id"] == acc_id and r2["swipes"] == 4, r2
    a = ok(api.get(f"/api/accounts/{acc_id}"))
    assert a["liked_count"] + a["disliked_count"] == swiped + 4, "counts continue on the same account"
    assert ok(api.get("/api/accounts"))["total"] == 1, "no new account"
    assert len(jaumo.state()["registrations"]) == 1


def test_continue_skips_accounts_that_cannot_swipe(app, api, jaumo):
    cid = setup_ready(api, photos=3, max_swipes=1)
    runs = wait_runs_done(api, ok(api.post("/api/runs", json={"config_id": cid, "count": 2}))["run_ids"])
    ok_id, blocked_id = runs[0]["account_id"], runs[1]["account_id"]
    ok(api.patch(f"/api/accounts/{blocked_id}", json={"status": "blocked"}))
    ok(api.put("/api/config", json={"settings": {"max_swipes": 1, "delays": {**FAST_DELAYS, "between_swipes": [1, 1]}}}))
    res = ok(api.post("/api/accounts/swipe", json={"account_ids": [ok_id, blocked_id]}))
    assert len(res["run_ids"]) == 1 and res["skipped"] == [{"id": blocked_id, "name": runs[1]["requested_name"],
                                                            "reason": "blocked by Jaumo"}]
    r = api.post(f"/api/accounts/{ok_id}/swipe")
    assert r.status_code == 409 and r.json()["detail"] == "already working"
    wait_runs_done(api, res["run_ids"])
    assert api.post("/api/accounts/swipe", json={"account_ids": []}).status_code == 422
    assert api.post("/api/accounts/999/swipe").status_code == 404


def test_continue_from_the_accounts_page(browser, app, jaumo):
    api = app.client()
    cid = setup_ready(api, photos=2, max_swipes=1)
    acc_id = wait_runs_done(api, ok(api.post("/api/runs", json={"config_id": cid, "count": 1}))["run_ids"])[0]["account_id"]
    ok(api.put("/api/config", json={"settings": {"max_swipes": 6, "delays": SLOWISH}}))
    pg = Page(browser, app).login("accounts")
    try:
        row = pg.p.locator(f'#acc-tbody tr[data-acc="{acc_id}"]')
        row.locator("[data-more]").click()
        pg.p.click(".menu [data-act=swipe]")
        pg.p.wait_for_selector(f'#acc-tbody tr[data-acc="{acc_id}"] .state-badge.working', timeout=15000)
        pg.p.wait_for_selector(f'#acc-tbody tr[data-acc="{acc_id}"] .state-badge.ok', timeout=30000)
        runs = ok(api.get(f"/api/accounts/{acc_id}/runs"))
        assert runs[0]["kind"] == "swipe" and runs[0]["status"] == "done" and runs[0]["swipes"] == 6
        pg.assert_clean("continue swiping")
    finally:
        pg.close()
