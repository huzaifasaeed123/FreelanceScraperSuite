"""Stats sync: engine (read-only Jaumo calls) and panel integration (cooldown, refresh-all delay, storage)."""

import time


from bot.engine import StatsSyncRunner
from conftest import FAST_DELAYS, ok, setup_ready, wait_runs_done, wait_until
from test_engine import APK, Recorder, _account_from_signup, photo  # noqa: F401 (fixture)


def _writes(st):
    return len(st["likes"]), len(st["dislikes"]), len(st["messages"]), len(st["registrations"]), len(st["uploads"])


# --- engine ------------------------------------------------------------------------------

def _sync(jaumo, account, **kw):
    rec = Recorder()
    r = StatsSyncRunner({"delays": FAST_DELAYS, **kw}, APK, account, emit=rec)
    r.client.base_url = jaumo.base
    return r.run(), rec


def test_sync_reads_counters_like_the_app(jaumo, photo):
    acc = _account_from_signup(jaumo, photo)
    before = _writes(jaumo.state())
    jaumo.control(unseen={"likes": 12, "visits": 30, "conversations": 5, "matches": 3, "requests": 2, "communities": 0})
    res, rec = _sync(jaumo, acc)
    st = jaumo.state()
    assert res["status"] == "done", res
    stats = rec.kinds("stats")[0]
    assert stats["counters"] == {"likes": 12, "visits": 30, "conversations": 5, "matches": 3, "requests": 2}
    assert stats["match_ids"] is None, "3 matches already known -> no list paging"
    assert st.get("root_calls") == 1 and st.get("unseen_calls") == 1 and not st.get("mutual_calls")
    assert _writes(st) == before, "a sync must not like, dislike, message, register or upload"
    assert st["bad_signatures"] == [] and st["bad_headers"] == []
    sync_reqs = [r for r in st["requests"] if r["path"] in ("/v2/", "/v2/me/unseen/")]
    assert {r["device"] for r in sync_reqs} == {acc["device_id"]}, "same device identity as at signup"


def test_sync_reads_new_match_ids_only_when_needed(jaumo, photo):
    acc = _account_from_signup(jaumo, photo)
    jaumo.control(unseen={"likes": 1, "visits": 1, "conversations": 0, "matches": 9, "requests": 0, "communities": 0},
                  mutual_ids=["9001", "9002", "9003"])
    res, rec = _sync(jaumo, acc)
    assert res["status"] == "done"
    assert rec.kinds("stats")[0]["match_ids"] == ["9001", "9002", "9003"]
    assert jaumo.state()["mutual_calls"] == 2, "3 ids at 2 per page -> follows links.next once"


def test_sync_failure_is_reported(jaumo, photo):
    acc = _account_from_signup(jaumo, photo)
    jaumo.control(unseen_status=503)
    res, rec = _sync(jaumo, acc)
    assert res["status"] == "failed" and "503" in res["reason"] and rec.kinds("stats") == []


def test_sync_refreshes_expired_token(jaumo, photo):
    acc = _account_from_signup(jaumo, photo)
    acc["access_token"] = "expired"
    res, rec = _sync(jaumo, acc)
    assert res["status"] == "done"
    assert any("access_token" in u for u in rec.kinds("account_update")), "new token is stored"


# --- panel integration -----------------------------------------------------------------------

def _one_account(api, cid):
    run = wait_runs_done(api, ok(api.post("/api/runs", json={"config_id": cid, "count": 1}))["run_ids"])[0]
    assert run["status"] == "done"
    return run["account_id"]


def test_refresh_one_account_stores_numbers_and_cooldown(app, api, jaumo):
    cid = setup_ready(api, photos=2, max_swipes=6)
    acc_id = _one_account(api, cid)
    a = ok(api.get(f"/api/accounts/{acc_id}"))
    assert (a["likes_received"], a["profile_visits"], a["messages_received"], a["stats_synced_at"]) == (None, None, None, None)
    before = len(jaumo.state()["likes"])

    res = ok(api.post(f"/api/accounts/{acc_id}/sync"))
    run = wait_runs_done(api, res["run_ids"])[0]
    assert run["kind"] == "sync" and run["status"] == "done", run
    a = ok(api.get(f"/api/accounts/{acc_id}"))
    assert (a["likes_received"], a["profile_visits"], a["messages_received"], a["requests_received"]) == (4, 7, 2, 1)
    assert a["stats_synced_at"] and a["stats_sync_error"] == ""
    assert a["matches_count"] >= 3
    assert len(jaumo.state()["likes"]) == before, "refresh sends no likes"
    kinds = [e["kind"] for e in ok(api.get(f"/api/accounts/{acc_id}/events", params={"limit": 500}))]
    assert "sync" in kinds

    r = api.post(f"/api/accounts/{acc_id}/sync")
    assert r.status_code == 409 and "wait" in r.json()["detail"], "15 s cooldown per account"

    s = ok(api.get("/api/accounts/summary"))
    assert s["likes_received"] == 4 and s["visits_received"] == 7 and s["messages_received"] == 2
    assert s["stats_synced_accounts"] == 1 and s["likes_sent"] == a["liked_count"]


