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


def test_swipe_limit_answer_ends_the_session_cleanly(jaumo, photo):
    """Live crash 2026-10-02: Jaumo answered the zapping call with "items": null (unlock dialog)
    -> TypeError: object of type 'NoneType' has no len()."""
    acc = _account_from_signup(jaumo, photo)
    jaumo.control(batches=0, empty_deck={"items": None, "unlock": {"title": "Unlock more profiles"},
                                         "unlockExpiresIn": 3600, "noResult": None})
    calls = jaumo.state()["requests"]
    res, rec = _swipe(jaumo, acc, max_swipes=0)
    assert res == {"status": "done", "reason": "Jaumo lock: cards locked for 3600 s (dialog)"}, res
    assert {"status": "active"} in rec.kinds("account_update"), "the account stays active"
    zapping = [r for r in jaumo.state()["requests"][len(calls):] if "zapping/pop" in r["path"]]
    assert len(zapping) == 1, "a long lock (> 15 min) is not requested again and again"


# The live answer from 2026-10-03 (shortened): a "rate us" dialog that locks the cards for 147 s.
RATE_APP = {"items": None, "actionRequired": None, "noResult": None,
            "unlock": {"identifier": "", "title": "Having fun on <b>Jaumo?</b>", "illustration": "RATING",
                       "options": [{"caption": "Will you give us 5 stars?", "type": "rate_app", "style": "primary"}],
                       "links": {}},
            "unlockTimeout": "2026-10-02T20:50:23+00:00", "unlockExpiresIn": 1, "progress": None}
NO_WAIT = {**FAST_DELAYS, "after_jaumo_pause": [0, 0]}


def test_short_jaumo_pause_is_waited_out_and_swiping_continues(jaumo, photo):
    acc = _account_from_signup(jaumo, photo)
    jaumo.control(zapping_script=[RATE_APP])
    res, rec = _swipe(jaumo, acc, max_swipes=6, delays=NO_WAIT)
    assert res == {"status": "done", "reason": "max swipes reached (6)"}, res
    assert len(rec.kinds("swipe")) == 6, "swiping went on after the pause"
    logs = [l["msg"] for l in rec.kinds("log")]
    assert any("[PAUSE] Jaumo paused the cards for 1 s (rate_app)" in m for m in logs), logs
    assert not any("rate" in r["path"] or "unlock" in r["path"] for r in jaumo.state()["requests"]),         "the dialog is never clicked"


def test_repeated_pauses_without_swipes_end_the_session(jaumo, photo):
    acc = _account_from_signup(jaumo, photo)
    jaumo.control(zapping_script=[RATE_APP] * 5)
    res, rec = _swipe(jaumo, acc, max_swipes=6, delays=NO_WAIT)
    assert res == {"status": "done", "reason": "Jaumo pause repeated 3 times without new cards (rate_app)"}, res
    assert rec.kinds("swipe") == [] and {"status": "active"} in rec.kinds("account_update")


def test_stop_during_a_jaumo_pause(jaumo, photo):
    import threading
    acc = _account_from_signup(jaumo, photo)
    jaumo.control(zapping_script=[{**RATE_APP, "unlockExpiresIn": 600}])
    rec, ev = Recorder(), threading.Event()
    r = SwipeRunner({"delays": NO_WAIT, "max_swipes": 3}, APK, acc, emit=rec, stop_event=ev)
    r.client.base_url = jaumo.base
    threading.Timer(1.0, ev.set).start()
    res = r.run()
    assert res["status"] == "stopped", "a 10 min wait can be stopped right away"


def test_no_more_profiles_answer_ends_the_session_cleanly(jaumo, photo):
    acc = _account_from_signup(jaumo, photo)
    jaumo.control(batches=0, empty_deck={"items": None, "noResult": {"title": "No more people nearby"}})
    res, rec = _swipe(jaumo, acc, max_swipes=0, max_empty_batches=2)
    assert res == {"status": "done", "reason": "no more profiles (noResult)"}, res


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


# --- stop / remove from queue (accounts list, account page) ------------------------------

def _three_accounts(api):
    cid = setup_ready(api, photos=3, max_swipes=1)
    ok(api.put("/api/settings", json={"bot": {"parallel_accounts": 3}}))
    runs = wait_runs_done(api, ok(api.post("/api/runs", json={"config_id": cid, "count": 3}))["run_ids"])
    ok(api.put("/api/settings", json={"bot": {"parallel_accounts": 1}}))
    ok(api.put("/api/config", json={"settings": {"max_swipes": 0, "delays": {**FAST_DELAYS, "between_swipes": [0.5, 0.5]}}}))
    return [r["account_id"] for r in runs]


def test_stop_running_and_remove_queued_by_account(app, api, jaumo):
    ids = _three_accounts(api)
    res = ok(api.post("/api/accounts/swipe", json={"account_ids": ids}))
    wait_until(lambda: ok(api.get("/api/stats"))["running"] == 1, msg="one worker busy")
    items = {a["id"]: a for a in ok(api.get("/api/accounts"))["items"]}
    states = sorted(items[i]["active_run"]["status"] for i in ids)
    assert states == ["queued", "queued", "running"], "1 worker: the others wait in the queue"
    queued = [i for i in ids if items[i]["active_run"]["status"] == "queued"]
    running = next(i for i in ids if items[i]["active_run"]["status"] == "running")

    ok(api.post(f"/api/accounts/{queued[0]}/stop"))
    r = wait_runs_done(api, [items[queued[0]]["active_run"]["id"]])[0]
    assert r["status"] == "stopped" and r["reason"] == "stopped before start", "taken out of the queue"
    assert ok(api.post("/api/accounts/stop", json={"account_ids": [running, queued[1]]}))["stopped"] == 2
    runs = wait_runs_done(api, res["run_ids"])
    assert all(r["status"] == "stopped" for r in runs)
    a = ok(api.get(f"/api/accounts/{running}"))
    assert a["status"] == "active" and a["active_run"] is None, "a stopped account can continue later"
    assert api.post(f"/api/accounts/{running}/stop").status_code == 409


def test_stop_from_the_accounts_page(browser, app, jaumo):
    api = app.client()
    ids = _three_accounts(api)
    ok(api.post("/api/accounts/swipe", json={"account_ids": ids}))
    wait_until(lambda: ok(api.get("/api/stats"))["running"] == 1, msg="one worker busy")
    pg = Page(browser, app).login("accounts")
    try:
        pg.p.wait_for_selector("#acc-tbody .state-badge.queued")
        assert pg.p.locator("#acc-tbody .state-badge.queued").count() == 2, "waiting accounts are marked"
        queued_row = pg.p.locator("#acc-tbody tr", has=pg.p.locator(".state-badge.queued")).first
        queued_row.locator("[data-more]").click()
        assert "Aus Warteschlange entfernen" in pg.p.inner_text(".menu [data-act=stop]")
        pg.p.click(".menu [data-act=stop]")
        pg.p.wait_for_function("document.querySelectorAll('#acc-tbody .state-badge.queued').length === 1")
        pg.p.check("#acc-all")
        pg.p.click("#bulk-stop")
        wait_until(lambda: ok(api.get("/api/stats"))["running"] + ok(api.get("/api/stats"))["queued"] == 0, msg="all stopped")
        pg.p.wait_for_function("!document.querySelector('#acc-tbody .state-badge.working, #acc-tbody .state-badge.queued')")
        pg.assert_clean("stop from accounts page")
    finally:
        pg.close()
