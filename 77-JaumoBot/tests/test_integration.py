"""
Bot <-> admin panel integration: launches go through the real API, the bot talks to the
fake Jaumo, and every number must agree across Jaumo, runs, accounts, summary, events,
stats, photos and export.
"""

import json
import threading
import time

import pytest
from websockets.sync.client import connect

from conftest import ok, setup_ready, wait_runs_done, wait_until
from fake_proxy import FakeProxy


def launch(api, cid, count=1, names=None):
    return ok(api.post("/api/runs", json={"config_id": cid, "count": count, "names": names or []}))["run_ids"]


def accounts(api, **params):
    return ok(api.get("/api/accounts", params={"limit": 500, **params}))


# --- the core contract ----------------------------------------------------------------

def test_full_flow_numbers_agree_everywhere(app, api, jaumo):
    cid = setup_ready(api, photos=5, max_swipes=6)
    ok(api.put("/api/settings", json={"bot": {"parallel_accounts": 2}}))
    ids = launch(api, cid, 3)
    runs = wait_runs_done(api, ids)
    st = jaumo.state()
    assert st["bad_signatures"] == [] and st["bad_headers"] == []

    # runs
    assert [r["status"] for r in runs] == ["done"] * 3
    assert {r["worker"] for r in runs} <= {1, 2}
    assert len({r["photo"] for r in runs}) == 3 and len({r["requested_name"] for r in runs}) == 3
    assert all(r["swipes"] == 6 and r["account_id"] for r in runs)

    # accounts vs runs vs Jaumo
    acc = {a["id"]: a for a in accounts(api)["items"]}
    assert len(acc) == 3
    users = {u["id"]: u for u in st["users"].values()}
    for r in runs:
        a = acc[r["account_id"]]
        full = ok(api.get(f"/api/accounts/{a['id']}"))
        assert a["state"] == "active" and a["status"] == "active" and not a["working"]
        assert a["worker"] == r["worker"] and a["photo"] == r["photo"] and a["name"] == r["requested_name"]
        assert a["jaumo_id"] and int(a["jaumo_id"]) in users, "jaumo id from /me must be stored"
        assert a["photo_uploaded"] and a["last_activity_at"]
        assert (a["liked_count"], a["disliked_count"], a["matches_count"]) == (r["liked"], r["disliked"], r["matches"])
        assert a["actions"] == a["liked_count"] + a["disliked_count"] + a["messages_sent"]
        assert len(full["liked"]) == a["liked_count"] and len(full["disliked"]) == a["disliked_count"]
        assert set(full["matches"]) <= set(full["liked"])
        u = users[int(a["jaumo_id"])]
        assert u["likes"] == a["liked_count"] and u["name"] == a["name"] and u["gallery"] == 1
        assert [x["id"] for x in ok(api.get(f"/api/accounts/{a['id']}/runs"))] == [r["id"]]
        # activity timeline
        ev = ok(api.get(f"/api/accounts/{a['id']}/events", params={"limit": 1000}))
        kinds = [e["kind"] for e in ev]
        assert kinds.count("like") + kinds.count("match") == a["liked_count"]
        assert kinds.count("match") == a["matches_count"] and kinds.count("dislike") == a["disliked_count"]
        assert "created" in kinds and "status" in kinds

    # summary cards == sums == /api/stats
    tot = lambda k: sum(a[k] for a in acc.values())  # noqa: E731
    s = ok(api.get("/api/accounts/summary", params={"tz_offset": 0}))
    assert s["accounts"] == 3 and s["accounts_today"] == 3
    assert s["likes"] == tot("liked_count") == s["likes_today"]
    assert s["matches"] == tot("matches_count") == s["matches_today"]
    assert s["actions"] == tot("actions") == s["actions_today"]
    assert s["working"] == 0 and s["messages_received_synced"] == 0
    stats = ok(api.get("/api/stats"))
    assert (stats["liked"], stats["matches"], stats["running"], stats["queued"]) == (s["likes"], s["matches"], 0, 0)
    assert stats["accounts_by_status"] == {"active": 3}
    daily = ok(api.get("/api/stats/daily", params={"days": 7, "tz_offset": 0}))
    assert daily[-1]["created"] == 3 and daily[-1]["active"] == 3 and daily[-1]["likes"] == s["likes"]

    # photo library knows who uses each photo
    photos = {p["name"]: p for p in ok(api.get("/api/photos"))}
    for r in runs:
        assert photos[r["photo"]]["status"] == "used" and photos[r["photo"]]["account"]["id"] == r["account_id"]
    assert sum(p["status"] == "available" for p in photos.values()) == 2

    # export carries the same data
    lines = [json.loads(x) for x in api.get("/api/accounts/export").text.splitlines()]
    assert sorted(x["id"] for x in lines) == sorted(acc) and all(x["worker"] for x in lines)


