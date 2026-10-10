"""Telegram run engine against the fake Telethon client: message order and types, pauses (timing taken from the
fake's outbox timestamps), pause / resume / stop, restart recovery, errors, retry, FloodWait, an account that goes
offline, one run per account, parallel accounts and the /runs routes (tests/fake_telegram.py documents the seam)."""

import json
import threading
import time
from datetime import datetime

import httpx
import pytest
from websockets.sync.client import connect

from conftest import jpeg_bytes, ok, wait_until
from test_telegram_accounts import ENV, PHONE, accounts
from test_telegram_chats import Scenario, chats, db, dlg, link_synced, wait_sync
from test_telegram_workflows import ogg_opus

T = "/api/telegram"
PHONE_B = "+4915100000003"
RETRY_WAIT = 0.3
TOL = 0.45      # seconds of slack on timing assertions (a loaded Windows machine is slow to wake up)


@pytest.fixture
def scn(tmp_path):
    return Scenario(tmp_path / "fake_tg")


@pytest.fixture
def rig(make_app, scn):
    scn.dialogs([dlg(i) for i in range(1, 6)])      # chats 1001..1005, access_hash 5001..5005
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir), TELEGRAM_RETRY_WAIT=str(RETRY_WAIT))
    return app, app.client(), scn


# --- helpers ---------------------------------------------------------------------------------------

def outbox(scn, account=None):
    path = scn.dir / "outbox.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
    for r in rows:
        r["t"] = datetime.fromisoformat(r["ts"]).timestamp()
    return [r for r in rows if account is None or r["account"] == account]


def wait_sent(scn, n, timeout=20):
    wait_until(lambda: len(outbox(scn)) >= n, timeout=timeout, msg=f"{n} messages sent")


def text_step(text, pause=0):
    return {"type": "text", "content": text, "pause_after": pause}


def make_workflow(api, steps, name="Flow"):
    return ok(api.post(f"{T}/workflows", json={"name": name, "steps": steps}))


def upload(api, name, data):
    return ok(api.post(f"{T}/media", files=[("files", (name, data))]))["saved"][0]["name"]


def chat_ids(api, account, *telegram_ids):
    """Database ids of the chats with these Telegram ids, in the order given."""
    by_tid = {c["telegram_id"]: c["id"] for c in chats(api, account_id=account["id"])["items"]}
    return [by_tid[str(t)] for t in telegram_ids]


def start(api, account, workflow, ids, expect=200, **kw):
    r = api.post(f"{T}/runs", json={"account_id": account["id"], "workflow_id": workflow["id"], "chat_ids": ids, **kw})
    return ok(r, expect)


def run(api, run_id):
    return ok(api.get(f"{T}/runs/{run_id}"))


def run_chats(api, run_id, **params):
    return ok(api.get(f"{T}/runs/{run_id}/chats", params=params))["items"]


def wait_status(api, run_id, *statuses, timeout=30):
    return wait_until(lambda: (r := run(api, run_id))["status"] in statuses and r, timeout=timeout,
                      msg=f"run {run_id} to be {statuses}")


def chat_row(api, chat_id):
    return ok(api.get(f"{T}/chats/{chat_id}"))


def control(api, run_id, action, expect=200):
    return ok(api.post(f"{T}/runs/{run_id}/{action}"), expect)


@pytest.fixture
def linked(rig):
    app, api, scn = rig
    acc = link_synced(api)
    return app, api, scn, acc


# --- order, types, pauses, bookkeeping ----------------------------------------------------------------

