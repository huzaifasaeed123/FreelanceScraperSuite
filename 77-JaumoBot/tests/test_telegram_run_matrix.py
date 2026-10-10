"""Telegram run engine matrix: pause / resume / stop at every position of a run, remaining pause time, rapid and concurrent
controls, stop then restart, restart recovery (hard kill and graceful stop) at several positions, on_error next / retry with
1..5 retries, FloodWait, PeerFlood, revoked session, dropped connection, parallel accounts, one run per account, stale chats,
workflow / account changes during a run and leaked asyncio tasks.
The fake client (tests/fake_telegram.py) makes sends slow with control.json "send_delay" and lists the server's asyncio tasks
with "dump_tasks"."""

import json
import threading
import time

import httpx
import pytest

from conftest import jpeg_bytes, ok, wait_until
from test_telegram_accounts import ENV, PHONE, accounts, link
from test_telegram_chats import Scenario, db, dlg, link_synced
from test_telegram_hardening import ctl, wait_account
from test_telegram_runs import (PHONE_B, T, chat_ids, chat_row, control, make_workflow, outbox, run, run_chats, start,
                                text_step, upload, wait_sent, wait_status)

FAST = {"TELEGRAM_WATCH_INTERVAL": "0.2", "TELEGRAM_RECONNECT_BASE": "0.3", "TELEGRAM_RETRY_WAIT": "0.2"}
TOL = 0.6
ENDED = "Telegram ended this session, log in again"


@pytest.fixture
def scn(tmp_path):
    return Scenario(tmp_path / "fake_tg")


@pytest.fixture
def mx(make_app, scn):
    """build(**env) -> (app, api, account): chats 1001..1006, one linked account, fast watchdog."""
    scn.dialogs([dlg(i) for i in range(1, 7)])
    envs = {}

    def build(**extra):
        envs.update({**ENV, "FAKE_TG_DIR": str(scn.dir), **FAST, **extra})
        app = make_app(**envs)
        api = app.client()
        return app, api, link_synced(api)

    build.restart = lambda app: make_app(storage=app.storage, **envs)
    return build


# --- helpers -----------------------------------------------------------------------------------------

def delay(scn, seconds):
    ctl(scn, send_delay=seconds)


def script(scn, **per_chat):
    (scn.dir / "send_errors.json").write_text(json.dumps({k.removeprefix("c"): v for k, v in per_chat.items()}))


def attempts_left(scn, chat, key="times"):
    return json.loads((scn.dir / "send_errors.json").read_text())[str(chat)][key]


def seq(chats, steps):
    return [(c, s) for c in chats for s in steps]


def sent(scn):
    return [(m["chat_id"], m["content"]) for m in outbox(scn)]


def check_integrity(api, scn, run_id):
    """What the run says it did equals what the fake Telegram received (nothing lost, nothing doubled)."""
    rows = run_chats(api, run_id)
    assert sum(r["steps_done"] for r in rows) == len(outbox(scn))
    for r in rows:
        assert chat_row(api, r["chat_id"])["messages_sent"] == len([m for m in outbox(scn) if str(m["chat_id"]) == r["telegram_id"]])
    return rows


def tasks(scn, wait_fresh=True):
    ctl(scn, dump_tasks=True)
    since = time.time()

    def read():
        try:
            d = json.loads((scn.dir / "tasks.json").read_text())
        except (OSError, ValueError):
            return None
        return d["tasks"] if d["ts"] > since else None
    return wait_until(read, timeout=10, msg="a task dump")


def count(names, part):
    return len([n for n in names if part in n])


# --- pause / resume at every position ----------------------------------------------------------------

def test_pause_during_a_send_lets_it_finish_then_freezes_the_countdown(mx, scn):
    app, api, acc = mx()
    delay(scn, 0.8)
    r = start(api, acc, make_workflow(api, [text_step("a", 2), text_step("b")]), chat_ids(api, acc, 1001))
    time.sleep(0.3)
    assert control(api, r["id"], "pause")["status"] == "paused"
    wait_sent(scn, 1)
    delay(scn, 0)
    time.sleep(0.4)
    s = run(api, r["id"])
    assert s["status"] == "paused" and abs(s["seconds_remaining"] - 2) < 0.2     # the countdown starts frozen
    time.sleep(2.4)
    assert len(outbox(scn)) == 1 and abs(run(api, r["id"])["seconds_remaining"] - 2) < 0.2
    at = time.time()
    control(api, r["id"], "resume")
    wait_status(api, r["id"], "done")
    assert abs(outbox(scn)[1]["t"] - at - 2) < TOL
    assert sent(scn) == seq([1001], "ab")


@pytest.mark.parametrize("at", [0.2, 1.0, 1.8])
def test_pause_in_the_countdown_at_any_point_keeps_the_rest(mx, scn, at):
    app, api, acc = mx()
    r = start(api, acc, make_workflow(api, [text_step("a", 2), text_step("b")]), chat_ids(api, acc, 1001))
    wait_sent(scn, 1)
    first = outbox(scn)[0]["t"]
    time.sleep(max(0, first + at - time.time()))
    p = control(api, r["id"], "pause")
    assert abs(p["seconds_remaining"] - (2 - at)) < 0.35
    time.sleep(1.0)
    control(api, r["id"], "resume")
    wait_status(api, r["id"], "done")
    gap = outbox(scn)[1]["t"] - first
    assert abs(gap - 2 - 1.0) < TOL + 0.2, gap


def test_pauses_add_up_to_the_configured_wait_over_many_cycles(mx, scn):
    app, api, acc = mx()
    r = start(api, acc, make_workflow(api, [text_step("a", 3), text_step("b")]), chat_ids(api, acc, 1001))
    wait_sent(scn, 1)
    held = 0.0
    for _ in range(3):
        time.sleep(0.4)
        control(api, r["id"], "pause")
        t = time.time()
        time.sleep(0.5)
        control(api, r["id"], "resume")
        held += time.time() - t
    wait_status(api, r["id"], "done")
    gap = outbox(scn)[1]["t"] - outbox(scn)[0]["t"]
    assert abs(gap - held - 3) < 0.8, (gap, held)


