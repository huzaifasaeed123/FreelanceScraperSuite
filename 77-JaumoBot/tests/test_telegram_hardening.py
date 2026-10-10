"""Telegram hardening against the fake Telethon client: a dropped connection (status, reconnect loop with backoff, runs that
pause and resume, auto-resume), revoked and banned sessions (idle and during a run), PeerFlood, unused media cleanup,
abandoned logins, a clean shutdown in the middle of a run and an engine that survives broken events and failing checks.
The fake's control.json (tests/fake_telegram.py) drops connections and revokes sessions while the server runs."""

import json
import sqlite3
import threading
import time

import pytest
from websockets.sync.client import connect

from conftest import jpeg_bytes, ok, wait_until
from test_telegram_accounts import ENV, PHONE, accounts, link
from test_telegram_chats import Scenario, chats, db, dlg, link_synced, wait_sync
from test_telegram_runs import (T, chat_ids, chat_row, control, make_workflow, outbox, run, run_chats, start, text_step,
                                upload, wait_sent, wait_status)

LOST = "Connection to Telegram lost"
ENDED = "Telegram ended this session, log in again"
FAST = {"TELEGRAM_WATCH_INTERVAL": "0.2", "TELEGRAM_RECONNECT_BASE": "0.3", "TELEGRAM_RETRY_WAIT": "0.3"}


@pytest.fixture
def scn(tmp_path):
    return Scenario(tmp_path / "fake_tg")


@pytest.fixture
def hard(make_app, scn):
    """build(**env) -> (app, api, account): a server with the fast watchdog timings and one linked account with chats 1001..1003."""
    scn.dialogs([dlg(i) for i in range(1, 4)])

    def build(**extra):
        app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir), **{**FAST, **extra})
        api = app.client()
        return app, api, link_synced(api)
    return build


def ctl(scn, **lists):
    """Set the lists of control.json (drop, down, revoke, ban, probe_error, drop_on_send) the fake client reads."""
    path = scn.dir / "control.json"
    state = json.loads(path.read_text()) if path.exists() else {}
    path.write_text(json.dumps({**state, **lists}), encoding="utf-8")


def status_of(api, phone=PHONE):
    return accounts(api)[phone]["status"]


def wait_account(api, status, phone=PHONE, timeout=20):
    return wait_until(lambda: (a := accounts(api)[phone])["status"] == status and a, timeout=timeout,
                      msg=f"account {phone} to be {status}")


def connection_log(scn):
    path = scn.dir / "connections.jsonl"
    return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []


class Events:
    """Collects the module WebSocket events of a running server in the background."""

    def __init__(self, app, api):
        self.seen, self.ready = [], threading.Event()
        cookie = {"Cookie": f"jb_session={api.cookies['jb_session']}"}
        self.thread = threading.Thread(target=self._read, args=(app.url.replace("http", "ws") + "/ws/modules/telegram", cookie),
                                       daemon=True)
        self.thread.start()
        assert self.ready.wait(10)

    def _read(self, url, cookie):
        with connect(url, additional_headers=cookie, open_timeout=10) as c:
            self.ready.set()
            while True:
                try:
                    self.seen.append(json.loads(c.recv(timeout=30)))
                except Exception:  # noqa: BLE001 — the server went away or the test is over
                    return


# --- a dropped connection ------------------------------------------------------------------------------

def test_a_dropped_connection_is_shown_and_retried_with_growing_waits(hard, scn):
    app, api, acc = hard()
    ctl(scn, down=[PHONE])
    lost = wait_account(api, "connecting")
    assert lost["status_msg"] in (LOST, "Could not reach Telegram (network problem)") and lost["has_session"]
    time.sleep(3.0)
    attempts = [c for c in connection_log(scn) if c["event"] == "connect_failed"]
    assert 2 <= len(attempts) <= 5, attempts          # 0.3 s, 0.6 s, 1.2 s ... : a fixed 0.3 s pause would give about ten
    assert status_of(api) == "connecting" and accounts(api)[PHONE]["status_msg"].startswith("Could not reach")
    ctl(scn, down=[])
    back = wait_account(api, "online")
    assert back["status_msg"] == "" and back["auto_connect"]
    wait_sync(api)