def test_messages_go_out_chat_by_chat_in_order_with_the_right_pauses(linked):
    app, api, scn, acc = linked
    voice, image = upload(api, "v.ogg", ogg_opus(2)), upload(api, "p.jpg", jpeg_bytes(1, (60, 40)))
    wf = make_workflow(api, [{"type": "voice", "file": voice, "pause_after": 1}, text_step("Hallo", 1),
                             {"type": "image", "file": image, "pause_after": 0},
                             {"type": "voice", "file": voice, "pause_after": 0}])
    ids = chat_ids(api, acc, 1002, 1001)       # deliberately not the sync order
    r = start(api, acc, wf, ids)
    assert r["status"] == "running" and r["total"] == 2 and r["workflow_name"] == "Flow"
    final = wait_status(api, r["id"], "done")
    assert (final["processed"], final["success"], final["errors"], final["percent"]) == (2, 2, 0, 100)

    sent = outbox(scn)
    assert [(m["chat_id"], m["type"]) for m in sent] == [(1002, t) for t in ("voice", "text", "image", "voice")] + \
                                                         [(1001, t) for t in ("voice", "text", "image", "voice")]
    assert sent[1]["content"] == "Hallo" and sent[2]["file"].endswith(image) and sent[0]["file"].endswith(voice)
    # a voice memo says how long it is (real Telethon would send 0:00 without hachoir); other types carry no duration
    assert sent[0]["duration"] == 2 and sent[3]["duration"] == 2 and "duration" not in sent[2]
    first = sent[:4]
    for (a, b), wanted in zip(zip(first, first[1:]), (1, 1, 0)):    # the gap after each step is that step's pause
        assert wanted - 0.1 <= b["t"] - a["t"] <= wanted + TOL, (a, b)
    assert sent[4]["t"] - sent[3]["t"] < TOL      # the last step has no pause: the next chat starts right away

    for tid, ahash in ((1002, "5002"), (1001, "5001")):    # sent to the stored (id, access_hash), not an entity lookup
        assert {(m["peer"], str(m["access_hash"])) for m in sent if m["chat_id"] == tid} == {("InputPeerUser", ahash)}
    assert db(app, "select access_hash from tg_chat where telegram_id='1002'") == [("5002",)]

    for cid in ids:
        c = chat_row(api, cid)
        assert (c["chat_status"], c["messages_sent"], c["error_reason"]) == ("done", 4, "") and c["last_processed_at"]
    rows = run_chats(api, r["id"])
    assert [(x["chat_id"], x["status"], x["steps_done"]) for x in rows] == [(ids[0], "done", 4), (ids[1], "done", 4)]
    assert all(x["processed_at"] and x["started_at"] for x in rows)
    assert final["finished_at"] and final["chat"] is None and final["step"] is None


def test_live_state_shows_chat_step_next_step_and_countdown(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("one", 4), text_step("two", 0)])
    ids = chat_ids(api, acc, 1001, 1002)
    r = start(api, acc, wf, ids)
    wait_sent(scn, 1)
    s = wait_until(lambda: (x := run(api, r["id"]))["wait_kind"] == "pause" and x, msg="the pause to begin")
    assert s["status"] == "running" and s["chat"] == {"id": ids[0], "name": "User1", "username": "user1"}
    assert s["step"] == {"index": 0, "type": "text"} and s["next_step_type"] == "text"
    assert 2.5 < s["seconds_remaining"] <= 4 and s["next_action_at"]
    assert (s["processed"], s["total"], s["percent"]) == (0, 2, 0)
    assert chat_row(api, ids[0])["chat_status"] == "in_progress" and chat_row(api, ids[1])["chat_status"] == "pending"
    control(api, r["id"], "stop")


def test_workflow_edits_after_the_start_do_not_change_a_running_run(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("original", 2), text_step("second", 0)])
    r = start(api, acc, wf, chat_ids(api, acc, 1001))
    wait_sent(scn, 1)
    ok(api.put(f"{T}/workflows/{wf['id']}", json={"name": "Flow", "steps": [text_step("changed")]}))
    wait_status(api, r["id"], "done")
    assert [m["content"] for m in outbox(scn)] == ["original", "second"]


# --- pause, resume, stop ----------------------------------------------------------------------------------

def test_pause_freezes_the_countdown_and_resume_continues_with_the_rest(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("one", 3), text_step("two", 0)])
    ids = chat_ids(api, acc, 1001)
    r = start(api, acc, wf, ids)
    wait_sent(scn, 1)
    time.sleep(1.0)
    paused = control(api, r["id"], "pause")
    assert paused["status"] == "paused" and paused["next_action_at"] is None
    assert 1.2 <= paused["seconds_remaining"] <= 2.3
    assert chat_row(api, ids[0])["chat_status"] == "paused"
    time.sleep(3.2)      # longer than the whole pause: nothing may be sent and the countdown must not move
    assert len(outbox(scn)) == 1
    still = run(api, r["id"])
    assert still["status"] == "paused" and abs(still["seconds_remaining"] - paused["seconds_remaining"]) < 0.2

    resumed_at = time.time()
    back = control(api, r["id"], "resume")
    assert back["status"] == "running" and back["step"] == {"index": 0, "type": "text"}
    assert chat_row(api, ids[0])["chat_status"] == "in_progress"
    wait_status(api, r["id"], "done")
    second = outbox(scn)[1]
    waited = second["t"] - resumed_at
    assert abs(waited - paused["seconds_remaining"]) < TOL, waited        # the remaining time, not the full 3 s
    assert [m["content"] for m in outbox(scn)] == ["one", "two"]          # same chat, next step: nothing repeated


