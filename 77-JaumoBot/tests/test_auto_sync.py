"""Stats: read by the session itself (every N swipes + at the end), idle accounts on a timer, login reuse."""

import time

from bot.engine import StatsSyncRunner, SwipeRunner
from conftest import FAST_DELAYS, ok, setup_ready, wait_runs_done, wait_until
from test_engine import APK, Recorder, _account_from_signup, photo  # noqa: F401 (fixture)

AFTER_ON = {"bot": {"sync_after_session": True}}


def _sync_runs(api, account_id=None):
    runs = ok(api.get("/api/runs", params={"kind": "sync", "limit": 200}))["items"]
    return [r for r in runs if account_id is None or r["account_id"] == account_id]


def _logs(api, run_id):
    return [l["msg"] for l in ok(api.get(f"/api/runs/{run_id}/logs", params={"limit": 5000}))]


def _token_renewals(jaumo, since=0):
    return [r for r in jaumo.state()["requests"][since:] if r["path"] == "/v2/auth/token"]


# --- engine: login reuse (A) -------------------------------------------------------------------

def test_valid_login_is_reused_and_expired_one_renewed(jaumo, photo):
    acc = _account_from_signup(jaumo, photo)
    assert acc.get("token_expires_at") is None, "signup itself gives no expiry"
    n = len(jaumo.state()["requests"])
    rec = Recorder()
    r = StatsSyncRunner({"delays": FAST_DELAYS}, APK, {**acc, "token_expires_at": time.time() + 3000}, emit=rec)
    r.client.base_url = jaumo.base
    assert r.run()["status"] == "done"
    assert _token_renewals(jaumo, n) == [], "valid for 50 more minutes -> no new login"
    assert not any("access_token" in u for u in rec.kinds("account_update"))
    assert sum(1 for x in jaumo.state()["requests"][n:]) == 2, "a refresh costs 2 requests (API root + counters)"

    n = len(jaumo.state()["requests"])
    rec = Recorder()
    r = StatsSyncRunner({"delays": FAST_DELAYS}, APK, {**acc, "token_expires_at": time.time() + 60}, emit=rec)
    r.client.base_url = jaumo.base
    assert r.run()["status"] == "done"
    assert len(_token_renewals(jaumo, n)) == 1, "less than 5 min left -> renewed once"
    upd = next(u for u in rec.kinds("account_update") if "access_token" in u)
    assert 3500 < upd["token_expires_at"] - time.time() <= 3601, "new expiry stored from expires_in"


# --- engine: stats read by the session itself (B, C) --------------------------------------------

def test_swipe_session_reads_stats_with_its_own_login(jaumo, photo):
    acc = {**_account_from_signup(jaumo, photo), "token_expires_at": time.time() + 3000}
    n = len(jaumo.state()["requests"])
    rec = Recorder()
    r = SwipeRunner({"delays": FAST_DELAYS, "max_swipes": 7, "stats_every_swipes": 3, "stats_at_end": True},
                    APK, acc, emit=rec)
    r.client.base_url = jaumo.base
    res = r.run()
    assert res["status"] == "done" and len(rec.kinds("swipe")) == 7
    assert len(rec.kinds("stats")) == 3, "after swipe 3, after swipe 6, and at the end"
    assert _token_renewals(jaumo, n) == [], "no second login: the session's own token is used"
    tokens = {x["token"] for x in jaumo.state()["requests"][n:] if x["token"]}
    assert tokens == {acc["access_token"]}, "every request (swipes + stats) with the same login"


def test_stopped_session_still_reads_its_stats(jaumo, photo):
    import threading
    acc = {**_account_from_signup(jaumo, photo), "token_expires_at": time.time() + 3000}
    rec, ev = Recorder(), threading.Event()
    r = SwipeRunner({"delays": {**FAST_DELAYS, "between_swipes": [0.3, 0.3]}, "max_swipes": 0, "stats_every_swipes": 0,
                     "stats_at_end": True}, APK, acc, emit=rec, stop_event=ev)
    r.client.base_url = jaumo.base
    threading.Timer(1.0, ev.set).start()
    assert r.run()["status"] == "stopped"
    assert len(rec.kinds("stats")) == 1, "final read also after a stop"


def test_stats_off_means_no_reads(jaumo, photo):
    acc = _account_from_signup(jaumo, photo)
    rec = Recorder()
    r = SwipeRunner({"delays": FAST_DELAYS, "max_swipes": 5, "stats_every_swipes": 0, "stats_at_end": False},
                    APK, acc, emit=rec)
    r.client.base_url = jaumo.base
    assert r.run()["status"] == "done" and rec.kinds("stats") == []


# --- panel -----------------------------------------------------------------------------------------