def test_a_dropped_connection_is_pushed_to_the_panel_and_the_old_client_is_closed(hard, scn):
    app, api, acc = hard()
    ev = Events(app, api)
    ctl(scn, drop=[PHONE])
    wait_until(lambda: [m for m in ev.seen if m["type"] == "account" and m["status"] == "connecting"], msg="connecting event")
    wait_until(lambda: [m for m in ev.seen if m["type"] == "account" and m["status"] == "online"], msg="online again")
    log = connection_log(scn)
    assert [c["event"] for c in log].count("connect") == 2          # the first client and its replacement
    first = log[0]["client"]
    assert any(c["client"] == first and c["event"] == "disconnect" for c in log)    # the dead one was closed, not abandoned


def test_manually_disconnected_accounts_are_not_reconnected(hard, scn):
    app, api, acc = hard()
    ok(api.post(f"{T}/accounts/{acc['id']}/disconnect"))
    time.sleep(1.0)
    assert status_of(api) == "offline"


def test_a_run_pauses_when_the_connection_drops_and_continues_after_a_manual_resume(hard, scn):
    app, api, acc = hard()
    r = start(api, acc, make_workflow(api, [text_step("a", 3), text_step("b")]), chat_ids(api, acc, 1001, 1002))
    wait_sent(scn, 1)
    ctl(scn, down=[PHONE])
    s = wait_status(api, r["id"], "paused")
    assert s["status_msg"] == LOST and s["errors"] == 0 and 0 < s["seconds_remaining"] <= 3     # the countdown is frozen
    assert chat_row(api, s["chat"]["id"])["chat_status"] == "paused"
    assert control(api, r["id"], "resume", 409)["detail"] == "This account is not online, connect it first"
    ctl(scn, down=[])
    wait_account(api, "online")
    time.sleep(1.0)
    assert run(api, r["id"])["status"] == "paused"          # auto-resume is off by default: the operator decides
    assert run(api, r["id"])["auto_resume"] is False
    control(api, r["id"], "resume")
    final = wait_status(api, r["id"], "done")
    assert (final["success"], final["errors"]) == (2, 0)
    assert [(m["chat_id"], m["content"]) for m in outbox(scn)] == [(1001, "a"), (1001, "b"), (1002, "a"), (1002, "b")]


def test_auto_resume_continues_by_itself_when_the_account_is_back(hard, scn):
    app, api, acc = hard()
    r = start(api, acc, make_workflow(api, [text_step("a", 2), text_step("b")]), chat_ids(api, acc, 1001, 1002), auto_resume=True)
    assert r["auto_resume"] is True
    wait_sent(scn, 1)
    ctl(scn, down=[PHONE])
    wait_status(api, r["id"], "paused")
    ctl(scn, down=[])
    final = wait_status(api, r["id"], "done", timeout=30)
    assert (final["success"], final["errors"]) == (2, 0) and final["status_msg"] == ""
    assert [(m["chat_id"], m["content"]) for m in outbox(scn)] == [(1001, "a"), (1001, "b"), (1002, "a"), (1002, "b")]
    again = control(api, r["id"], "restart")                  # the choice is part of what a restart repeats
    assert again["auto_resume"] is True
    control(api, again["id"], "stop")


def test_auto_resume_never_overrides_a_pause_by_the_operator(hard, scn):
    app, api, acc = hard()
    r = start(api, acc, make_workflow(api, [text_step("a", 3), text_step("b")]), chat_ids(api, acc, 1001), auto_resume=True)
    wait_sent(scn, 1)
    control(api, r["id"], "pause")
    ok(api.post(f"{T}/accounts/{acc['id']}/disconnect"))
    ok(api.post(f"{T}/accounts/{acc['id']}/connect"))
    time.sleep(1.0)
    assert run(api, r["id"])["status"] == "paused" and run(api, r["id"])["status_msg"] == ""
    control(api, r["id"], "stop")