def test_pause_between_chats_resumes_at_the_next_chat(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("hi", 2)])
    r = start(api, acc, wf, chat_ids(api, acc, 1001, 1002))
    wait_sent(scn, 1)
    control(api, r["id"], "pause")
    s = run(api, r["id"])
    assert s["processed"] == 1 and s["chat"]["name"] == "User1"       # chat 1 is finished, chat 2 not begun
    time.sleep(2.5)
    assert len(outbox(scn)) == 1
    control(api, r["id"], "resume")
    wait_status(api, r["id"], "done")
    assert [m["chat_id"] for m in outbox(scn)] == [1001, 1002]


def test_transitions_that_do_not_fit_the_state_are_refused_with_409(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("hi", 5)])
    r = start(api, acc, wf, chat_ids(api, acc, 1001, 1002))
    wait_sent(scn, 1)
    control(api, r["id"], "pause")
    assert control(api, r["id"], "pause", 409)["detail"] == "The run cannot be paused, it is paused"
    control(api, r["id"], "stop")
    for action in ("pause", "resume", "stop"):
        assert control(api, r["id"], action, 409)["detail"].endswith("it is stopped")
    assert control(api, 9999, "pause", 404)["detail"] == "Run not found"
    running = start(api, acc, make_workflow(api, [text_step("x", 3)], "Other"), chat_ids(api, acc, 1003, 1004))
    assert control(api, running["id"], "resume", 409)["detail"].endswith("it is running")
    assert control(api, running["id"], "restart", 409)["detail"] == "The run is still active, stop it first"
    control(api, running["id"], "stop")


def test_stop_skips_the_chats_not_reached(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("a", 1), text_step("b", 1)])
    ids = chat_ids(api, acc, 1001, 1002, 1003)
    r = start(api, acc, wf, ids)
    wait_sent(scn, 3)         # chat 1 done, chat 2 has sent "a"
    stopped = control(api, r["id"], "stop")
    assert stopped["status"] == "stopped" and stopped["finished_at"] and stopped["seconds_remaining"] is None
    assert (stopped["processed"], stopped["success"], stopped["skipped"]) == (1, 1, 2)
    rows = run_chats(api, r["id"])
    assert [(x["status"], x["steps_done"]) for x in rows] == [("done", 2), ("skipped", 1), ("skipped", 0)]
    assert [chat_row(api, i)["chat_status"] for i in ids] == ["done", "paused", "pending"]    # half-done chat is marked
    time.sleep(1.6)
    assert len(outbox(scn)) == 3                    # nothing is sent after Stop
    other = start(api, acc, wf, ids[:1])            # the account is free again
    control(api, other["id"], "stop")


def test_stop_a_paused_run(linked):
    app, api, scn, acc = linked
    r = start(api, acc, make_workflow(api, [text_step("a", 5)]), chat_ids(api, acc, 1001, 1002))
    wait_sent(scn, 1)
    control(api, r["id"], "pause")
    assert control(api, r["id"], "stop")["status"] == "stopped"
    assert run_chats(api, r["id"])[1]["status"] == "skipped"


# --- restart recovery --------------------------------------------------------------------------------------

def test_run_left_running_by_a_restart_is_paused_with_its_place_and_resumes(linked, make_app):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("a", 1), text_step("b", 4), text_step("c", 0)])
    ids = chat_ids(api, acc, 1001, 1002)
    r = start(api, acc, wf, ids)
    wait_sent(scn, 2)       # "b" is out, its 4 s pause is running
    app.stop(kill=True)
    app2 = make_app(storage=app.storage, **ENV, FAKE_TG_DIR=str(scn.dir), TELEGRAM_RETRY_WAIT=str(RETRY_WAIT))
    api2 = app2.client()
    s = run(api2, r["id"])
    assert s["status"] == "paused" and s["status_msg"] == "Server restarted"
    assert s["chat"]["name"] == "User1" and s["step"] == {"index": 1, "type": "text"} and s["wait_kind"] == "pause"
    assert chat_row(api2, ids[0])["chat_status"] == "paused"
    wait_until(lambda: accounts(api2)[PHONE]["status"] == "online", msg="the account to reconnect")
    sent_before = len(outbox(scn))
    time.sleep(1.2)
    assert len(outbox(scn)) == sent_before                       # a restored run waits for the operator
    assert control(api2, r["id"], "resume")["status"] == "running"
    wait_status(api2, r["id"], "done")
    # every step of both chats went out exactly once and in order
    assert [(m["chat_id"], m["content"]) for m in outbox(scn)] == [(1001, "a"), (1001, "b"), (1001, "c"),
                                                                   (1002, "a"), (1002, "b"), (1002, "c")]