def test_list_filters_search_sort_pagination(app, api, jaumo):
    cid = setup_ready(api, photos=6, max_swipes=4)
    ok(api.put("/api/settings", json={"bot": {"parallel_accounts": 2}}))
    jaumo.control(block_after_likes=1)
    runs = wait_runs_done(api, launch(api, cid, 2, ["Alpha", "Beta"]))
    jaumo.control(block_after_likes=0)
    runs += wait_runs_done(api, launch(api, cid, 2, ["Gamma", "Delta"]))
    by_name = {a["name"]: a for a in accounts(api)["items"]}

    blocked = accounts(api, state="blocked")["items"]
    assert {a["name"] for a in blocked} <= {"Alpha", "Beta"} and all(a["state"] == "blocked" for a in blocked)
    assert accounts(api, state="active")["total"] + accounts(api, state="blocked")["total"] == 4
    assert accounts(api, q="gam")["items"][0]["name"] == "Gamma"
    assert accounts(api, q=by_name["Delta"]["jaumo_id"])["items"][0]["name"] == "Delta"
    assert accounts(api, q=str(by_name["Beta"]["id"]))["items"][0]["name"] == "Beta"
    for w in {a["worker"] for a in by_name.values()}:
        got = accounts(api, worker=w)["items"]
        assert got and all(a["worker"] == w for a in got)
        assert accounts(api, q=f"worker-{w}")["total"] == len(got)
    likes = [a["liked_count"] for a in accounts(api, sort="liked_count", order="desc")["items"]]
    assert likes == sorted(likes, reverse=True)
    p1 = accounts(api, limit=3, offset=0)
    p2 = ok(api.get("/api/accounts", params={"limit": 3, "offset": 3}))
    assert p1["total"] == 4 and len(p1["items"]) == 3 and len(p2["items"]) == 1
    assert not {a["id"] for a in p1["items"]} & {a["id"] for a in p2["items"]}
    exp = api.get("/api/accounts/export", params={"state": "blocked"}).text.splitlines()
    assert len(exp) == len(blocked)


# --- live updates (what the panel shows in real time) -------------------------------------

def test_websockets_stream_run_account_and_logs(app, api, jaumo):
    cid = setup_ready(api, photos=2, max_swipes=8,
                      delays={k: [0.05, 0.1] for k in ("after_signup", "after_location", "after_refresh", "after_profile",
                                                         "before_photo", "after_photo", "between_swipes", "between_batches", "before_message")})
    cookie = {"Cookie": f"jb_session={api.cookies['jb_session']}"}
    ws = app.url.replace("http", "ws")
    events, logs, activity = [], [], []

    def reader(url, sink, stop):
        with connect(url, additional_headers=cookie, open_timeout=10) as c:
            while not stop.is_set():
                try:
                    sink.append(json.loads(c.recv(timeout=0.5)))
                except TimeoutError:
                    pass
                except Exception:   # server closed the socket at teardown
                    return

    stop = threading.Event()
    t1 = threading.Thread(target=reader, args=(ws + "/ws/events", events, stop), daemon=True)
    t1.start()
    time.sleep(0.5)
    rid = launch(api, cid, 1)[0]
    threading.Thread(target=reader, args=(ws + f"/ws/runs/{rid}", logs, stop), daemon=True).start()
    acc_id = wait_until(lambda: ok(api.get(f"/api/runs/{rid}"))["account_id"], msg="account created")
    threading.Thread(target=reader, args=(ws + f"/ws/accounts/{acc_id}", activity, stop), daemon=True).start()
    wait_runs_done(api, [rid])
    time.sleep(0.8)
    stop.set()

    statuses = [e["run"]["status"] for e in events if e.get("type") == "run" and e["run"]["id"] == rid]
    assert statuses[0] in ("queued", "running") and statuses[-1] == "done" and "running" in statuses
    assert any(e.get("type") == "account" for e in events)
    assert any(m.get("type") == "log" for m in logs) and any(m.get("type") == "run" for m in logs)
    kinds = {m["event"]["kind"] for m in activity if m.get("type") == "activity"}
    assert kinds & {"like", "dislike", "match"}, activity[:5]


