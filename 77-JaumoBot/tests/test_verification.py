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