def test_resume_after_a_restart_keeps_the_remaining_pause(linked, make_app):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("a", 8), text_step("b", 0)])
    r = start(api, acc, wf, chat_ids(api, acc, 1001))
    wait_sent(scn, 1)
    time.sleep(1.0)
    paused = control(api, r["id"], "pause")
    app.stop(kill=True)
    app2 = make_app(storage=app.storage, **ENV, FAKE_TG_DIR=str(scn.dir), TELEGRAM_RETRY_WAIT=str(RETRY_WAIT))
    api2 = app2.client()
    time.sleep(2.0)      # downtime does not eat into a pause that was frozen before the restart
    s = run(api2, r["id"])
    assert s["status"] == "paused" and abs(s["seconds_remaining"] - paused["seconds_remaining"]) < 0.1
    wait_until(lambda: accounts(api2)[PHONE]["status"] == "online", msg="the account to reconnect")
    at = time.time()
    control(api2, r["id"], "resume")
    wait_status(api2, r["id"], "done")
    assert abs((outbox(scn)[1]["t"] - at) - paused["seconds_remaining"]) < TOL + 0.3
    assert [m["content"] for m in outbox(scn)] == ["a", "b"]


def test_a_restored_run_cannot_resume_while_its_account_is_offline_and_can_be_stopped(linked, make_app):
    app, api, scn, acc = linked
    r = start(api, acc, make_workflow(api, [text_step("a", 30)]), chat_ids(api, acc, 1001, 1002))
    wait_sent(scn, 1)
    ok(api.post(f"{T}/accounts/{acc['id']}/disconnect"))      # auto_connect is off: stays offline after the restart
    app.stop(kill=True)
    api2 = make_app(storage=app.storage, **ENV, FAKE_TG_DIR=str(scn.dir)).client()
    assert run(api2, r["id"])["status"] == "paused"
    assert control(api2, r["id"], "resume", 409)["detail"] == "This account is not online, connect it first"
    stopped = control(api2, r["id"], "stop")
    assert stopped["status"] == "stopped" and [x["status"] for x in run_chats(api2, r["id"])] == ["done", "skipped"]


# --- errors ---------------------------------------------------------------------------------------------------

def script_errors(scn, **per_chat):
    (scn.dir / "send_errors.json").write_text(json.dumps({k.removeprefix("c"): v for k, v in per_chat.items()}))


def test_an_error_in_one_chat_does_not_stop_the_run(linked):
    app, api, scn, acc = linked
    script_errors(scn, c1002={"error": "UserPrivacyRestrictedError"})
    wf = make_workflow(api, [text_step("a"), text_step("b")])
    ids = chat_ids(api, acc, 1001, 1002, 1003)
    r = start(api, acc, wf, ids)
    final = wait_status(api, r["id"], "done")
    assert (final["processed"], final["success"], final["errors"], final["percent"]) == (3, 2, 1, 100)
    assert [(m["chat_id"], m["content"]) for m in outbox(scn)] == [(1001, "a"), (1001, "b"), (1003, "a"), (1003, "b")]
    rows = run_chats(api, r["id"])
    assert [x["status"] for x in rows] == ["done", "error", "done"]
    assert rows[1]["error_reason"] == "The user's privacy settings do not allow this message" and rows[1]["steps_done"] == 0
    bad = chat_row(api, ids[1])
    assert (bad["chat_status"], bad["messages_sent"], bad["error_reason"]) == ("error", 0, rows[1]["error_reason"])
    assert bad["last_processed_at"]
    ok_chat = chat_row(api, ids[2])
    assert ok_chat["chat_status"] == "done" and ok_chat["error_reason"] == ""


def test_telegram_errors_become_readable_reasons(linked):
    app, api, scn, acc = linked
    script_errors(scn, c1001={"error": "PeerFloodError"}, c1002={"error": "InputUserDeactivatedError"},
                  c1003={"error": "UserIsBlockedError"}, c1004={"error": "PeerIdInvalidError"},
                  c1005={"error": "ConnectionError"})
    r = start(api, acc, make_workflow(api, [text_step("a")]), chat_ids(api, acc, 1001, 1002, 1003, 1004, 1005))
    wait_status(api, r["id"], "done")
    assert [x["error_reason"] for x in run_chats(api, r["id"])] == [
        "Telegram limited this account for writing to new people (PeerFlood)", "The user's account was deleted",
        "The user has blocked this account", "Invalid recipient (the chat could not be found)",
        "Could not reach Telegram (network problem)"]