def test_websocket_rejects_without_login(app):
    with pytest.raises(Exception):
        with connect(app.url.replace("http", "ws") + "/ws/events", open_timeout=5) as c:
            c.recv(timeout=3)


# --- account states and APK health ------------------------------------------------------

def test_blocked_account_and_apk_health(app, api, jaumo):
    cid = setup_ready(api, photos=2, max_swipes=0, like_ratio=1.0, block_threshold=2)
    jaumo.control(block_after_likes=3)
    run = wait_runs_done(api, launch(api, cid, 1))[0]
    assert run["status"] == "blocked" and run["liked"] == 3
    a = ok(api.get(f"/api/accounts/{run['account_id']}"))
    assert a["status"] == "blocked" and a["state"] == "blocked" and a["liked_count"] == 3
    assert ok(api.get("/api/stats"))["accounts_by_status"] == {"blocked": 1}
    apk = ok(api.get("/api/apk-profiles"))[0]
    assert apk["ok_count"] == 1 and apk["fail_streak"] == 0 and apk["health"] == "ok"


def test_banned_apk_flow_disable_and_switch(app, api, jaumo):
    cid = setup_ready(api, photos=6)
    bad = ok(api.post("/api/apk-profiles", json={"name": "Old", "client_id": "banned-client", "sign_secret": "banned-secret", "user_agent": "UA"}))
    good = next(a for a in ok(api.get("/api/apk-profiles")) if a["name"] == "Good APK")
    conf = ok(api.get("/api/configs"))[0]
    ok(api.put(f"/api/configs/{cid}", json={"name": conf["name"], "apk_profile_id": bad["id"], "settings": conf["settings"]}))
    runs = wait_runs_done(api, launch(api, cid, 3))
    assert all(r["status"] == "failed" and "client token" in r["reason"] for r in runs)
    assert accounts(api)["total"] == 0, "no account is stored when signup never happened"
    old = next(a for a in ok(api.get("/api/apk-profiles")) if a["id"] == bad["id"])
    assert old["fail_streak"] == 3 and old["health"] == "failing" and "401" in old["last_error"]
    assert [w["name"] for w in ok(api.get("/api/stats"))["apk_warnings"]] == ["Old"]
    # names/photos reserved by the failed runs are free again
    assert sum(p["status"] == "available" for p in ok(api.get("/api/photos"))) == 6
    ok(api.patch(f"/api/apk-profiles/{bad['id']}", json={"enabled": False}))
    r = api.post("/api/runs", json={"config_id": cid, "count": 1})
    assert r.status_code == 422 and "disabled" in r.json()["detail"]
    ok(api.post(f"/api/apk-profiles/{bad['id']}/move-configs", json={"to_apk_profile_id": good["id"]}))
    assert ok(api.get("/api/stats"))["apk_warnings"] == []
    run = wait_runs_done(api, launch(api, cid, 1))[0]
    assert run["status"] == "done"
    r = api.delete(f"/api/apk-profiles/{good['id']}")
    assert r.status_code == 409, "an APK profile in use cannot be deleted"