def test_stats_are_read_by_the_session_itself(app, api, jaumo):
    setup_ready(api, photos=2, max_swipes=3)
    ok(api.put("/api/settings", json=AFTER_ON))
    run = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]
    acc = run["account_id"]
    a = ok(api.get(f"/api/accounts/{acc}"))
    assert a["stats_synced_at"], "read at the end of the session"
    assert (a["likes_received"], a["profile_visits"], a["messages_received"]) == (4, 7, 2), "numbers from Jaumo"
    assert a["token_expires_at"] and a["token_expires_at"] > time.time() + 3000, "expiry stored"
    assert _sync_runs(api) == [], "no separate refresh job"
    assert any("[STATS] end of session" in m for m in _logs(api, run["id"]))
    kinds = [e["kind"] for e in ok(api.get(f"/api/accounts/{acc}/events", params={"limit": 500}))]
    assert "sync" in kinds, "stored in the database like a manual refresh"


def test_after_session_refresh_can_be_switched_off(app, api, jaumo):
    setup_ready(api, photos=2, max_swipes=2)          # switches it off
    acc = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]["account_id"]
    assert _sync_runs(api) == [] and ok(api.get(f"/api/accounts/{acc}"))["stats_synced_at"] is None


def test_working_accounts_are_never_refreshed_at_the_same_time(app, api, jaumo):
    setup_ready(api, photos=2, max_swipes=2)
    acc = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]["account_id"]
    ok(api.put("/api/settings", json=AFTER_ON))       # the swipe session below reads at its end
    ok(api.put("/api/config", json={"settings": {"max_swipes": 0, "delays": {**FAST_DELAYS, "between_swipes": [0.4, 0.4]}}}))
    rid = ok(api.post(f"/api/accounts/{acc}/swipe"))["run_ids"][0]
    wait_until(lambda: ok(api.get(f"/api/runs/{rid}"))["status"] == "running", msg="swiping")
    r = api.post(f"/api/accounts/{acc}/sync")
    assert r.status_code == 409 and "working" in r.json()["detail"], "a refresh would swap the session's tokens"
    assert ok(api.post("/api/accounts/sync", json={"all": True}))["run_ids"] == []
    ok(api.post(f"/api/runs/{rid}/stop"))
    wait_runs_done(api, [rid])
    wait_until(lambda: ok(api.get(f"/api/accounts/{acc}"))["stats_synced_at"], msg="the stopped session read its stats")


def test_a_session_has_priority_over_a_queued_refresh(app, api, jaumo):
    setup_ready(api, photos=3, max_swipes=1, messaging_enabled=True, message_templates=["Hi"])
    runs = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 2}))["run_ids"])
    a1, a2 = runs[0]["account_id"], runs[1]["account_id"]
    jaumo.control(slow_ms=600)
    ok(api.put("/api/settings", json={"bot": {"sync_delay_seconds": 5}}))
    first = ok(api.post("/api/accounts/sync", json={"account_ids": [a1, a2]}))["run_ids"]
    assert len(first) == 2
    swipe = ok(api.post(f"/api/accounts/{a2}/swipe"))["run_ids"][0]   # a2's refresh is still queued
    r2 = wait_runs_done(api, [first[1]], timeout=60)[0]
    assert r2["status"] == "stopped", "the queued refresh of a2 was removed for the session"
    s = wait_runs_done(api, [swipe], timeout=60)[0]
    assert s["status"] == "done", s
    jaumo.control(slow_ms=0)


def test_all_accounts_are_refreshed_on_a_timer(make_app, jaumo):
    app = make_app(AUTO_SYNC_TICK_SECONDS="0.3", AUTO_SYNC_INTERVAL_SECONDS="3")
    api = app.client()
    setup_ready(api, photos=3, max_swipes=1)
    ok(api.put("/api/settings", json={"bot": {"sync_delay_seconds": 2}}))
    ids = [r["account_id"] for r in wait_runs_done(api, ok(api.post("/api/runs", json={"count": 2}))["run_ids"])]
    wait_until(lambda: all(ok(api.get(f"/api/accounts/{i}"))["stats_synced_at"] for i in ids), timeout=40,
               msg="timer refreshed every account")
    first = {i: ok(api.get(f"/api/accounts/{i}"))["stats_synced_at"] for i in ids}
    wait_until(lambda: all(ok(api.get(f"/api/accounts/{i}"))["stats_synced_at"] != first[i] for i in ids),
               timeout=40, msg="and again on the next round")
    assert all(r["status"] in ("done", "queued", "running") for r in _sync_runs(api))


def test_timer_off_and_validation(app, api):
    assert ok(api.get("/api/settings"))["bot"]["auto_sync_minutes"] == 30, "default every 30 minutes"
    ok(api.put("/api/settings", json={"bot": {"auto_sync_minutes": 0}}))
    assert ok(api.get("/api/settings"))["bot"]["auto_sync_minutes"] == 0
    for bad in (3, -1, 2000):
        assert api.put("/api/settings", json={"bot": {"auto_sync_minutes": bad}}).status_code == 422