def test_unknown_errors_name_their_type_and_keep_what_was_sent_before(linked):
    app, api, scn, acc = linked
    script_errors(scn, c1001={"error": "ChatAdminRequiredError", "after": 1})      # the second message fails
    ids = chat_ids(api, acc, 1001)
    r = start(api, acc, make_workflow(api, [text_step("a"), text_step("b")]), ids)
    wait_status(api, r["id"], "done")
    row = run_chats(api, r["id"])[0]
    assert (row["status"], row["steps_done"]) == ("error", 1)
    assert row["error_reason"] == "Telegram error: ChatAdminRequiredError"
    assert chat_row(api, ids[0])["messages_sent"] == 1 and chat_row(api, ids[0])["chat_status"] == "error"


def test_a_chat_without_an_access_hash_fails_with_a_clear_reason(rig):
    app, api, scn = rig
    scn.dialogs([dlg(1, access_hash=None), dlg(2)])
    acc = link_synced(api)
    r = start(api, acc, make_workflow(api, [text_step("a")]), chat_ids(api, acc, 1001, 1002))
    wait_status(api, r["id"], "done")
    assert run_chats(api, r["id"])[0]["error_reason"] == "The chat has no access key, sync the chats again"
    assert [m["chat_id"] for m in outbox(scn)] == [1002]


def test_a_missing_media_file_fails_that_chat_only(linked):
    app, api, scn, acc = linked
    image = upload(api, "p.jpg", jpeg_bytes(1, (60, 40)))
    wf = make_workflow(api, [text_step("a", 1), {"type": "image", "file": image, "pause_after": 0}])
    r = start(api, acc, wf, chat_ids(api, acc, 1001, 1002))
    for p in (app.storage / "telegram" / "media").glob("img-*"):    # removed behind the panel's back after the start
        p.unlink()
    final = wait_status(api, r["id"], "done")
    assert (final["errors"], final["success"]) == (2, 0)
    assert [(x["steps_done"], x["error_reason"]) for x in run_chats(api, r["id"])] == [
        (1, "The media file is missing on the server")] * 2


# --- retry -----------------------------------------------------------------------------------------------------

def test_retry_mode_repeats_the_failed_step_with_a_wait(linked):
    app, api, scn, acc = linked
    script_errors(scn, c1001={"error": "ConnectionError", "times": 2})
    wf = make_workflow(api, [text_step("a"), text_step("b")])
    ids = chat_ids(api, acc, 1001, 1002)
    r = start(api, acc, wf, ids, on_error="retry", retries=3)
    final = wait_status(api, r["id"], "done")
    assert (final["success"], final["errors"]) == (2, 0)
    sent = outbox(scn)
    assert [(m["chat_id"], m["content"]) for m in sent] == [(1001, "a"), (1001, "b"), (1002, "a"), (1002, "b")]
    assert chat_row(api, ids[0])["messages_sent"] == 2            # the failed attempts are not counted as sent


def test_retry_mode_gives_up_after_the_configured_attempts(linked):
    app, api, scn, acc = linked
    script_errors(scn, c1001={"error": "ConnectionError"})
    ids = chat_ids(api, acc, 1001, 1002)
    t0 = time.time()
    r = start(api, acc, make_workflow(api, [text_step("a")]), ids, on_error="retry", retries=2)
    final = wait_status(api, r["id"], "done")
    assert (final["success"], final["errors"]) == (1, 1)
    assert [x["status"] for x in run_chats(api, r["id"])] == ["error", "done"]
    assert outbox(scn)[0]["t"] - t0 >= 2 * RETRY_WAIT - 0.1       # two waits before the third and last attempt failed


def test_next_mode_does_not_retry(linked):
    app, api, scn, acc = linked
    script_errors(scn, c1001={"error": "ConnectionError", "times": 1})
    r = start(api, acc, make_workflow(api, [text_step("a")]), chat_ids(api, acc, 1001, 1002), retries=5)
    final = wait_status(api, r["id"], "done")
    assert (final["errors"], final["on_error"]) == (1, "next") and len(outbox(scn)) == 1


# --- FloodWait ------------------------------------------------------------------------------------------------------