# --- messaging job ------------------------------------------------------------------------

def test_messaging_job_end_to_end(app, api, jaumo):
    cid = setup_ready(api, photos=2, max_swipes=9, like_ratio=1.0, message_templates=["Hallo :)"])
    run = wait_runs_done(api, launch(api, cid, 1))[0]
    acc_id = run["account_id"]
    a = ok(api.get(f"/api/accounts/{acc_id}"))
    assert a["matches_count"] == 3 and a["pending_messages"] == 3

    r = api.post("/api/messages", json={"config_id": cid, "account_ids": [acc_id]})
    assert r.status_code == 422 and "Messaging is turned off" in r.json()["detail"]
    conf = ok(api.get("/api/configs"))[0]
    ok(api.put(f"/api/configs/{cid}", json={"name": conf["name"], "apk_profile_id": conf["apk_profile_id"],
                                            "settings": {**conf["settings"], "messaging_enabled": True}}))
    mids = ok(api.post("/api/messages", json={"config_id": cid, "account_ids": [acc_id]}))["run_ids"]
    mrun = wait_runs_done(api, mids)[0]
    assert mrun["kind"] == "message" and mrun["status"] == "done" and mrun["messages_sent"] == 3

    a = ok(api.get(f"/api/accounts/{acc_id}"))
    assert sorted(a["messaged"]) == sorted(a["matches"]) and a["messages_sent"] == 3 and a["pending_messages"] == 0
    assert a["actions"] == a["liked_count"] + a["disliked_count"] + 3
    sent = jaumo.state()["messages"]
    assert sorted(m["to"] for m in sent) == sorted(a["matches"]) and {m["form"]["text"] for m in sent} == {"Hallo :)"}
    kinds = [e["kind"] for e in ok(api.get(f"/api/accounts/{acc_id}/events", params={"limit": 500}))]
    assert kinds.count("message") == 3
    assert ok(api.post("/api/messages", json={"config_id": cid, "account_ids": []}))["run_ids"] == []
    s = ok(api.get("/api/accounts/summary"))
    assert s["messages_sent"] == 3 and s["actions"] == a["actions"]
    assert {r["id"] for r in ok(api.get(f"/api/accounts/{acc_id}/runs"))} == {run["id"], mrun["id"]}


# --- names & photos are global -------------------------------------------------------------

def test_names_and_photos_never_reused_across_launches(app, api, jaumo):
    cid = setup_ready(api, photos=4, max_swipes=1, name_source="custom", name_pool=["Ana", "Bea", "Cleo", "Dora", "Eva"])
    first = wait_runs_done(api, launch(api, cid, 2, ["Ana"]))
    assert first[0]["requested_name"] == "Ana"
    r = api.post("/api/runs", json={"config_id": cid, "count": 1, "names": ["ana"]})
    assert r.status_code == 422 and "already used" in r.json()["detail"]
    second = wait_runs_done(api, launch(api, cid, 2))
    names = [x["requested_name"] for x in first + second]
    photos = [x["photo"] for x in first + second]
    assert len(set(names)) == 4 and len(set(photos)) == 4
    r = api.post("/api/runs", json={"config_id": cid, "count": 1})
    assert r.status_code == 422 and "photos" in r.json()["detail"], "4 photos -> 4 accounts"
    ok(api.put("/api/settings", json={"identity": {"unique_names": True, "unique_photos": False}}))
    remaining = ({"Ana", "Bea", "Cleo", "Dora", "Eva"} - set(names)).pop()
    third = wait_runs_done(api, launch(api, cid, 1))[0]
    assert third["status"] == "done" and third["requested_name"] == remaining, "the one unused name is picked"
    r = api.post("/api/runs", json={"config_id": cid, "count": 1})
    assert r.status_code == 422 and "names" in r.json()["detail"]