def test_a_connection_lost_while_sending_does_not_fail_the_chat(hard, scn):
    app, api, acc = hard()
    ctl(scn, drop_on_send=[PHONE])
    r = start(api, acc, make_workflow(api, [text_step("a"), text_step("b")]), chat_ids(api, acc, 1001, 1002), auto_resume=True)
    final = wait_status(api, r["id"], "done", timeout=30)
    assert (final["success"], final["errors"]) == (2, 0)
    # the message that was cut off is sent again once the account is back; nothing is lost or doubled
    assert [(m["chat_id"], m["content"]) for m in outbox(scn)] == [(1001, "a"), (1001, "b"), (1002, "a"), (1002, "b")]


def test_an_unreachable_telegram_at_startup_is_retried(hard, scn, make_app):
    app, api, acc = hard()
    app.stop()
    ctl(scn, down=[PHONE])
    app2 = make_app(storage=app.storage, **ENV, FAKE_TG_DIR=str(scn.dir), **FAST)
    api2 = app2.client()
    wait_until(lambda: accounts(api2)[PHONE]["status"] == "connecting" and accounts(api2)[PHONE]["status_msg"].startswith("Could not reach"),
               msg="the startup connect to fail and keep trying")
    ctl(scn, down=[])
    wait_account(api2, "online")


# --- revoked and banned sessions ---------------------------------------------------------------------------

def test_a_session_revoked_while_idle_turns_the_account_into_an_error_and_can_be_logged_in_again(hard, scn):
    app, api, acc = hard(TELEGRAM_AUTH_PROBE="0.3")
    ctl(scn, revoke=[PHONE])
    a = wait_account(api, "error")
    assert not a["has_session"] and "log in again" in a["status_msg"]
    assert db(app, "select session_string from tg_account") == [("",)]            # nothing of the dead login is kept
    assert "fake:" not in api.get(f"{T}/accounts").text
    assert connection_log(scn)[0]["client"] in {c["client"] for c in connection_log(scn) if c["event"] == "disconnect"}
    ctl(scn, revoke=[])
    relinked = link(api)
    assert relinked["id"] == acc["id"] and relinked["status"] == "online"


@pytest.mark.parametrize("auto_resume", [False, True])
def test_a_revoked_session_during_a_run_pauses_it_until_the_account_logs_in_again(hard, scn, auto_resume):
    app, api, acc = hard(TELEGRAM_AUTH_PROBE="0.3")
    r = start(api, acc, make_workflow(api, [text_step("a", 3), text_step("b")]), chat_ids(api, acc, 1001), auto_resume=auto_resume)
    wait_sent(scn, 1)
    ctl(scn, revoke=[PHONE])
    wait_account(api, "error")
    s = wait_status(api, r["id"], "paused")
    assert s["status_msg"] == ENDED and s["errors"] == 0
    assert control(api, r["id"], "resume", 409)["detail"] == "This account is not online, connect it first"
    ctl(scn, revoke=[])
    link(api)
    if not auto_resume:
        time.sleep(0.8)
        assert run(api, r["id"])["status"] == "paused"
        control(api, r["id"], "resume")
    final = wait_status(api, r["id"], "done", timeout=30)
    assert (final["success"], final["errors"]) == (1, 0)
    assert [m["content"] for m in outbox(scn)] == ["a", "b"]


def test_a_banned_account_found_by_a_send_pauses_the_run_instead_of_failing_every_chat(hard, scn):
    app, api, acc = hard()           # the periodic check is far away: the failing send is what finds out
    r = start(api, acc, make_workflow(api, [text_step("a", 1), text_step("b")]), chat_ids(api, acc, 1001, 1002, 1003))
    wait_sent(scn, 1)
    ctl(scn, ban=[PHONE])
    s = wait_status(api, r["id"], "paused")
    assert s["status_msg"] == "This Telegram account was banned" and s["errors"] == 0 and s["processed"] == 0
    a = wait_account(api, "error")
    assert a["status_msg"] == "This Telegram account was banned" and not a["has_session"]
    assert [c["status"] for c in run_chats(api, r["id"])] == ["running", "pending", "pending"]
    control(api, r["id"], "stop")


# --- FloodWait / PeerFlood ----------------------------------------------------------------------------------