def test_floodwait_is_waited_out_published_and_the_step_retried(linked):
    app, api, scn, acc = linked
    script_errors(scn, c1001={"error": "FloodWaitError", "seconds": 1, "times": 1})
    cookie = {"Cookie": f"jb_session={api.cookies['jb_session']}"}
    seen, ready = [], threading.Event()

    def reader():
        with connect(app.url.replace("http", "ws") + "/ws/modules/telegram", additional_headers=cookie,
                     open_timeout=10) as c:
            ready.set()
            while not any(m["type"] == "run" and m["status"] == "done" for m in seen):
                try:
                    seen.append(json.loads(c.recv(timeout=15)))
                except Exception:
                    return

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    assert ready.wait(10)
    t0 = time.time()
    r = start(api, acc, make_workflow(api, [text_step("a"), text_step("b")]), chat_ids(api, acc, 1001))
    flooding = wait_until(lambda: (x := run(api, r["id"]))["wait_kind"] == "flood" and x, msg="the flood wait")
    assert flooding["status"] == "running" and 0 < flooding["seconds_remaining"] <= 2 and flooding["step"]["index"] == 0
    final = wait_status(api, r["id"], "done")
    assert (final["success"], final["errors"]) == (1, 0)
    assert outbox(scn)[0]["t"] - t0 >= 1.9                      # waited the 1 s Telegram asked for, plus one
    t.join(10)
    flood = [m for m in seen if m["type"] == "flood"]
    assert flood == [{"type": "flood", "run_id": r["id"], "account_id": acc["id"], "seconds": 1}]
    assert any(m["type"] == "run" and m["wait_kind"] == "flood" for m in seen)


def test_pause_during_a_flood_wait_freezes_it(linked):
    app, api, scn, acc = linked
    script_errors(scn, c1001={"error": "FloodWaitError", "seconds": 3, "times": 1})
    r = start(api, acc, make_workflow(api, [text_step("a")]), chat_ids(api, acc, 1001))
    wait_until(lambda: run(api, r["id"])["wait_kind"] == "flood", msg="the flood wait")
    s = control(api, r["id"], "pause")
    time.sleep(4.5)
    assert outbox(scn) == [] and run(api, r["id"])["seconds_remaining"] > 2.0
    control(api, r["id"], "resume")
    wait_status(api, r["id"], "done", timeout=15)
    assert len(outbox(scn)) == 1 and s["wait_kind"] == "flood"


# --- account offline ------------------------------------------------------------------------------------------------------

def test_an_account_that_goes_offline_pauses_the_run_instead_of_failing_chats(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("a", 1), text_step("b", 0)])
    ids = chat_ids(api, acc, 1001, 1002, 1003)
    r = start(api, acc, wf, ids)
    wait_sent(scn, 1)
    ok(api.post(f"{T}/accounts/{acc['id']}/disconnect"))
    s = wait_status(api, r["id"], "paused")
    assert s["status_msg"] == "Account offline" and s["errors"] == 0 and s["step"] == {"index": 1, "type": "text"}
    assert s["seconds_remaining"] is None
    assert chat_row(api, ids[0])["chat_status"] == "paused"
    assert control(api, r["id"], "resume", 409)["detail"] == "This account is not online, connect it first"
    ok(api.post(f"{T}/accounts/{acc['id']}/connect"))
    wait_sync(api)
    assert control(api, r["id"], "resume")["status_msg"] == ""
    final = wait_status(api, r["id"], "done")
    assert (final["success"], final["errors"]) == (3, 0)
    assert [(m["chat_id"], m["content"]) for m in outbox(scn)] == [(1001, "a"), (1001, "b"), (1002, "a"), (1002, "b"),
                                                                   (1003, "a"), (1003, "b")]


# --- one run per account, several accounts ----------------------------------------------------------------------------------

def test_a_second_run_on_the_same_account_is_refused_even_when_paused(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("a", 5), text_step("b")])
    ids = chat_ids(api, acc, 1001, 1002)
    r = start(api, acc, wf, ids[:1])
    wait_sent(scn, 1)
    assert start(api, acc, wf, ids[1:], expect=409)["detail"] == "This account already has an active run"
    control(api, r["id"], "pause")
    assert start(api, acc, wf, ids[1:], expect=409)["detail"] == "This account already has an active run"
    assert ok(api.delete(f"{T}/accounts/{acc['id']}", ), 409)["detail"].startswith("This account has an active run")
    control(api, r["id"], "stop")
    control(api, start(api, acc, wf, ids[1:])["id"], "stop")