def test_concurrent_launches_never_share_name_or_photo(app, api, jaumo):
    cid = setup_ready(api, photos=24, max_swipes=1)
    ok(api.put("/api/settings", json={"bot": {"parallel_accounts": 4}}))
    out = []
    ts = [threading.Thread(target=lambda: out.append(api.post("/api/runs", json={"config_id": cid, "count": 3}))) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    ids = [i for r in out for i in ok(r)["run_ids"]]
    runs = wait_runs_done(api, ids, timeout=120)
    assert len(ids) == 24
    assert len({r["requested_name"] for r in runs}) == 24 and len({r["photo"] for r in runs}) == 24
    assert all(r["status"] == "done" for r in runs)


# --- queue: one by one / parallel workers ----------------------------------------------------

def _max_running(api, ids, stop_after=60):
    peak, end = 0, time.time() + stop_after
    while time.time() < end:
        s = ok(api.get("/api/stats"))
        peak = max(peak, s["running"])
        if s["running"] == 0 and s["queued"] == 0:
            break
        time.sleep(0.05)
    return peak


SLOW = {k: [0.15, 0.2] for k in ("after_signup", "after_location", "after_refresh", "after_profile", "before_photo",
                                  "after_photo", "between_swipes", "between_batches", "before_message")}


def test_one_by_one_is_strictly_sequential_and_fifo(app, api, jaumo):
    cid = setup_ready(api, photos=4, max_swipes=2, delays=SLOW)
    ok(api.put("/api/settings", json={"bot": {"parallel_accounts": 1}}))
    ids = launch(api, cid, 4)
    assert _max_running(api, ids) == 1
    runs = wait_runs_done(api, ids)
    assert [r["worker"] for r in runs] == [1, 1, 1, 1]
    starts = [r["started_at"] for r in runs]
    assert starts == sorted(starts)
    for a, b in zip(runs, runs[1:]):
        assert a["finished_at"] <= b["started_at"], "next account only starts after the previous finished"


def test_parallel_workers_and_live_change(app, api, jaumo):
    cid = setup_ready(api, photos=8, max_swipes=3, delays=SLOW)
    ok(api.put("/api/settings", json={"bot": {"parallel_accounts": 3}}))
    ids = launch(api, cid, 8)
    wait_until(lambda: ok(api.get("/api/stats"))["running"] == 3, msg="3 running")
    ok(api.put("/api/settings", json={"bot": {"parallel_accounts": 1}}))
    # sessions already running finish their account; after that only one works at a time
    wait_until(lambda: ok(api.get("/api/stats"))["running"] <= 1, timeout=15, msg="lowering workers applies while running")
    for _ in range(6):
        time.sleep(0.5)
        assert ok(api.get("/api/stats"))["running"] <= 1, "no new parallel starts after lowering workers"
    runs = wait_runs_done(api, ids, timeout=120)
    assert all(r["status"] == "done" for r in runs)
    assert {r["worker"] for r in runs} <= {1, 2, 3}
    s = ok(api.get("/api/accounts/summary"))
    assert set(s["workers"]) >= {r["worker"] for r in runs}


# --- stop -------------------------------------------------------------------------------------

def test_stop_running_and_queued(app, api, jaumo):
    cid = setup_ready(api, photos=4, max_swipes=0, delays={**SLOW, "between_swipes": [1, 1]})
    ok(api.put("/api/settings", json={"bot": {"parallel_accounts": 1}}))
    ids = launch(api, cid, 3)
    wait_until(lambda: ok(api.get(f"/api/runs/{ids[0]}"))["step"] == "swiping", msg="first swiping")
    working = accounts(api, state="working")["items"]
    assert len(working) == 1 and working[0]["working"]
    ok(api.post(f"/api/runs/{ids[2]}/stop"))
    ok(api.post(f"/api/runs/{ids[0]}/stop"))
    r0 = wait_until(lambda: (lambda r: r if r["status"] == "stopped" else None)(ok(api.get(f"/api/runs/{ids[0]}"))), msg="stop")
    assert ok(api.get(f"/api/accounts/{r0['account_id']}"))["status"] == "active"
    wait_until(lambda: ok(api.get(f"/api/runs/{ids[1]}"))["step"] == "swiping", msg="second starts")
    assert ok(api.post("/api/runs/stop-all"))["stopped"] >= 1
    runs = wait_runs_done(api, ids)
    assert [r["status"] for r in runs] == ["stopped", "stopped", "stopped"]
    assert runs[2]["reason"] == "stopped before start" and runs[2]["account_id"] is None
    assert api.delete(f"/api/runs/{ids[0]}").status_code == 200
    assert api.get(f"/api/runs/{ids[0]}").status_code == 404


# --- proxies ----------------------------------------------------------------------------------

def test_shared_proxy_carries_all_jaumo_traffic(app, api, jaumo):
    px = FakeProxy("shared-1")
    try:
        cid = setup_ready(api, photos=2, max_swipes=2, require_proxy=True)
        ok(api.post("/api/proxies/bulk", json={"text": px.line, "shared": True, "label": "test"}))
        proxy = ok(api.get("/api/proxies"))[0]
        test = ok(api.post(f"/api/proxies/{proxy['id']}/test"))
        assert test["ok"] and test["ip"] == "203.0.113.7"
        runs = wait_runs_done(api, launch(api, cid, 2))
        assert all(r["status"] == "done" and r["proxy_id"] == proxy["id"] for r in runs)
        reqs = [r for r in jaumo.state()["requests"] if r["path"].startswith("/v2/")]
        assert reqs and all(r["via_proxy"] == "shared-1" for r in reqs), "every Jaumo call must go through the proxy"
        assert px.auth_failures == 0
        acc = accounts(api)["items"]
        assert all(a["proxy_id"] == proxy["id"] for a in acc)
        assert ok(api.get("/api/proxies"))[0]["use_count"] == 2
    finally:
        px.close()


def test_dedicated_proxy_one_account_at_a_time(app, api, jaumo):
    px = FakeProxy("dedicated-1")
    try:
        cid = setup_ready(api, photos=2, max_swipes=3, require_proxy=True, delays=SLOW)
        ok(api.put("/api/settings", json={"bot": {"parallel_accounts": 2}}))
        ok(api.post("/api/proxies/bulk", json={"text": px.line, "shared": False}))
        ids = launch(api, cid, 2)
        # both workers start together; whichever does not get the proxy waits for it
        def waiter():
            steps = [ok(api.get(f"/api/runs/{i}"))["step"] for i in ids]
            return ids[steps.index("waiting_proxy")] if "waiting_proxy" in steps else None
        waited = wait_until(waiter, msg="one session waits for the dedicated proxy")
        runs = {r["id"]: r for r in wait_runs_done(api, ids)}
        assert all(r["status"] == "done" for r in runs.values())
        holder = next(i for i in ids if i != waited)
        assert runs[holder]["finished_at"] <= runs[waited]["finished_at"], "the waiting session works after the holder"
    finally:
        px.close()


def test_require_proxy_without_proxy_fails_cleanly(app, api, jaumo):
    cid = setup_ready(api, photos=2, require_proxy=True)
    run = wait_runs_done(api, launch(api, cid, 1))[0]
    assert run["status"] == "failed" and "no enabled proxies" in run["reason"]
    assert jaumo.state()["requests"] == [], "nothing may be sent to Jaumo without the required proxy"
    assert sum(p["status"] == "available" for p in ok(api.get("/api/photos"))) == 2


def test_proxy_test_reports_failure(app, api, jaumo):
    ok(api.post("/api/proxies", json={"line": "127.0.0.1:9:u:p"}))
    res = ok(api.post("/api/proxies/test-all"))
    assert res == {"tested": 1, "ok": 0}
    p = ok(api.get("/api/proxies"))[0]
    assert p["last_test_ok"] is False and p["last_test_error"]


# --- signup values: panel -> API -> bot -> Jaumo -------------------------------------------

@pytest.mark.parametrize("rel,dating", [("FLIRT", "FLIRT"), ("FRIENDSHIP", "FLIRT")])
def test_relationship_values_from_panel_reach_jaumo(app, api, jaumo, rel, dating):
    cid = setup_ready(api, photos=2, max_swipes=1)
    conf = ok(api.get("/api/configs"))[0]
    assert conf["settings"]["relationship_search"] == "FLIRT" == conf["settings"]["dating_relationship_search"], "default FLIRT"
    ok(api.put(f"/api/configs/{cid}", json={"name": conf["name"], "apk_profile_id": conf["apk_profile_id"],
                                            "settings": {**conf["settings"], "relationship_search": rel, "dating_relationship_search": dating}}))
    for bad in ("DATING", "flirt", "UNSET", ""):
        r = api.put(f"/api/configs/{cid}", json={"name": conf["name"], "apk_profile_id": conf["apk_profile_id"],
                                                 "settings": {**conf["settings"], "relationship_search": bad}})
        assert r.status_code == 422, bad
    run = wait_runs_done(api, launch(api, cid, 1))[0]
    assert run["status"] == "done"
    f = jaumo.state()["registrations"][0]["form"]
    assert (f["relationship_search"], f["dating_relationship_search"]) == (rel, dating)
    assert "signup_photo_urls" not in conf["settings"] and f["photo_url"].endswith("0339ee18d142fbf39e.jpg")
    a = ok(api.get(f"/api/accounts/{run['account_id']}"))
    assert (a["relationship_search"], a["dating_relationship_search"]) == (rel, dating)
    meta = ok(api.get("/api/meta"))
    assert meta["relationship_values"] == ["FLIRT", "FRIENDSHIP"]
    assert meta["signup_defaults"]["data"]["relationship_search"]["items"][1]["value"] == "FRIENDSHIP"


# --- bot log in the server output (Coolify runtime log) -------------------------------------

def test_bot_log_lines_go_to_server_output(app, api, jaumo):
    cid = setup_ready(api, photos=2, max_swipes=3)
    run = wait_runs_done(api, launch(api, cid, 1, ["Lotte"]))[0]
    acc = ok(api.get(f"/api/accounts/{run['account_id']}"))
    time.sleep(0.3)
    out = app.log.read_text(encoding="utf-8", errors="replace")
    label = f"[session {run['id']} · Worker-01 · Lotte]"
    assert f"{label} INFO    [SIGNUP] OK" in out
    assert f"{label} RESULT  done: max swipes reached (3)" in out
    assert "[PHOTO UPLOAD] Body" not in out and "Headers:" not in out, "debug/HTTP bodies stay out of the runtime log"
    full = ok(api.get(f"/api/accounts/{acc['id']}"))
    assert "acc-" not in "".join(l for l in out.splitlines() if l.startswith("[session")), "no tokens in the runtime log"
    assert full["id"]


# --- start check (Neuer Account dialog) -------------------------------------------------------

def test_start_check_lists_every_reason_and_matches_launch(app, api):
    conf = ok(api.get("/api/configs"))[0]
    ok(api.put(f"/api/configs/{conf['id']}", json={"name": conf["name"], "apk_profile_id": None,
                                                    "settings": {**conf["settings"], "require_proxy": True}}))
    res = ok(api.post("/api/runs/check", json={"config_id": conf["id"], "count": 1}))
    assert not res["ok"]
    assert {p["code"]: p["page"] for p in res["problems"]} == {"apk": "configs", "photos": "photos", "proxy": "proxies"}
    assert api.post("/api/runs", json={"config_id": conf["id"], "count": 1}).status_code == 422, "check and launch agree"
    assert ok(api.get("/api/runs"))["total"] == 0, "the check starts nothing"

    cid = setup_ready(api, photos=2)
    res = ok(api.post("/api/runs/check", json={"config_id": cid, "count": 1}))
    assert res == {"ok": True, "problems": []}
    res = ok(api.post("/api/runs/check", json={"config_id": cid, "count": 3}))
    assert [p["code"] for p in res["problems"]] == ["photos"] and "only 2 of 3" in res["problems"][0]["message"]
    assert api.post("/api/runs/check", json={"config_id": 999, "count": 1}).status_code == 404
