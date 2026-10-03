"""Jaumo "Verification required" (HTTP 403, code 4031) is reported as its own status, not as 'blocked'."""

from bot.engine import BotRunner, JaumoClient
from conftest import FAST_DELAYS, ok, setup_ready, wait_runs_done
from test_engine import APK, Recorder, photo  # noqa: F401 (fixture)
from test_ui import Page, browser  # noqa: F401 (fixture)

VERIFY_BODY = {"missingField": "verification",
               "primaryAction": {"type": "verification", "caption": "Verify your profile"},
               "title": "Verification required", "subtitle": "Please verify your profile to contact Amo",
               "error": {"message": "Verification required Please verify your profile", "code": 4031}}


def test_detects_verification_vs_a_normal_403():
    assert JaumoClient.verification_block(403, VERIFY_BODY) == \
        "Verification required — Please verify your profile to contact Amo"
    assert JaumoClient.verification_block(403, {"error": {"code": 4031}}) == "Verification required"
    assert JaumoClient.verification_block(403, {"error": "restricted"}) is None   # a real block
    assert JaumoClient.verification_block(200, VERIFY_BODY) is None


# --- engine ------------------------------------------------------------------------------

def test_session_ends_as_verification_not_blocked(jaumo, photo):
    jaumo.control(verification_required=True)
    rec = Recorder()
    r = BotRunner({"delays": FAST_DELAYS, "max_swipes": 10, "block_threshold": 3, "like_ratio": 1.0},
                  APK, photo, emit=rec)
    r.client.base_url = jaumo.base
    res = r.run()
    assert res["status"] == "verification_required", res
    assert "Verification required" in res["reason"]
    assert {"status": "verification_required", "verify_info": res["reason"]} in rec.kinds("account_update")
    assert not any(u.get("status") == "blocked" for u in rec.kinds("account_update")), "never labelled blocked"
    assert rec.kinds("verification")[0]["message"] == res["reason"]
    assert len(jaumo.state()["likes"]) == 0, "nothing counted as a like"


# --- panel -------------------------------------------------------------------------------

def test_account_shows_verification_required(app, api, jaumo):
    cid = setup_ready(api, photos=2, max_swipes=5, like_ratio=1.0, block_threshold=3)
    jaumo.control(verification_required=True)
    run = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]
    assert run["status"] == "verification_required" and "Verification required" in run["reason"]
    a = ok(api.get(f"/api/accounts/{run['account_id']}"))
    assert a["status"] == "verification_required", "not 'blocked'"
    assert "Verification required" in a["verify_info"]
    assert a["state"] == "verification"
    kinds = [e["kind"] for e in ok(api.get(f"/api/accounts/{a['id']}/events", params={"limit": 50}))]
    assert "verification" in kinds and "status" not in [e for e in kinds if e == "blocked"]
    # the accounts list filter has its own group, separate from "blocked"
    assert ok(api.get("/api/accounts", params={"state": "verification"}))["total"] == 1
    assert ok(api.get("/api/accounts", params={"state": "blocked"}))["total"] == 0


def test_account_page_shows_jaumo_message(browser, app, jaumo):
    api = app.client()
    cid = setup_ready(api, photos=2, max_swipes=5, like_ratio=1.0, block_threshold=3)
    jaumo.control(verification_required=True)
    acc = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]["account_id"]
    pg = Page(browser, app).login(f"account/{acc}")
    try:
        pg.p.wait_for_selector("#acc-hero .acc-title")
        hero = pg.p.inner_text("#acc-hero")
        assert "Verifizierung nötig" in pg.p.inner_text("#acc-hero .acc-title .badge")
        assert "Jaumo verlangt eine Verifizierung" in hero
        assert "Please verify your profile" in hero, "shows exactly what Jaumo said"
        pg.assert_clean("verification account")
    finally:
        pg.close()