def test_two_accounts_run_at_the_same_time_but_each_works_its_chats_one_by_one(rig):
    app, api, scn = rig
    a = link_synced(api)
    b = link_synced(api, PHONE_B)
    wf = make_workflow(api, [text_step("x", 1), text_step("y", 0)])
    ra = start(api, a, wf, chat_ids(api, a, 1001, 1002, 1003))
    rb = start(api, b, wf, chat_ids(api, b, 1001, 1002, 1003))
    wait_status(api, ra["id"], "done")
    wait_status(api, rb["id"], "done")
    for phone in ("+4915100000001", PHONE_B):
        sent = outbox(scn, phone)
        assert [(m["chat_id"], m["content"]) for m in sent] == [(c, s) for c in (1001, 1002, 1003) for s in "xy"]
    first = [outbox(scn, p)[0]["t"] for p in ("+4915100000001", PHONE_B)]
    assert abs(first[0] - first[1]) < 1.0
    span = max(m["t"] for m in outbox(scn)) - min(m["t"] for m in outbox(scn))
    assert span < 4.0       # one after the other would take twice the 3 s a single account needs


# --- starting a run: validation ---------------------------------------------------------------------------------------------------------

def test_start_validation(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("a")])
    ids = chat_ids(api, acc, 1001, 1002)
    assert start(api, acc, wf, [], expect=422)["detail"] == "No chats selected"
    assert start(api, acc, wf, [ids[0], 99999], expect=422)["detail"] == "Some of the chats do not belong to this account"
    other = link_synced(api, PHONE_B)
    assert start(api, other, wf, ids, expect=422)["detail"] == "Some of the chats do not belong to this account"
    assert ok(api.post(f"{T}/runs", json={"account_id": acc["id"], "workflow_id": 999, "chat_ids": ids}), 404)
    assert ok(api.post(f"{T}/runs", json={"account_id": 999, "workflow_id": wf["id"], "chat_ids": ids}), 404)
    assert ok(api.post(f"{T}/runs", json={"account_id": acc["id"], "workflow_id": wf["id"], "chat_ids": ids,
                                          "on_error": "explode"}), 422)
    for retries in (0, 6):
        assert ok(api.post(f"{T}/runs", json={"account_id": acc["id"], "workflow_id": wf["id"], "chat_ids": ids,
                                              "on_error": "retry", "retries": retries}), 422)
    ok(api.post(f"{T}/accounts/{acc['id']}/disconnect"))
    assert start(api, acc, wf, ids, expect=409)["detail"] == "This account is not online"
    assert ok(api.get(f"{T}/runs"))["total"] == 0 and outbox(scn) == []


def test_start_refuses_a_workflow_whose_media_was_removed(linked):
    app, api, scn, acc = linked
    image = upload(api, "p.jpg", jpeg_bytes(1, (60, 40)))
    wf = make_workflow(api, [{"type": "image", "file": image, "pause_after": 0}])
    for p in (app.storage / "telegram" / "media").glob("img-*"):
        p.unlink()
    assert "does not exist" in start(api, acc, wf, chat_ids(api, acc, 1001), expect=422)["detail"]


def test_chats_keep_the_given_order_and_duplicates_count_once(linked):
    app, api, scn, acc = linked
    ids = chat_ids(api, acc, 1004, 1002, 1005)
    r = start(api, acc, make_workflow(api, [text_step("a")]), [ids[0], ids[1], ids[0], ids[2]])
    assert r["total"] == 3
    wait_status(api, r["id"], "done")
    assert [m["chat_id"] for m in outbox(scn)] == [1004, 1002, 1005]
    assert [x["chat_id"] for x in run_chats(api, r["id"])] == ids


# --- restart (a new run), listing, auth --------------------------------------------------------------------------------------------------

def test_restart_makes_a_new_run_from_the_same_snapshot_and_chats(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("v1", 1)])
    ids = chat_ids(api, acc, 1003, 1001)
    r = start(api, acc, wf, ids, on_error="retry", retries=2)
    wait_sent(scn, 1)
    control(api, r["id"], "stop")
    ok(api.put(f"{T}/workflows/{wf['id']}", json={"name": "Flow", "steps": [text_step("v2")]}))
    new = control(api, r["id"], "restart")
    assert new["id"] != r["id"] and new["status"] == "running" and new["total"] == 2
    assert (new["on_error"], new["retries"], new["workflow_id"], new["workflow_name"]) == ("retry", 2, wf["id"], "Flow")
    wait_status(api, new["id"], "done")
    assert [x["chat_id"] for x in run_chats(api, new["id"])] == ids
    assert [m["content"] for m in outbox(scn)[1:]] == ["v1", "v1"]      # the frozen snapshot, not the edited workflow
    assert run(api, r["id"])["status"] == "stopped"                      # the old run is untouched
    again = control(api, new["id"], "restart")                           # a finished run can be restarted too
    wait_status(api, again["id"], "done")