def test_pause_between_steps_without_a_pause_holds_the_next_step(mx, scn):
    app, api, acc = mx()
    delay(scn, 0.6)
    r = start(api, acc, make_workflow(api, [text_step("a"), text_step("b"), text_step("c")]), chat_ids(api, acc, 1001))
    time.sleep(0.3)
    control(api, r["id"], "pause")
    delay(scn, 0)
    time.sleep(1.5)
    assert sent(scn) == [(1001, "a")]
    s = run(api, r["id"])
    assert s["status"] == "paused" and s["step"] == {"index": 1, "type": "text"}
    assert chat_row(api, s["chat"]["id"])["chat_status"] == "paused"
    control(api, r["id"], "resume")
    wait_status(api, r["id"], "done")
    assert sent(scn) == seq([1001], "abc")


def test_pause_during_the_last_step_of_a_chat_holds_the_next_chat(mx, scn):
    app, api, acc = mx()
    delay(scn, 0.6)
    ids = chat_ids(api, acc, 1001, 1002, 1003)
    r = start(api, acc, make_workflow(api, [text_step("a")]), ids)
    time.sleep(0.3)
    control(api, r["id"], "pause")
    delay(scn, 0)
    time.sleep(1.2)
    assert sent(scn) == [(1001, "a")]
    assert chat_row(api, ids[0])["chat_status"] == "done"
    # a paused run must not show a chat as being worked on
    assert chat_row(api, ids[1])["chat_status"] in ("paused", "pending")
    control(api, r["id"], "resume")
    wait_status(api, r["id"], "done")
    assert sent(scn) == seq([1001, 1002, 1003], "a")


def test_pause_right_before_the_last_step(mx, scn):
    app, api, acc = mx()
    r = start(api, acc, make_workflow(api, [text_step("a"), text_step("b", 2), text_step("c")]), chat_ids(api, acc, 1001))
    wait_sent(scn, 2)
    s = control(api, r["id"], "pause")
    assert s["step"] == {"index": 1, "type": "text"} and s["next_step_type"] == "text"
    time.sleep(2.5)
    assert len(outbox(scn)) == 2
    control(api, r["id"], "resume")
    final = wait_status(api, r["id"], "done")
    assert (final["processed"], final["success"]) == (1, 1) and sent(scn) == seq([1001], "abc")


def test_pause_during_the_last_send_of_the_last_chat_loses_and_repeats_nothing(mx, scn):
    app, api, acc = mx()
    delay(scn, 0.6)
    r = start(api, acc, make_workflow(api, [text_step("a")]), chat_ids(api, acc, 1001))
    time.sleep(0.3)
    control(api, r["id"], "pause")
    delay(scn, 0)
    time.sleep(1.2)
    s = run(api, r["id"])
    if s["status"] == "paused":
        control(api, r["id"], "resume")
    wait_status(api, r["id"], "done")
    assert sent(scn) == [(1001, "a")]
    check_integrity(api, scn, r["id"])


def test_controls_on_a_finished_run_are_refused(mx, scn):
    app, api, acc = mx()
    r = start(api, acc, make_workflow(api, [text_step("a")]), chat_ids(api, acc, 1001))
    wait_status(api, r["id"], "done")
    for action in ("pause", "resume", "stop"):
        assert control(api, r["id"], action, 409)["detail"].endswith("it is done")
    again = control(api, r["id"], "restart")
    wait_status(api, again["id"], "done")


def test_rapid_pause_resume_cycles_never_lose_or_repeat_a_message(mx, scn):
    app, api, acc = mx()
    r = start(api, acc, make_workflow(api, [text_step("a", 1), text_step("b", 1), text_step("c")]),
              chat_ids(api, acc, 1001, 1002))
    for _ in range(40):
        control(api, r["id"], "pause")
        time.sleep(0.02)
        control(api, r["id"], "resume")
        time.sleep(0.03)
    wait_status(api, r["id"], "done", timeout=40)
    assert sent(scn) == seq([1001, 1002], "abc")
    check_integrity(api, scn, r["id"])