def test_peer_flood_is_counted_on_the_run_and_published(hard, scn):
    app, api, acc = hard()
    ev = Events(app, api)
    (scn.dir / "send_errors.json").write_text(json.dumps({"1002": {"error": "PeerFloodError"}}))
    r = start(api, acc, make_workflow(api, [text_step("a")]), chat_ids(api, acc, 1001, 1002, 1003))
    final = wait_status(api, r["id"], "done")
    assert (final["success"], final["errors"], final["peer_floods"]) == (2, 1, 1)
    assert run_chats(api, r["id"])[1]["error_reason"].endswith("(PeerFlood)")
    flood = wait_until(lambda: [m for m in ev.seen if m["type"] == "flood" and m.get("kind") == "peer"], msg="the PeerFlood event")
    assert flood == [{"type": "flood", "kind": "peer", "run_id": r["id"], "account_id": acc["id"]}]
    assert ok(api.get(f"{T}/stats"))["last_run"]["peer_floods"] == 1


# --- housekeeping -----------------------------------------------------------------------------------------------

def test_unused_media_is_listed_and_cleaned_but_files_in_use_and_fresh_uploads_stay(hard, scn):
    app, api, acc = hard()
    used = upload(api, "u.jpg", jpeg_bytes(1, (40, 40)))
    spare1, spare2 = upload(api, "s1.jpg", jpeg_bytes(2, (40, 40))), upload(api, "s2.png", jpeg_bytes(3, (40, 40), "PNG"))
    make_workflow(api, [{"type": "image", "file": used, "pause_after": 0}])
    fresh = ok(api.get(f"{T}/media/unused"))
    assert fresh == {"items": [], "bytes": 0}                 # uploaded a moment ago: the editor may still be about to save it
    listing = ok(api.get(f"{T}/media/unused", params={"min_age_minutes": 0}))
    assert sorted(i["name"] for i in listing["items"]) == sorted([spare1, spare2])
    assert listing["bytes"] == sum(i["size"] for i in listing["items"]) > 0
    assert ok(api.post(f"{T}/media/cleanup", json={"min_age_minutes": 60})) == {"deleted": 0, "bytes": 0}
    done = ok(api.post(f"{T}/media/cleanup", json={"min_age_minutes": 0}))
    assert done == {"deleted": 2, "bytes": listing["bytes"]}
    assert sorted(m["name"] for m in ok(api.get(f"{T}/media"))) == [used]
    assert ok(api.post(f"{T}/media/cleanup", json={"min_age_minutes": 0})) == {"deleted": 0, "bytes": 0}
    assert api.post(f"{T}/media/cleanup", json={"min_age_minutes": -1}).status_code == 422
    assert api.get(f"{T}/media/unused", params={"min_age_minutes": "x"}).status_code == 422


def test_a_file_of_an_unfinished_run_is_not_cleaned_up(hard, scn):
    app, api, acc = hard()
    img = upload(api, "u.jpg", jpeg_bytes(1, (40, 40)))
    wf = make_workflow(api, [{"type": "image", "file": img, "pause_after": 5}, text_step("x")])
    r = start(api, acc, wf, chat_ids(api, acc, 1001))
    wait_sent(scn, 1)
    ok(api.put(f"{T}/workflows/{wf['id']}", json={"name": "Flow", "steps": [text_step("other")]}))    # the file left the workflow
    assert ok(api.get(f"{T}/media/unused", params={"min_age_minutes": 0}))["items"] == []     # ... but the run still sends it
    control(api, r["id"], "stop")
    assert [i["name"] for i in ok(api.get(f"{T}/media/unused", params={"min_age_minutes": 0}))["items"]] == [img]


def test_media_cleanup_routes_need_a_login(hard, scn):
    app, api, acc = hard()
    import httpx
    anon = httpx.Client(base_url=app.url)
    assert anon.get(f"{T}/media/unused").status_code in (401, 403)
    assert anon.post(f"{T}/media/cleanup", json={"min_age_minutes": 0}).status_code in (401, 403)