def test_blocked_and_verification_accounts_can_be_retried(app, api, jaumo):
    cid = setup_ready(api, photos=3, max_swipes=5, like_ratio=1.0, block_threshold=3)
    jaumo.control(verification_required=True)
    vacc = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]["account_id"]
    assert ok(api.get(f"/api/accounts/{vacc}"))["status"] == "verification_required"
    jaumo.control(block_after_likes=2, verification_required=False)
    bacc = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]["account_id"]
    assert ok(api.get(f"/api/accounts/{bacc}"))["status"] == "blocked"

    # both are retryable; once Jaumo is fine again, swiping heals them to active
    jaumo.control(block_after_likes=0)
    ok(api.put("/api/config", json={"settings": {"max_swipes": 2}}))
    for acc in (vacc, bacc):
        r = ok(api.post(f"/api/accounts/{acc}/swipe"))
        run = wait_runs_done(api, r["run_ids"])[0]
        assert run["status"] == "done", run
        assert ok(api.get(f"/api/accounts/{acc}"))["status"] == "active", "retry heals the account"


def test_blocked_accounts_are_not_auto_refreshed(app, api, jaumo):
    """A blocked account must not generate stats requests (saves the proxy). Manual bulk/per-account refuse it;
    the account stays retryable via 'Weiter swipen'."""
    cid = setup_ready(api, photos=2, max_swipes=5, like_ratio=1.0, block_threshold=2)
    jaumo.control(block_after_likes=1)
    acc = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]["account_id"]
    assert ok(api.get(f"/api/accounts/{acc}"))["status"] == "blocked"
    n_before = len([r for r in jaumo.state()["requests"] if r["path"] == "/v2/me/unseen/"])

    # "refresh all" skips it
    res = ok(api.post("/api/accounts/sync", json={"all": True}))
    assert acc not in res["run_ids"] and res["run_ids"] == []
    # a direct refresh is refused with a clear reason
    r = api.post(f"/api/accounts/{acc}/sync")
    assert r.status_code == 409 and "blocked by Jaumo" in r.json()["detail"]
    # no extra stats request hit Jaumo through the proxy
    assert len([x for x in jaumo.state()["requests"] if x["path"] == "/v2/me/unseen/"]) == n_before


def test_like_limit_is_its_own_status_not_blocked(jaumo, photo):
    from bot.engine import BotRunner, JaumoClient
    assert JaumoClient.like_limit(403, {"error": {"code": 4032}}) is not None
    assert JaumoClient.like_limit(403, {"dialog": {"options": [{"referrer": "like_capped"}]}}) is not None
    assert JaumoClient.like_limit(403, {"error": {"code": 4031}}) is None
    jaumo.control(like_capped=True)
    rec = Recorder()
    r = BotRunner({"delays": FAST_DELAYS, "max_swipes": 10, "block_threshold": 3, "like_ratio": 1.0},
                  APK, photo, emit=rec)
    r.client.base_url = jaumo.base
    res = r.run()
    assert res["status"] == "limit_reached", res
    assert not any(u.get("status") == "blocked" for u in rec.kinds("account_update"))


def test_permanent_lock_stays_blocked(app, api, jaumo):
    from bot.engine import SwipeRunner
    import time
    from test_engine import _account_from_signup
    cid = setup_ready(api, photos=2, max_swipes=2)
    acc_id = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]["account_id"]
    # force a fresh login on the next run, then make refresh return the permanent lock
    jaumo.control(account_locked=True)
    ok(api.put("/api/config", json={"settings": {"max_swipes": 2}}))
    run = wait_runs_done(api, ok(api.post(f"/api/accounts/{acc_id}/swipe"))["run_ids"])[0]
    assert run["status"] == "blocked" and "locked" in run["reason"].lower(), run
    a = ok(api.get(f"/api/accounts/{acc_id}"))
    assert a["status"] == "blocked"
    # a permanently locked account is never auto-refreshed and a manual refresh is refused
    assert ok(api.post("/api/accounts/sync", json={"all": True}))["run_ids"] == []
    assert api.post(f"/api/accounts/{acc_id}/sync").status_code == 409