def test_concurrent_pause_requests_exactly_one_wins_and_so_does_resume(mx, scn):
    app, api, acc = mx()
    r = start(api, acc, make_workflow(api, [text_step("a", 4), text_step("b")]), chat_ids(api, acc, 1001))
    wait_sent(scn, 1)

    def fire(action):
        codes = []
        ts = [threading.Thread(target=lambda: codes.append(app.client().post(f"{T}/runs/{r['id']}/{action}").status_code))
              for _ in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        return sorted(codes)
    assert fire("pause") == [200] + [409] * 7
    assert fire("resume") == [200] + [409] * 7
    control(api, r["id"], "stop")


# --- stop at every position ----------------------------------------------------------------------------

def stop_setup(scn, api, acc, where):
    ids = chat_ids(api, acc, 1001, 1002, 1003)
    if where == "during_send":
        delay(scn, 0.8)
        r = start(api, acc, make_workflow(api, [text_step("a", 1), text_step("b")]), ids)
        time.sleep(0.3)
    elif where == "during_pause":
        r = start(api, acc, make_workflow(api, [text_step("a", 5), text_step("b")]), ids)
        wait_sent(scn, 1)
    elif where == "between_steps":
        delay(scn, 0.6)
        r = start(api, acc, make_workflow(api, [text_step("a"), text_step("b"), text_step("c")]), ids)
        time.sleep(0.3)
    elif where == "while_paused":
        r = start(api, acc, make_workflow(api, [text_step("a", 5), text_step("b")]), ids)
        wait_sent(scn, 1)
        control(api, r["id"], "pause")
    elif where == "flood_wait":
        script(scn, c1001={"error": "FloodWaitError", "seconds": 5, "times": 1})
        r = start(api, acc, make_workflow(api, [text_step("a"), text_step("b")]), ids)
        wait_until(lambda: run(api, r["id"])["wait_kind"] == "flood", msg="the flood wait")
    else:      # retry_wait
        script(scn, c1001={"error": "ConnectionError"})
        r = start(api, acc, make_workflow(api, [text_step("a")]), ids, on_error="retry", retries=5)
        wait_until(lambda: run(api, r["id"])["wait_kind"] == "retry", msg="the retry wait")
    return r


@pytest.mark.parametrize("where", ["during_send", "during_pause", "between_steps", "while_paused", "flood_wait", "retry_wait"])
def test_stop_at_every_position(mx, scn, where):
    app, api, acc = mx(TELEGRAM_RETRY_WAIT="3")
    r = stop_setup(scn, api, acc, where)
    s = control(api, r["id"], "stop")
    assert s["status"] == "stopped" and s["seconds_remaining"] is None and s["finished_at"]
    delay(scn, 0)
    rows = check_integrity(api, scn, r["id"])
    assert all(x["status"] in ("done", "skipped", "error") for x in rows)
    assert s["processed"] + s["skipped"] == s["total"] == 3
    n = len(outbox(scn))
    time.sleep(1.2)
    assert len(outbox(scn)) == n                          # nothing goes out after Stop
    nxt = start(api, acc, make_workflow(api, [text_step("z", 5)], "Z"), chat_ids(api, acc, 1004, 1005))     # the account is free
    control(api, nxt["id"], "stop")


def test_stop_between_chats_leaves_the_untouched_chat_pending(mx, scn):
    app, api, acc = mx()
    delay(scn, 0.6)
    ids = chat_ids(api, acc, 1001, 1002, 1003)
    r = start(api, acc, make_workflow(api, [text_step("a")]), ids)
    time.sleep(0.3)
    control(api, r["id"], "stop")
    delay(scn, 0)
    assert chat_row(api, ids[0])["chat_status"] == "done"
    for cid in ids[1:]:       # nothing was sent to them: still "not processed yet"
        c = chat_row(api, cid)
        assert c["chat_status"] == "pending" and c["messages_sent"] == 0 and c["last_processed_at"] is None


def test_stop_during_a_flood_wait_before_any_message_leaves_the_chat_untouched(mx, scn):
    app, api, acc = mx()
    script(scn, c1001={"error": "FloodWaitError", "seconds": 5, "times": 1})
    ids = chat_ids(api, acc, 1001)
    r = start(api, acc, make_workflow(api, [text_step("a")]), ids)
    wait_until(lambda: run(api, r["id"])["wait_kind"] == "flood", msg="the flood wait")
    control(api, r["id"], "stop")
    assert chat_row(api, ids[0])["chat_status"] == "pending"


def test_stop_during_the_last_send_of_the_last_chat_is_consistent(mx, scn):
    app, api, acc = mx()
    delay(scn, 0.6)
    r = start(api, acc, make_workflow(api, [text_step("a")]), chat_ids(api, acc, 1001))
    time.sleep(0.3)
    s = control(api, r["id"], "stop")
    assert s["status"] in ("stopped", "done") and sent(scn) == [(1001, "a")]
    check_integrity(api, scn, r["id"])


def test_stop_then_restart_again_and_again_starts_from_the_top(mx, scn):
    app, api, acc = mx()
    wf = make_workflow(api, [text_step("a", 1), text_step("b", 1)])
    ids = chat_ids(api, acc, 1001, 1002)
    r = start(api, acc, wf, ids)
    wait_sent(scn, 1)
    for _ in range(3):
        control(api, r["id"], "stop")
        r = control(api, r["id"], "restart")
        assert r["status"] == "running" and r["processed"] == 0 and r["total"] == 2
        wait_sent(scn, len(outbox(scn)) + 1)
    control(api, r["id"], "stop")
    final = control(api, control(api, r["id"], "restart")["id"], "stop")
    assert final["status"] == "stopped"
    assert sent(scn)[0] == (1001, "a")
    assert [m for m in sent(scn) if m[1] == "a"][:4] == [(1001, "a")] * 4       # every new run began with chat 1, step 1


def test_restart_is_refused_while_another_run_holds_the_account(mx, scn):
    app, api, acc = mx()
    wf = make_workflow(api, [text_step("a", 5)])
    r = start(api, acc, wf, chat_ids(api, acc, 1001, 1004))
    wait_sent(scn, 1)
    control(api, r["id"], "stop")
    other = start(api, acc, wf, chat_ids(api, acc, 1002, 1003))
    assert control(api, r["id"], "restart", 409)["detail"] == "This account already has an active run"
    control(api, other["id"], "stop")


# --- restart recovery (hard kill and graceful stop) ----------------------------------------------------------------

def shut(app, how):
    app.stop(kill=True) if how == "kill" else app.stop_gracefully()


def arrange(scn, api, acc, where):
    """Start a run and bring it to `where`; returns (run, the exact message sequence the finished run must have sent)."""
    ids = chat_ids(api, acc, 1001, 1002)
    if where == "mid_send":
        delay(scn, 3)
        r = start(api, acc, make_workflow(api, [text_step("a"), text_step("b", 1), text_step("c")]), ids)
        time.sleep(0.6)
        return r, seq([1001, 1002], "abc")
    if where == "mid_countdown":
        r = start(api, acc, make_workflow(api, [text_step("a", 4), text_step("b")]), ids)
        wait_sent(scn, 1)
        time.sleep(0.5)
        return r, seq([1001, 1002], "ab")
    if where == "operator_paused":
        r = start(api, acc, make_workflow(api, [text_step("a", 5), text_step("b")]), ids)
        wait_sent(scn, 1)
        time.sleep(0.8)
        control(api, r["id"], "pause")
        return r, seq([1001, 1002], "ab")
    if where == "after_chat_finished":
        r = start(api, acc, make_workflow(api, [text_step("a"), text_step("b", 3)]), ids)
        wait_sent(scn, 2)
        return r, seq([1001, 1002], "ab")
    # mid_flood
    script(scn, c1001={"error": "FloodWaitError", "seconds": 4, "times": 1})
    r = start(api, acc, make_workflow(api, [text_step("a"), text_step("b")]), ids)
    wait_until(lambda: run(api, r["id"])["wait_kind"] == "flood", msg="the flood wait")
    return r, seq([1001, 1002], "ab")


@pytest.mark.parametrize("how", ["kill", "graceful"])
@pytest.mark.parametrize("where", ["mid_send", "mid_countdown", "operator_paused", "after_chat_finished", "mid_flood"])
def test_restart_recovery_matrix_resumes_without_loss_or_duplicates(mx, scn, where, how):
    app, api, acc = mx()
    r, expected = arrange(scn, api, acc, where)
    before = len(outbox(scn))
    shut(app, how)
    delay(scn, 0)
    api2 = mx.restart(app).client()
    s = run(api2, r["id"])
    assert s["status"] == "paused" and s["errors"] == 0
    assert s["status_msg"] == ("" if where == "operator_paused" else "Server restarted")
    assert s["seconds_remaining"] is None or s["seconds_remaining"] <= 5.01
    wait_account(api2, "online")
    time.sleep(0.8)
    assert len(outbox(scn)) == before                      # a restored run waits for the operator
    remaining = s["seconds_remaining"] or 0
    at = time.time()
    assert control(api2, r["id"], "resume")["status"] == "running"
    wait_status(api2, r["id"], "done", timeout=40)
    assert sent(scn) == expected
    if where == "operator_paused":
        assert outbox(scn)[1]["t"] - at < remaining + TOL + 0.3
    if where == "mid_countdown":
        assert outbox(scn)[1]["t"] - at <= 4 + TOL           # never longer than the configured pause
    check_integrity(api2, scn, r["id"])


def test_two_restarts_in_a_row_keep_the_place(mx, scn):
    app, api, acc = mx()
    r = start(api, acc, make_workflow(api, [text_step("a", 3), text_step("b")]), chat_ids(api, acc, 1001, 1002))
    wait_sent(scn, 1)
    time.sleep(0.4)      # the message is recorded before the run's own bookkeeping: a kill in between is a different test
    app.stop(kill=True)
    app2 = mx.restart(app)
    first = run(app2.client(), r["id"])
    app2.stop(kill=True)
    api3 = mx.restart(app2).client()
    again = run(api3, r["id"])
    assert again["status"] == "paused" and again["chat"] == first["chat"] and again["step"] == first["step"]
    wait_account(api3, "online")
    control(api3, r["id"], "resume")
    wait_status(api3, r["id"], "done")
    assert sent(scn) == seq([1001, 1002], "ab")


def test_workflow_snapshot_survives_a_restart_even_if_the_workflow_changed_meanwhile(mx, scn):
    app, api, acc = mx()
    wf = make_workflow(api, [text_step("old1", 3), text_step("old2")])
    r = start(api, acc, wf, chat_ids(api, acc, 1001))
    wait_sent(scn, 1)
    ok(api.put(f"{T}/workflows/{wf['id']}", json={"name": "Renamed", "steps": [text_step("new", 0)]}))
    app.stop(kill=True)
    api2 = mx.restart(app).client()
    wait_account(api2, "online")
    control(api2, r["id"], "resume")
    s = wait_status(api2, r["id"], "done")
    assert s["workflow_name"] == "Flow" and [m[1] for m in sent(scn)] == ["old1", "old2"]


# --- on_error modes ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_retry_mode_succeeds_when_the_step_works_again_within_n_retries(mx, scn, n):
    app, api, acc = mx()
    script(scn, c1001={"error": "ConnectionError", "times": n})
    t0 = time.time()
    r = start(api, acc, make_workflow(api, [text_step("a")]), chat_ids(api, acc, 1001, 1002), on_error="retry", retries=n)
    final = wait_status(api, r["id"], "done")
    assert (final["success"], final["errors"]) == (2, 0)
    assert sent(scn) == [(1001, "a"), (1002, "a")]
    assert outbox(scn)[0]["t"] - t0 >= n * 0.2 - 0.1


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_retry_mode_gives_up_after_exactly_n_extra_attempts(mx, scn, n):
    app, api, acc = mx()
    script(scn, c1001={"error": "ConnectionError", "times": 100})
    r = start(api, acc, make_workflow(api, [text_step("a")]), chat_ids(api, acc, 1001, 1002), on_error="retry", retries=n)
    final = wait_status(api, r["id"], "done")
    assert (final["success"], final["errors"]) == (1, 1)
    assert attempts_left(scn, 1001) == 100 - (n + 1)
    assert run_chats(api, r["id"])[0]["error_reason"] == "Could not reach Telegram (network problem)"


def test_retry_budget_is_per_step(mx, scn):
    app, api, acc = mx()
    script(scn, c1001={"error": "ConnectionError", "times": 1})
    r = start(api, acc, make_workflow(api, [text_step("a"), text_step("b")]), chat_ids(api, acc, 1001), on_error="retry", retries=1)
    wait_status(api, r["id"], "done")
    script(scn, c1001={"error": "ConnectionError", "times": 1, "after": 1})      # the second step fails once
    again = control(api, r["id"], "restart")
    final = wait_status(api, again["id"], "done")
    assert final["errors"] == 0 and sent(scn) == seq([1001], "ab") * 2


def test_next_mode_continues_through_a_run_where_every_chat_fails(mx, scn):
    app, api, acc = mx()
    script(scn, **{f"c{c}": {"error": "UserPrivacyRestrictedError"} for c in (1001, 1002, 1003)})
    ids = chat_ids(api, acc, 1001, 1002, 1003)
    r = start(api, acc, make_workflow(api, [text_step("a", 5), text_step("b")]), ids)
    t0 = time.time()
    final = wait_status(api, r["id"], "done")
    assert (final["errors"], final["success"], final["percent"]) == (3, 0, 100) and time.time() - t0 < 4    # no pause after a failure
    assert [chat_row(api, i)["chat_status"] for i in ids] == ["error"] * 3 and outbox(scn) == []


def test_a_failed_chat_starts_clean_in_the_next_run_and_loses_its_error(mx, scn):
    app, api, acc = mx()
    script(scn, c1001={"error": "UserIsBlockedError", "times": 1})
    ids = chat_ids(api, acc, 1001)
    r = start(api, acc, make_workflow(api, [text_step("a")]), ids)
    wait_status(api, r["id"], "done")
    assert chat_row(api, ids[0])["error_reason"]
    wait_status(api, control(api, r["id"], "restart")["id"], "done")
    c = chat_row(api, ids[0])
    assert (c["chat_status"], c["error_reason"], c["messages_sent"]) == ("done", "", 1)


def test_pause_during_the_retry_wait_freezes_it(mx, scn):
    app, api, acc = mx(TELEGRAM_RETRY_WAIT="3")
    script(scn, c1001={"error": "ConnectionError", "times": 1})
    r = start(api, acc, make_workflow(api, [text_step("a")]), chat_ids(api, acc, 1001), on_error="retry", retries=2)
    wait_until(lambda: run(api, r["id"])["wait_kind"] == "retry", msg="the retry wait")
    control(api, r["id"], "pause")
    time.sleep(3.5)
    assert outbox(scn) == []
    control(api, r["id"], "resume")
    wait_status(api, r["id"], "done", timeout=15)
    assert sent(scn) == [(1001, "a")]


# --- FloodWait / PeerFlood ----------------------------------------------------------------------------------

def test_flood_wait_on_a_later_chat_delays_only_that_chat(mx, scn):
    app, api, acc = mx()
    script(scn, c1002={"error": "FloodWaitError", "seconds": 1, "times": 1})
    r = start(api, acc, make_workflow(api, [text_step("a"), text_step("b")]), chat_ids(api, acc, 1001, 1002, 1003))
    final = wait_status(api, r["id"], "done")
    assert final["errors"] == 0 and sent(scn) == seq([1001, 1002, 1003], "ab")
    rows = outbox(scn)
    assert rows[2]["t"] - rows[1]["t"] >= 1.9 and rows[1]["t"] - rows[0]["t"] < 1


def test_flood_waits_are_given_up_after_many_in_a_row_and_the_run_goes_on(mx, scn):
    app, api, acc = mx()
    script(scn, c1001={"error": "FloodWaitError", "seconds": 0, "times": 100})
    r = start(api, acc, make_workflow(api, [text_step("a")]), chat_ids(api, acc, 1001, 1002))
    final = wait_status(api, r["id"], "done", timeout=40)
    assert (final["errors"], final["success"]) == (1, 1)
    assert "FloodWait" in run_chats(api, r["id"])[0]["error_reason"] and sent(scn) == [(1002, "a")]


def test_flood_waits_do_not_use_up_the_retry_budget(mx, scn):
    app, api, acc = mx()
    script(scn, c1001={"error": "FloodWaitError", "seconds": 0, "times": 3})
    r = start(api, acc, make_workflow(api, [text_step("a")]), chat_ids(api, acc, 1001), on_error="retry", retries=1)
    assert wait_status(api, r["id"], "done", timeout=20)["errors"] == 0


def test_peer_flood_in_several_chats_counts_each_and_the_run_continues(mx, scn):
    app, api, acc = mx()
    script(scn, c1002={"error": "PeerFloodError"}, c1003={"error": "PeerFloodError", "after": 1})
    r = start(api, acc, make_workflow(api, [text_step("a"), text_step("b")]), chat_ids(api, acc, 1001, 1002, 1003, 1004))
    final = wait_status(api, r["id"], "done")
    assert (final["success"], final["errors"], final["peer_floods"]) == (2, 2, 2)
    assert [x["steps_done"] for x in run_chats(api, r["id"])] == [2, 0, 1, 2]


def test_peer_flood_with_retries_is_counted_once_per_chat(mx, scn):
    app, api, acc = mx()
    script(scn, c1001={"error": "PeerFloodError", "times": 100})
    r = start(api, acc, make_workflow(api, [text_step("a")]), chat_ids(api, acc, 1001, 1002), on_error="retry", retries=2)
    final = wait_status(api, r["id"], "done")
    assert (final["peer_floods"], final["errors"]) == (1, 1) and attempts_left(scn, 1001) == 97


# --- revoked session / dropped connection ------------------------------------------------------------------------

def test_a_send_that_finds_the_session_revoked_pauses_and_the_message_goes_out_once_after_relogin(mx, scn):
    app, api, acc = mx()
    script(scn, c1002={"error": "AuthKeyUnregisteredError", "times": 1})
    r = start(api, acc, make_workflow(api, [text_step("a"), text_step("b")]), chat_ids(api, acc, 1001, 1002, 1003))
    s = wait_status(api, r["id"], "paused")
    assert s["status_msg"] == ENDED and s["errors"] == 0 and s["chat"]["name"] == "User2"
    wait_account(api, "error")
    link(api)
    control(api, r["id"], "resume")
    final = wait_status(api, r["id"], "done")
    assert final["errors"] == 0 and sent(scn) == seq([1001, 1002, 1003], "ab")


def test_revoked_session_then_server_restart_then_relogin_resumes(mx, scn):
    app, api, acc = mx()
    r = start(api, acc, make_workflow(api, [text_step("a", 3), text_step("b")]), chat_ids(api, acc, 1001))
    wait_sent(scn, 1)
    ctl(scn, ban=[PHONE])
    wait_status(api, r["id"], "paused")
    app.stop(kill=True)
    ctl(scn, ban=[])
    api2 = mx.restart(app).client()
    assert run(api2, r["id"])["status"] == "paused"
    assert control(api2, r["id"], "resume", 409)
    link(api2)
    control(api2, r["id"], "resume")
    wait_status(api2, r["id"], "done")
    assert sent(scn) == seq([1001], "ab")


def test_operator_pause_is_kept_when_the_session_is_revoked_meanwhile(mx, scn):
    app, api, acc = mx(TELEGRAM_AUTH_PROBE="0.3")
    r = start(api, acc, make_workflow(api, [text_step("a", 3), text_step("b")]), chat_ids(api, acc, 1001))
    wait_sent(scn, 1)
    control(api, r["id"], "pause")
    ctl(scn, revoke=[PHONE])
    wait_account(api, "error")
    assert run(api, r["id"])["status"] == "paused"
    assert control(api, r["id"], "resume", 409)["detail"] == "This account is not online, connect it first"
    ctl(scn, revoke=[])
    link(api)
    time.sleep(0.8)
    assert run(api, r["id"])["status"] == "paused"          # relogin does not lift a pause the operator set
    control(api, r["id"], "resume")
    wait_status(api, r["id"], "done")
    assert sent(scn) == seq([1001], "ab")


def test_a_drop_during_the_countdown_freezes_it_and_auto_resume_continues_with_the_rest(mx, scn):
    app, api, acc = mx()
    r = start(api, acc, make_workflow(api, [text_step("a", 4), text_step("b")]), chat_ids(api, acc, 1001), auto_resume=True)
    wait_sent(scn, 1)
    time.sleep(0.8)
    ctl(scn, down=[PHONE])
    p = wait_status(api, r["id"], "paused")
    left = p["seconds_remaining"]
    assert 2 < left < 3.6
    time.sleep(1.5)
    assert abs(run(api, r["id"])["seconds_remaining"] - left) < 0.2
    ctl(scn, down=[])
    back = wait_status(api, r["id"], "running", "done", timeout=30)
    seen = time.time()
    wait_status(api, r["id"], "done", timeout=30)
    assert outbox(scn)[1]["t"] - seen <= left + TOL and sent(scn) == seq([1001], "ab")


def test_two_drops_in_one_run_lose_nothing(mx, scn):
    app, api, acc = mx()
    r = start(api, acc, make_workflow(api, [text_step("a", 1), text_step("b", 1), text_step("c")]),
              chat_ids(api, acc, 1001, 1002), auto_resume=True)
    for n in (1, 3):
        wait_sent(scn, n)
        ctl(scn, drop=[PHONE])
    final = wait_status(api, r["id"], "done", timeout=40)
    assert final["errors"] == 0 and sent(scn) == seq([1001, 1002], "abc")


def test_a_drop_during_a_send_in_retry_mode_does_not_use_a_retry(mx, scn):
    app, api, acc = mx()
    ctl(scn, drop_on_send=[PHONE])
    r = start(api, acc, make_workflow(api, [text_step("a")]), chat_ids(api, acc, 1001), on_error="retry", retries=1, auto_resume=True)
    final = wait_status(api, r["id"], "done", timeout=30)
    assert final["errors"] == 0 and sent(scn) == [(1001, "a")]


# --- accounts in parallel / one run per account -----------------------------------------------------------------------

def test_two_accounts_are_independent_pause_revoke_and_stop(mx, scn):
    app, api, a = mx()
    b = link_synced(api, PHONE_B)
    wf = make_workflow(api, [text_step("x", 1), text_step("y")])
    ra = start(api, a, wf, chat_ids(api, a, 1001, 1002))
    rb = start(api, b, wf, chat_ids(api, b, 1001, 1002))
    wait_sent(scn, 2)
    control(api, ra["id"], "pause")
    wait_status(api, rb["id"], "done")                     # B is not held up by A's pause
    assert run(api, ra["id"])["status"] == "paused" and len(outbox(scn, PHONE)) <= 2
    assert chat_row(api, chat_ids(api, b, 1001)[0])["chat_status"] == "done"
    assert chat_row(api, chat_ids(api, a, 1002)[0])["chat_status"] == "pending"      # same Telegram id, other account
    control(api, ra["id"], "resume")
    wait_status(api, ra["id"], "done")
    for p in (PHONE, PHONE_B):
        assert [(m["chat_id"], m["content"]) for m in outbox(scn, p)] == seq([1001, 1002], "xy")


def test_a_revoked_account_does_not_disturb_the_other_accounts_run(mx, scn):
    app, api, a = mx()
    b = link_synced(api, PHONE_B)
    wf = make_workflow(api, [text_step("x", 1), text_step("y")])
    ra = start(api, a, wf, chat_ids(api, a, 1001, 1002))
    rb = start(api, b, wf, chat_ids(api, b, 1001, 1002))
    wait_sent(scn, 2)
    ctl(scn, ban=[PHONE])
    wait_status(api, ra["id"], "paused")
    final = wait_status(api, rb["id"], "done")
    assert final["errors"] == 0 and len(outbox(scn, PHONE_B)) == 4
    control(api, ra["id"], "stop")


def test_stopping_one_account_leaves_the_other_running(mx, scn):
    app, api, a = mx()
    b = link_synced(api, PHONE_B)
    wf = make_workflow(api, [text_step("x", 1), text_step("y")])
    ra = start(api, a, wf, chat_ids(api, a, 1001, 1002))
    rb = start(api, b, wf, chat_ids(api, b, 1001, 1002))
    wait_sent(scn, 2)
    control(api, ra["id"], "stop")
    assert wait_status(api, rb["id"], "done")["success"] == 2


def test_concurrent_starts_on_one_account_exactly_one_wins(mx, scn):
    app, api, acc = mx()
    wf = make_workflow(api, [text_step("a", 3)])
    ids = chat_ids(api, acc, 1001, 1002)
    codes = []
    body = {"account_id": acc["id"], "workflow_id": wf["id"], "chat_ids": ids}
    ts = [threading.Thread(target=lambda: codes.append(app.client().post(f"{T}/runs", json=body).status_code)) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(codes) == [200] + [409] * 7
    assert ok(api.get(f"{T}/runs"))["total"] == 1
    control(api, ok(api.get(f"{T}/runs"))["items"][0]["id"], "stop")


def test_a_restored_paused_run_still_blocks_a_new_run_on_its_account(mx, scn):
    app, api, acc = mx()
    wf = make_workflow(api, [text_step("a", 5)])
    r = start(api, acc, wf, chat_ids(api, acc, 1001, 1002))
    wait_sent(scn, 1)
    time.sleep(0.4)
    app.stop(kill=True)
    api2 = mx.restart(app).client()
    wait_account(api2, "online")
    assert start(api2, acc, wf, chat_ids(api2, acc, 1003), expect=409)["detail"] == "This account already has an active run"
    control(api2, r["id"], "stop")
    control(api2, start(api2, acc, wf, chat_ids(api2, acc, 1003, 1004))["id"], "stop")


# --- stale chats ----------------------------------------------------------------------------------------------------

def test_selection_with_unknown_foreign_or_removed_chats_is_refused_and_nothing_runs(mx, scn):
    app, api, acc = mx()
    other = link_synced(api, PHONE_B)
    wf = make_workflow(api, [text_step("a")])
    ids = chat_ids(api, acc, 1001, 1002)
    db(app, "delete from tg_chat where id=?", ids[1])
    for bad in ([ids[0], ids[1]], [ids[0], chat_ids(api, other, 1001)[0]], [0], [-1]):
        assert start(api, acc, wf, bad, expect=422)["detail"] == "Some of the chats do not belong to this account"
    assert api.post(f"{T}/runs", json={"account_id": acc["id"], "workflow_id": wf["id"], "chat_ids": ["x"]}).status_code == 422
    assert outbox(scn) == [] and ok(api.get(f"{T}/runs"))["total"] == 0


def test_a_stale_recipient_fails_that_chat_in_both_modes_and_the_rest_go_on(mx, scn):
    app, api, acc = mx()
    script(scn, c1002={"error": "PeerIdInvalidError", "times": 100})
    for kw in ({}, {"on_error": "retry", "retries": 2}):
        r = start(api, acc, make_workflow(api, [text_step("a")], f"F{len(kw)}"), chat_ids(api, acc, 1001, 1002, 1003), **kw)
        final = wait_status(api, r["id"], "done")
        assert (final["success"], final["errors"]) == (2, 1)
        assert run_chats(api, r["id"])[1]["error_reason"] == "Invalid recipient (the chat could not be found)"


def test_a_chat_row_deleted_during_a_run_does_not_end_the_run(mx, scn):
    app, api, acc = mx()
    ids = chat_ids(api, acc, 1001, 1002, 1003)
    r = start(api, acc, make_workflow(api, [text_step("a", 2)]), ids)
    wait_sent(scn, 1)
    control(api, r["id"], "pause")
    db(app, "delete from tg_chat where id=?", ids[1])
    control(api, r["id"], "resume")
    final = wait_status(api, r["id"], "done", timeout=20)
    assert (1003, "a") in sent(scn), final


def test_a_resync_during_a_run_leaves_the_run_and_chat_states_alone(mx, scn):
    app, api, acc = mx()
    ids = chat_ids(api, acc, 1001, 1002)
    r = start(api, acc, make_workflow(api, [text_step("a", 2)]), ids)
    wait_sent(scn, 1)
    scn.dialogs([dlg(2)])                                   # Telegram no longer lists chat 1001
    ok(api.post(f"{T}/accounts/{acc['id']}/sync-chats"))
    wait_until(lambda: accounts(api)[PHONE]["sync"] is None, msg="sync")
    final = wait_status(api, r["id"], "done")
    assert final["success"] == 2 and sent(scn) == [(1001, "a"), (1002, "a")]
    assert chat_row(api, ids[0])["chat_status"] == "done"


# --- workflow / account changes during a run -----------------------------------------------------------------------------

def test_workflow_edit_rename_and_pause_change_do_not_touch_a_running_run(mx, scn):
    app, api, acc = mx()
    wf = make_workflow(api, [text_step("a", 2), text_step("b", 0), text_step("c")])
    r = start(api, acc, wf, chat_ids(api, acc, 1001))
    wait_sent(scn, 1)
    ok(api.put(f"{T}/workflows/{wf['id']}", json={"name": "New", "steps": [text_step("z", 0)]}))
    wait_status(api, r["id"], "done")
    rows = outbox(scn)
    assert [m["content"] for m in rows] == ["a", "b", "c"] and rows[1]["t"] - rows[0]["t"] >= 1.7
    assert run(api, r["id"])["workflow_name"] == "Flow"


@pytest.mark.parametrize("paused", [False, True])
def test_a_workflow_with_an_active_run_cannot_be_deleted_but_can_after_stop(mx, scn, paused):
    app, api, acc = mx()
    wf = make_workflow(api, [text_step("a", 5), text_step("b")])
    r = start(api, acc, wf, chat_ids(api, acc, 1001))
    wait_sent(scn, 1)
    if paused:
        control(api, r["id"], "pause")
    assert ok(api.delete(f"{T}/workflows/{wf['id']}"), 409)["detail"] == "This workflow has an active run, stop it first"
    control(api, r["id"], "stop")
    ok(api.delete(f"{T}/workflows/{wf['id']}"))
    s = run(api, r["id"])
    assert s["workflow_name"] == "Flow" and s["workflow_id"] is None
    new = control(api, r["id"], "restart")                  # the frozen snapshot is enough
    wait_status(api, new["id"], "done", timeout=20)
    assert [m[1] for m in sent(scn)][-2:] == ["a", "b"]


def test_a_media_file_used_only_by_a_running_run_cannot_be_deleted_and_is_still_sent(mx, scn):
    app, api, acc = mx()
    img = upload(api, "p.jpg", jpeg_bytes(1, (60, 40)))
    wf = make_workflow(api, [text_step("a", 1), {"type": "image", "file": img, "pause_after": 0}])
    r = start(api, acc, wf, chat_ids(api, acc, 1001))
    wait_sent(scn, 1)
    ok(api.put(f"{T}/workflows/{wf['id']}", json={"name": "Flow", "steps": [text_step("other")]}))
    assert api.delete(f"{T}/media/{img}").status_code == 409
    final = wait_status(api, r["id"], "done")
    assert final["errors"] == 0 and outbox(scn)[1]["type"] == "image"


def test_removing_an_account_with_an_active_run_is_refused_and_the_run_continues(mx, scn):
    app, api, acc = mx()
    r = start(api, acc, make_workflow(api, [text_step("a", 1), text_step("b")]), chat_ids(api, acc, 1001))
    wait_sent(scn, 1)
    assert ok(api.delete(f"{T}/accounts/{acc['id']}"), 409)["detail"].startswith("This account has an active run")
    assert wait_status(api, r["id"], "done")["success"] == 1


def test_removing_an_account_after_stop_leaves_no_orphans_and_no_tasks(mx, scn):
    app, api, a = mx()
    b = link_synced(api, PHONE_B)
    wf = make_workflow(api, [text_step("x", 1), text_step("y")])
    ra = start(api, a, wf, chat_ids(api, a, 1001, 1002))
    rb = start(api, b, wf, chat_ids(api, b, 1001))
    wait_sent(scn, 2)
    control(api, ra["id"], "stop")
    ok(api.delete(f"{T}/accounts/{a['id']}"))
    assert db(app, "select count(*) from tg_run where account_id=?", a["id"]) == [(0,)]
    assert db(app, "select count(*) from tg_run_chat where run_id=?", ra["id"]) == [(0,)]
    assert db(app, "select count(*) from tg_chat where account_id=?", a["id"]) == [(0,)]
    assert wait_status(api, rb["id"], "done")["success"] == 1
    names = tasks(scn)
    assert count(names, "_watch") == 1 and count(names, "_drive") == 0


# --- leaked tasks ---------------------------------------------------------------------------------------------------------

def test_no_run_tasks_are_left_after_runs_end_in_every_way(mx, scn):
    app, api, acc = mx()
    base = tasks(scn)
    assert count(base, "_watch") == 1 and count(base, "_tail_inbox") == 1 and count(base, "_drive") == 0
    wf = make_workflow(api, [text_step("a", 1), text_step("b")])
    ids = chat_ids(api, acc, 1001, 1002)
    wait_status(api, start(api, acc, wf, ids)["id"], "done")                              # finished
    r = start(api, acc, wf, ids)
    wait_sent(scn, 3)
    control(api, r["id"], "stop")                                                         # stopped in a pause
    r = start(api, acc, wf, ids)
    control(api, r["id"], "pause")
    control(api, r["id"], "stop")                                                         # stopped while paused
    script(scn, c1001={"error": "UserIsBlockedError"})
    wait_status(api, start(api, acc, wf, ids)["id"], "done")                              # with an error
    for _ in range(10):
        control(api, start(api, acc, wf, ids)["id"], "stop")                              # start / stop in a row
    time.sleep(0.5)
    names = tasks(scn)
    for part in ("_drive", "RunEngine._wait", "_run_sync", "_recover"):
        assert count(names, part) == 0, (part, names)
    assert count(names, "_watch") == 1 and count(names, "_tail_inbox") == 1


def test_reconnect_cycles_leave_one_watcher_and_no_recovery_tasks(mx, scn):
    app, api, acc = mx()
    for _ in range(3):
        ctl(scn, drop=[PHONE])
        wait_until(lambda: accounts(api)[PHONE]["status"] != "online", timeout=5, msg="the drop")
        wait_account(api, "online")
    ok(api.post(f"{T}/accounts/{acc['id']}/disconnect"))
    time.sleep(0.5)
    ok(api.post(f"{T}/accounts/{acc['id']}/connect"))
    wait_account(api, "online")
    time.sleep(0.5)
    names = tasks(scn)
    assert count(names, "_watch") == 1 and count(names, "_recover") == 0 and count(names, "_tail_inbox") == 1


def test_graceful_shutdown_after_many_runs_is_clean(mx, scn):
    app, api, acc = mx(PYTHONWARNINGS="default::ResourceWarning")
    wf = make_workflow(api, [text_step("a", 1), text_step("b")])
    ids = chat_ids(api, acc, 1001, 1002)
    for _ in range(4):
        control(api, start(api, acc, wf, ids)["id"], "stop")
    start(api, acc, wf, ids)
    wait_sent(scn, 1)
    app.stop_gracefully()
    log = app.log.read_text(errors="replace")
    assert "Application shutdown complete" in log
    for noise in ("Task was destroyed", "never awaited", "ResourceWarning", "Traceback", "Task exception"):
        assert noise not in log, noise
    conns = [json.loads(x) for x in (scn.dir / "connections.jsonl").read_text().splitlines()]
    assert {c["client"] for c in conns if c["event"] == "connect"} == {c["client"] for c in conns if c["event"] == "disconnect"}