def test_logins_nobody_finished_are_removed_at_startup_but_real_accounts_stay(hard, scn, make_app):
    app, api, acc = hard()
    with sqlite3.connect(app.storage / "db.sqlite") as c:
        for phone, status, session in (("+4915100000071", "offline", ""), ("+4915100000072", "error", ""),
                                       ("+4915100000073", "offline", "fake:+4915100000073")):
            c.execute("insert into tg_account (label, phone, api_id, api_hash, session_string, status, status_msg, auto_connect,"
                      " tg_username, created_at) values ('', ?, 1, 'x', ?, ?, '', 0, '', '2026-01-01 00:00:00')", (phone, session, status))
    app.stop()
    api2 = make_app(storage=app.storage, **ENV, FAKE_TG_DIR=str(scn.dir), **FAST).client()
    assert set(accounts(api2)) == {PHONE, "+4915100000072", "+4915100000073"}      # only the half-made login is gone


def test_an_abandoned_login_is_closed_and_its_row_removed_while_the_server_runs(hard, scn):
    app, api, acc = hard(TELEGRAM_LOGIN_WINDOW="1")
    started = ok(api.post(f"{T}/accounts/start", json={"phone": "+4915100000005"}))
    assert accounts(api)["+4915100000005"]["login_pending"]
    wait_until(lambda: "+4915100000005" not in accounts(api), timeout=15, msg="the abandoned login to be swept")
    assert api.post(f"{T}/accounts/{started['id']}/code", json={"code": "12345"}).status_code == 404
    log = connection_log(scn)
    pending_client = [c["client"] for c in log if c["event"] == "connect"][-1]       # the login's connection, opened last
    assert any(c["client"] == pending_client and c["event"] == "disconnect" for c in log)
    assert PHONE in accounts(api) and accounts(api)[PHONE]["status"] == "online"


# --- shutdown and robustness ---------------------------------------------------------------------------------------

def test_stopping_the_server_during_a_run_leaves_no_task_or_connection_behind(hard, scn, make_app):
    app, api, acc = hard(PYTHONWARNINGS="default::ResourceWarning")
    ok(api.post(f"{T}/accounts/start", json={"phone": "+4915100000005"}))          # a login waiting for its code: one more open client
    r = start(api, acc, make_workflow(api, [text_step("a", 30), text_step("b")]), chat_ids(api, acc, 1001, 1002))
    wait_sent(scn, 1)
    ctl(scn, down=[PHONE])                                                          # ... and a reconnect loop in progress
    wait_account(api, "connecting")
    app.stop_gracefully()
    log = app.log.read_text(errors="replace")
    assert "Application shutdown complete" in log
    for noise in ("Task was destroyed", "never awaited", "ResourceWarning", "nclosed", "Traceback", "Task exception"):
        assert noise not in log, noise
    conns = connection_log(scn)
    opened = {c["client"] for c in conns if c["event"] == "connect"}
    assert len(opened) == 2 and opened == {c["client"] for c in conns if c["event"] == "disconnect"}   # every connection was closed
    ctl(scn, down=[])
    api2 = make_app(storage=app.storage, **ENV, FAKE_TG_DIR=str(scn.dir), **FAST).client()
    s = run(api2, r["id"])
    assert s["status"] == "paused" and s["step"] == {"index": 0, "type": "text"}       # it kept its place
    wait_account(api2, "online")
    control(api2, r["id"], "stop")


def test_a_broken_incoming_event_is_logged_and_the_next_one_still_arrives(hard, scn):
    app, api, acc = hard()
    scn.incoming(id=2001, access_hash=1, first_name="Broken", text="x", sender_error=True)
    scn.incoming(id=2002, access_hash=2, first_name="Good", text="hello")
    wait_until(lambda: any(c["telegram_id"] == "2002" for c in chats(api)["items"]), msg="the good message")
    assert not any(c["telegram_id"] == "2001" for c in chats(api)["items"])
    assert status_of(api) == "online"


def test_a_failing_session_check_is_logged_and_the_watch_goes_on(hard, scn):
    app, api, acc = hard(TELEGRAM_AUTH_PROBE="0.3")
    ctl(scn, probe_error=[PHONE])
    time.sleep(1.2)                                        # several checks fail
    assert status_of(api) == "online"
    ctl(scn, probe_error=[], revoke=[PHONE])
    wait_account(api, "error")                              # the watch is still alive and finds the revoked session