def test_refresh_all_runs_one_by_one_with_delay(app, api, jaumo):
    cid = setup_ready(api, photos=4, max_swipes=2)
    ok(api.put("/api/settings", json={"bot": {"parallel_accounts": 3, "sync_delay_seconds": 2}}))
    ids = ok(api.post("/api/runs", json={"config_id": cid, "count": 3}))["run_ids"]
    wait_runs_done(api, ids)
    res = ok(api.post("/api/accounts/sync", json={"all": True}))
    assert len(res["run_ids"]) == 3 and res["skipped"] == []
    runs = wait_runs_done(api, res["run_ids"], timeout=60)
    assert all(r["status"] == "done" for r in runs)
    for a, b in zip(runs, runs[1:]):
        assert a["finished_at"] <= b["started_at"], "one account after another"
        gap = time.mktime(time.strptime(b["started_at"][:19], "%Y-%m-%dT%H:%M:%S")) - \
            time.mktime(time.strptime(a["finished_at"][:19], "%Y-%m-%dT%H:%M:%S"))
        assert gap >= 1, f"delay between accounts expected, gap {gap}s"
    again = ok(api.post("/api/accounts/sync", json={"all": True}))
    assert again["run_ids"] == [] and len(again["skipped"]) == 3, "cooldown applies to refresh-all too"


def test_sync_is_not_counted_as_account_work(app, api, jaumo):
    cid = setup_ready(api, photos=2, max_swipes=1)
    acc_id = _one_account(api, cid)
    jaumo.control(slow_ms=700)
    rid = ok(api.post(f"/api/accounts/{acc_id}/sync"))["run_ids"][0]
    wait_until(lambda: ok(api.get(f"/api/runs/{rid}"))["status"] == "running", msg="sync running")
    st = ok(api.get("/api/stats"))
    assert st["running"] == 0 and st["syncing"] == 1
    assert not ok(api.get(f"/api/accounts/{acc_id}"))["working"]
    wait_runs_done(api, [rid], timeout=60)


def test_matches_found_by_sync_reach_messaging(app, api, jaumo):
    cid = setup_ready(api, photos=2, max_swipes=3, like_ratio=0.0, messaging_enabled=True, message_templates=["Hi"])
    acc_id = _one_account(api, cid)
    assert ok(api.get(f"/api/accounts/{acc_id}"))["matches_count"] == 0
    jaumo.control(unseen={"likes": 3, "visits": 2, "conversations": 0, "matches": 3, "requests": 0, "communities": 0},
                  mutual_ids=["9001", "9002", "9003"])
    wait_runs_done(api, ok(api.post(f"/api/accounts/{acc_id}/sync"))["run_ids"])
    a = ok(api.get(f"/api/accounts/{acc_id}"))
    assert sorted(a["matches"]) == ["9001", "9002", "9003"] and a["pending_messages"] == 3
    mrun = wait_runs_done(api, ok(api.post("/api/messages", json={"config_id": cid, "account_ids": [acc_id]}))["run_ids"])[0]
    assert mrun["messages_sent"] == 3
    assert sorted(m["to"] for m in jaumo.state()["messages"]) == ["9001", "9002", "9003"]


def test_failed_sync_keeps_old_numbers(app, api, jaumo):
    cid = setup_ready(api, photos=2, max_swipes=1)
    acc_id = _one_account(api, cid)
    jaumo.control(unseen_status=503)
    run = wait_runs_done(api, ok(api.post(f"/api/accounts/{acc_id}/sync"))["run_ids"])[0]
    assert run["status"] == "failed"
    a = ok(api.get(f"/api/accounts/{acc_id}"))
    assert a["likes_received"] is None and "503" in a["stats_sync_error"]


def test_sync_validation(app, api):
    assert api.post("/api/accounts/sync", json={}).status_code == 422
    assert api.post("/api/accounts/999/sync").status_code == 404
    for v in (1, 601):
        assert api.put("/api/settings", json={"bot": {"parallel_accounts": 1, "sync_delay_seconds": v}}).status_code == 422


def test_saving_workers_keeps_refresh_delay(app, api):
    ok(api.put("/api/settings", json={"bot": {"parallel_accounts": 1, "sync_delay_seconds": 30}}))
    ok(api.put("/api/settings", json={"bot": {"parallel_accounts": 3}}))
    assert ok(api.get("/api/settings"))["bot"] == {"parallel_accounts": 3, "sync_delay_seconds": 30,
                                                   "sync_after_session": True, "auto_sync_minutes": 30}