def test_list_runs_filters_and_paging(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("a")])
    ids = chat_ids(api, acc, 1001, 1002)
    made = []
    for chat in ids:
        made.append(start(api, acc, wf, [chat])["id"])
        wait_status(api, made[-1], "done")
    stopped = start(api, acc, make_workflow(api, [text_step("b", 3), text_step("c")], "Slow"), ids[:1])["id"]
    wait_sent(scn, 3)
    control(api, stopped, "stop")
    everything = ok(api.get(f"{T}/runs"))
    assert everything["total"] == 3 and [x["id"] for x in everything["items"]] == [stopped, made[1], made[0]]
    assert {x["status"] for x in ok(api.get(f"{T}/runs", params={"status": "stopped"}))["items"]} == {"stopped"}
    assert ok(api.get(f"{T}/runs", params={"status": "done,stopped"}))["total"] == 3
    assert ok(api.get(f"{T}/runs", params={"workflow_id": wf["id"]}))["total"] == 2
    assert ok(api.get(f"{T}/runs", params={"account_id": acc["id"] + 50}))["total"] == 0
    page = ok(api.get(f"{T}/runs", params={"limit": 2, "offset": 2}))
    assert page["total"] == 3 and [x["id"] for x in page["items"]] == [made[0]]
    assert ok(api.get(f"{T}/runs", params={"date_from": "2999-01-01"}))["total"] == 0
    assert api.get(f"{T}/runs", params={"status": "bogus"}).status_code == 422
    assert api.get(f"{T}/runs", params={"date_from": "yesterday"}).status_code == 422
    assert api.get(f"{T}/runs", params={"limit": 0}).status_code == 422


def test_run_chat_list_is_paged_and_filterable(linked):
    app, api, scn, acc = linked
    script_errors(scn, c1002={"error": "UserIsBlockedError"})
    r = start(api, acc, make_workflow(api, [text_step("a")]), chat_ids(api, acc, 1001, 1002, 1003, 1004))
    wait_status(api, r["id"], "done")
    page = ok(api.get(f"{T}/runs/{r['id']}/chats", params={"limit": 2, "offset": 1}))
    assert page["total"] == 4 and [x["display_name"] for x in page["items"]] == ["User2", "User3"]
    only = ok(api.get(f"{T}/runs/{r['id']}/chats", params={"status": "error"}))
    assert only["total"] == 1 and only["items"][0]["telegram_id"] == "1002" and only["items"][0]["username"] == "user2"
    assert "access_hash" not in json.dumps(page) and api.get(f"{T}/runs/999/chats").status_code == 404


def test_run_events_reach_the_websocket_with_the_live_fields(linked):
    app, api, scn, acc = linked
    cookie = {"Cookie": f"jb_session={api.cookies['jb_session']}"}
    seen, ready = [], threading.Event()

    def reader():
        with connect(app.url.replace("http", "ws") + "/ws/modules/telegram", additional_headers=cookie,
                     open_timeout=10) as c:
            ready.set()
            while not any(m["type"] == "run" and m["status"] == "done" for m in seen):
                try:
                    seen.append(json.loads(c.recv(timeout=15)))
                except Exception:
                    return

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    assert ready.wait(10)
    r = start(api, acc, make_workflow(api, [text_step("a", 1), text_step("b")]), chat_ids(api, acc, 1001, 1002))
    wait_status(api, r["id"], "done")
    t.join(10)
    events = [m for m in seen if m["type"] == "run" and m["id"] == r["id"]]
    waiting = next(m for m in events if m["wait_kind"] == "pause")
    assert waiting["chat"]["name"] == "User1" and "username" in waiting["chat"] and waiting["step"] == {"index": 0, "type": "text"}
    assert waiting["next_step_type"] == "text" and waiting["next_action_at"] and 0 < waiting["seconds_remaining"] <= 1
    assert (waiting["total"], waiting["processed"]) == (2, 0)
    assert [m["processed"] for m in events] == sorted(m["processed"] for m in events)
    assert events[-1]["status"] == "done" and events[-1]["percent"] == 100 and events[-1]["success"] == 2


def test_run_routes_need_a_login(linked):
    app, api, scn, acc = linked
    anon = httpx.Client(base_url=app.url)
    for method, path in (("get", "/runs"), ("post", "/runs"), ("get", "/runs/1"), ("get", "/runs/1/chats"),
                         ("post", "/runs/1/pause"), ("post", "/runs/1/resume"), ("post", "/runs/1/stop"),
                         ("post", "/runs/1/restart")):
        assert getattr(anon, method)(T + path).status_code in (401, 403), path
