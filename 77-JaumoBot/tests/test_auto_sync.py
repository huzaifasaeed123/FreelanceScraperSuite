"""Automatic stats refresh: right after every session, every N minutes, never while an account works."""

from conftest import FAST_DELAYS, ok, setup_ready, wait_runs_done, wait_until

AFTER_ON = {"bot": {"sync_after_session": True}}


def _sync_runs(api, account_id=None):
    runs = ok(api.get("/api/runs", params={"kind": "sync", "limit": 200}))["items"]
    return [r for r in runs if account_id is None or r["account_id"] == account_id]


def test_stats_are_read_right_after_the_session(app, api, jaumo):
    setup_ready(api, photos=2, max_swipes=3)
    ok(api.put("/api/settings", json=AFTER_ON))
    run = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]
    acc = run["account_id"]
    wait_until(lambda: ok(api.get(f"/api/accounts/{acc}"))["stats_synced_at"], msg="stats read after the session")
    a = ok(api.get(f"/api/accounts/{acc}"))
    assert (a["likes_received"], a["profile_visits"], a["messages_received"]) == (4, 7, 2), "numbers from Jaumo"
    sync = wait_runs_done(api, [r["id"] for r in _sync_runs(api, acc)])
    assert len(sync) == 1 and sync[0]["status"] == "done"
    log = ok(api.get(f"/api/runs/{run['id']}/logs", params={"limit": 2000}))
    assert any("[STATS] Stats refresh queued" in (l["msg"] if isinstance(l, dict) else l) for l in
               (log["items"] if isinstance(log, dict) else log))


def test_after_session_refresh_can_be_switched_off(app, api, jaumo):
    setup_ready(api, photos=2, max_swipes=2)          # switches it off
    acc = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]["account_id"]
    assert _sync_runs(api) == [] and ok(api.get(f"/api/accounts/{acc}"))["stats_synced_at"] is None


def test_working_accounts_are_never_refreshed_at_the_same_time(app, api, jaumo):
    setup_ready(api, photos=2, max_swipes=2)
    acc = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]["account_id"]
    ok(api.put("/api/config", json={"settings": {"max_swipes": 0, "delays": {**FAST_DELAYS, "between_swipes": [0.4, 0.4]}}}))
    rid = ok(api.post(f"/api/accounts/{acc}/swipe"))["run_ids"][0]
    wait_until(lambda: ok(api.get(f"/api/runs/{rid}"))["status"] == "running", msg="swiping")
    r = api.post(f"/api/accounts/{acc}/sync")
    assert r.status_code == 409 and "working" in r.json()["detail"], "a refresh would swap the session's tokens"
    assert ok(api.post("/api/accounts/sync", json={"all": True}))["run_ids"] == []
    ok(api.put("/api/settings", json=AFTER_ON))
    ok(api.post(f"/api/runs/{rid}/stop"))
    wait_runs_done(api, [rid])
    wait_until(lambda: ok(api.get(f"/api/accounts/{acc}"))["stats_synced_at"], msg="refresh once the session ended")


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
