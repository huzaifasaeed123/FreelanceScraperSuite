"""Telegram dashboard and history: GET /stats (every number of brief section 13, with and without the account filter),
the run list with durations, the per-chat results with timestamps and error reasons, CSV exports, cleanup of old runs
and deleting a run. Finished runs are written straight into the database so every number can be counted by hand;
the live-run cases use the real engine with the fake Telethon client."""

import csv
import io
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from conftest import ok
from test_telegram_chats import chats, db, scn  # noqa: F401  (scn, rig, linked: pytest fixtures, used by name)
from test_telegram_runs import chat_ids, control, linked, make_workflow, rig, run, run_chats, start, text_step, wait_status  # noqa: F401

T = "/api/telegram"


# --- helpers ---------------------------------------------------------------------------------------------

def stamp(d: datetime) -> str:
    """A datetime as SQLAlchemy stores it in SQLite."""
    return d.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")


def on_day(days_ago: int) -> datetime:
    """A moment on the UTC day `days_ago` days back: noon, or for today one minute past midnight (never in the future,
    so a run started by a test always ends after it). The day a row falls on cannot change while a test runs."""
    midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight + timedelta(minutes=1) if days_ago == 0 else midnight - timedelta(days=days_ago) + timedelta(hours=12)


def add_account(app, phone="+4915100000009"):
    db(app, "insert into tg_account (label, phone, api_id, api_hash, session_string, status, status_msg, auto_connect, "
            "tg_username, created_at) values ('Second', ?, 1, 'h', '', 'offline', '', 0, '', ?)", phone, stamp(on_day(30)))
    return db(app, "select id from tg_account where phone=?", phone)[0][0]


def add_chat(app, account_id, n, status="pending", sent=0, name=None):
    db(app, "insert into tg_chat (account_id, telegram_id, access_hash, search_text, username, display_name, last_message, "
            "chat_status, messages_sent, error_reason, notes, created_at) values (?, ?, '1', ?, '', ?, '', ?, ?, '', '', ?)",
       account_id, str(9000 + n), (name or f"B{n}").casefold(), name or f"B{n}", status, sent, stamp(on_day(30)))
    return db(app, "select id from tg_chat where telegram_id=?", str(9000 + n))[0][0]


def add_run(app, account_id, results, status="done", ended=None, seconds=60, name="Flow", workflow_id=None):
    """A finished run. results = [(chat_id, status, error_reason)] with status done | error | skipped | pending.
    The run took `seconds` and ended at `ended` (None = still active, no end)."""
    done = sum(1 for _, st, _ in results if st == "done")
    failed = sum(1 for _, st, _ in results if st == "error")
    started = (ended or on_day(0)) - timedelta(seconds=seconds)
    db(app, "insert into tg_run (account_id, workflow_id, workflow_name, workflow_snapshot, status, total_chats, processed, "
            "success, errors, on_error, retries, wait_kind, status_msg, current_step_index, created_at, started_at, finished_at) "
            "values (?, ?, ?, '{\"steps\": [{\"type\": \"text\", \"content\": \"a\", \"pause_after\": 0}, {\"type\": \"text\", \"content\": \"b\", \"pause_after\": 0}]}', ?, ?, ?, ?, ?, 'next', 3, '', '', 0, ?, ?, ?)",
       account_id, workflow_id, name, status, len(results), done + failed, done, failed,
       stamp(started), stamp(started), stamp(ended) if ended else None)
    run_id = db(app, "select max(id) from tg_run")[0][0]
    for pos, (chat_id, st, reason) in enumerate(results):
        at = stamp(ended - timedelta(seconds=len(results) - pos)) if ended and st in ("done", "error") else None
        db(app, "insert into tg_run_chat (run_id, chat_id, position, status, steps_done, error_reason, started_at, processed_at) "
                "values (?, ?, ?, ?, ?, ?, ?, ?)", run_id, chat_id, pos, st, 2 if st == "done" else 0, reason,
           at, at)
    return run_id


def age(app, run_id, days):
    """Make a run end exactly this many days before now (the fixture ages depend on the time of day)."""
    db(app, "update tg_run set finished_at=? where id=?", stamp(datetime.now(timezone.utc) - timedelta(days=days)), run_id)


def stats(api, **params):
    return ok(api.get(f"{T}/stats", params=params))


def parse_csv(text):
    assert text.startswith("\ufeff"), "the file starts with a byte order mark so Excel reads UTF-8"
    return list(csv.reader(io.StringIO(text[1:])))


@pytest.fixture
def hist(linked):
    """Account A (five synced chats) and a second account B with two chats, plus crafted finished runs:
    A/R1 done 2 ok + 1 error two days ago, A/R2 stopped 1 ok + 2 skipped yesterday, B/R3 done 1 ok today."""
    app, api, scn, acc = linked
    a = chat_ids(api, acc, 1001, 1002, 1003, 1004, 1005)
    ok(api.post(f"{T}/chats/bulk-status", json={"ids": a[:2], "status": "done"}))
    ok(api.post(f"{T}/chats/bulk-status", json={"ids": [a[2]], "status": "error"}))
    ok(api.post(f"{T}/chats/bulk-status", json={"ids": [a[3]], "status": "paused"}))
    for cid, sent in zip(a[:3], (3, 3, 1)):
        db(app, "update tg_chat set messages_sent=? where id=?", sent, cid)
    b_acc = add_account(app)
    b = [add_chat(app, b_acc, 1, "done", 2), add_chat(app, b_acc, 2)]
    r1 = add_run(app, acc["id"], [(a[0], "done", ""), (a[1], "done", ""), (a[2], "error", "The user has blocked this account")],
                 ended=on_day(2), seconds=95, name="Neukontakt")
    r2 = add_run(app, acc["id"], [(a[3], "done", ""), (a[4], "skipped", ""), (a[0], "skipped", "")], status="stopped",
                 ended=on_day(1), seconds=30, name="Follow-up")
    r3 = add_run(app, b_acc, [(b[0], "done", "")], ended=on_day(0), seconds=5, name="Neukontakt")
    return app, api, scn, acc, {"a": a, "b": b, "b_acc": b_acc, "runs": (r1, r2, r3)}


# --- /stats ------------------------------------------------------------------------------------------------

def test_stats_of_an_empty_server_are_all_zero(rig):
    app, api, scn = rig
    s = stats(api)
    assert s["chats"] == {"total": 0, "unprocessed": 0, "processed": 0, "errors": 0, "in_progress": 0, "paused": 0}
    assert s["sends"] == {"successful": 0, "failed": 0, "messages": 0}
    assert (s["runs"], s["active_run"], s["last_run"], s["accounts"], s["accounts_online"]) == (0, None, None, 0, 0)
    assert len(s["per_day"]) == 14 and all(d["successful"] == d["failed"] == 0 for d in s["per_day"])


def test_stats_count_chats_sends_runs_and_days_correctly(hist):
    app, api, scn, acc, x = hist
    s = stats(api)
    # five chats of A (2 done, 1 error, 1 paused, 1 pending) and two of B (1 done, 1 pending)
    assert s["chats"] == {"total": 7, "unprocessed": 2, "processed": 3, "errors": 1, "in_progress": 0, "paused": 1}
    assert s["sends"] == {"successful": 4, "failed": 1, "messages": 3 + 3 + 1 + 2}
    assert (s["runs"], s["accounts"], s["accounts_online"]) == (3, 2, 1)
    assert s["active_run"] is None
    assert s["last_run"]["id"] == x["runs"][2] and s["last_run"]["status"] == "done"
    assert (s["last_run"]["total"], s["last_run"]["success"], s["last_run"]["duration_seconds"]) == (1, 1, 5)

    by_day = {d["date"]: (d["successful"], d["failed"]) for d in s["per_day"]}
    assert len(by_day) == 14
    assert by_day[on_day(2).date().isoformat()] == (2, 1)
    assert by_day[on_day(1).date().isoformat()] == (1, 0)
    assert by_day[on_day(0).date().isoformat()] == (1, 0)
    assert sum(a + b for a, b in by_day.values()) == 5
    assert list(by_day) == sorted(by_day) and list(by_day)[-1] == datetime.now(timezone.utc).date().isoformat()


def test_stats_can_be_limited_to_one_account_and_a_number_of_days(hist):
    app, api, scn, acc, x = hist
    s = stats(api, account_id=acc["id"])
    assert s["chats"] == {"total": 5, "unprocessed": 1, "processed": 2, "errors": 1, "in_progress": 0, "paused": 1}
    assert s["sends"] == {"successful": 3, "failed": 1, "messages": 7}
    assert s["runs"] == 2 and s["last_run"]["id"] == x["runs"][1] and s["last_run"]["status"] == "stopped"
    assert s["last_run"]["skipped"] == 2
    b = stats(api, account_id=x["b_acc"])
    assert b["chats"]["total"] == 2 and b["sends"] == {"successful": 1, "failed": 0, "messages": 2}
    assert b["last_run"]["id"] == x["runs"][2]

    assert len(stats(api, days=3)["per_day"]) == 3
    assert sum(d["successful"] + d["failed"] for d in stats(api, days=2)["per_day"]) == 2     # yesterday and today only
    ok(api.get(f"{T}/stats", params={"account_id": 9999}), 404)
    ok(api.get(f"{T}/stats", params={"days": 0}), 422)


def test_stats_show_the_running_workflow_with_its_chat_and_progress(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("one", 30), text_step("two", 0)], name="Langsam")
    ids = chat_ids(api, acc, 1001, 1002)
    r = start(api, acc, wf, ids)
    live = stats(api)["active_run"]
    assert (live["id"], live["workflow_name"], live["status"], live["total"], live["percent"]) == (r["id"], "Langsam", "running", 2, 0)
    assert live["chat"]["name"] == "User1" and live["duration_seconds"] is not None
    assert stats(api, account_id=acc["id"])["active_run"]["id"] == r["id"]
    assert stats(api)["last_run"] is None

    control(api, r["id"], "stop")
    done = stats(api)
    assert done["active_run"] is None and done["last_run"]["id"] == r["id"] and done["last_run"]["status"] == "stopped"
    assert done["last_run"]["skipped"] == 2


def test_a_real_run_adds_to_the_sends_and_to_today(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("hi", 0)])
    r = start(api, acc, wf, chat_ids(api, acc, 1001, 1002, 1003))
    wait_status(api, r["id"], "done")
    s = stats(api)
    assert s["sends"] == {"successful": 3, "failed": 0, "messages": 3}
    assert s["chats"]["processed"] == 3 and s["chats"]["unprocessed"] == 2
    assert s["per_day"][-1] == {"date": datetime.now(timezone.utc).date().isoformat(), "successful": 3, "failed": 0}


# --- run list, duration, per-chat results -------------------------------------------------------------------

def test_duration_is_computed_from_start_and_end(hist):
    app, api, scn, acc, x = hist
    r1, r2, r3 = x["runs"]
    assert [run(api, r)["duration_seconds"] for r in (r1, r2, r3)] == [95, 30, 5]
    listed = {r["id"]: r for r in ok(api.get(f"{T}/runs"))["items"]}
    assert listed[r1]["duration_seconds"] == 95 and listed[r1]["skipped"] == 0 and listed[r2]["skipped"] == 2
    # a run that has not started has no duration; one that is still going counts up to now
    db(app, "update tg_run set started_at=NULL, finished_at=NULL, status='queued' where id=?", r3)
    assert run(api, r3)["duration_seconds"] is None
    db(app, "update tg_run set started_at=?, status='running' where id=?", stamp(datetime.now(timezone.utc) - timedelta(seconds=40)), r3)
    assert 40 <= run(api, r3)["duration_seconds"] <= 45


def test_a_real_run_has_a_duration_that_matches_its_timestamps(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("a", 1), text_step("b", 0)])
    r = start(api, acc, wf, chat_ids(api, acc, 1001))
    final = wait_status(api, r["id"], "done")
    span = datetime.fromisoformat(final["finished_at"]) - datetime.fromisoformat(final["started_at"])
    assert final["duration_seconds"] == int(span.total_seconds()) and final["duration_seconds"] >= 1


def test_run_chats_carry_timestamps_and_error_reasons(hist):
    app, api, scn, acc, x = hist
    rows = run_chats(api, x["runs"][0])
    assert [r["status"] for r in rows] == ["done", "done", "error"]
    assert rows[2]["error_reason"] == "The user has blocked this account"
    assert all(r["started_at"] and r["processed_at"] for r in rows)
    assert datetime.fromisoformat(rows[0]["processed_at"]) < datetime.fromisoformat(rows[2]["processed_at"])
    skipped = run_chats(api, x["runs"][1])
    assert [r["status"] for r in skipped] == ["done", "skipped", "skipped"] and skipped[1]["processed_at"] is None
    assert [r["status"] for r in run_chats(api, x["runs"][0], status="error")] == ["error"]


def test_the_run_list_filters_by_workflow_account_status_and_date(hist):
    app, api, scn, acc, x = hist
    r1, r2, r3 = x["runs"]
    ids = lambda **p: [r["id"] for r in ok(api.get(f"{T}/runs", params=p))["items"]]  # noqa: E731
    assert ids() == [r3, r2, r1]
    assert ids(account_id=acc["id"]) == [r2, r1] and ids(status="stopped") == [r2] and ids(status="done,stopped") == [r3, r2, r1]
    assert ids(date_from=on_day(1).date().isoformat(), date_to=on_day(1).date().isoformat()) == [r2]
    wf = make_workflow(api, [text_step("x")], name="Echt")
    db(app, "update tg_run set workflow_id=? where id=?", wf["id"], r1)
    assert ids(workflow_id=wf["id"]) == [r1]


# --- CSV ----------------------------------------------------------------------------------------------------

def test_runs_csv_has_one_row_per_run_and_follows_the_filters(hist):
    app, api, scn, acc, x = hist
    r = api.get(f"{T}/runs/export.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"] and ".csv" in r.headers["content-disposition"]
    rows = parse_csv(r.text)
    assert rows[0] == ["run_id", "account", "workflow", "status", "started_at", "finished_at", "chats_selected",
                       "successful", "errors", "aborted", "duration_seconds"]
    r1, r2, r3 = x["runs"]
    body = {int(row[0]): row for row in rows[1:]}
    assert list(body) == [r3, r2, r1]       # newest first
    assert body[r1][1:3] == [acc["label"] or acc["phone"], "Neukontakt"]
    assert body[r1][3] == "done" and body[r1][6:] == ["3", "2", "1", "0", "95"]
    assert body[r2][3] == "stopped" and body[r2][6:] == ["3", "1", "0", "2", "30"]
    assert body[r3][1] == "Second"
    assert body[r1][4].startswith(on_day(2).date().isoformat()) or body[r1][4].startswith((on_day(2) - timedelta(minutes=2)).date().isoformat())

    only = parse_csv(api.get(f"{T}/runs/export.csv", params={"account_id": acc["id"], "status": "stopped"}).text)
    assert [row[0] for row in only[1:]] == [str(r2)]
    ok(api.get(f"{T}/runs/export.csv", params={"status": "bogus"}), 422)


def test_run_csv_lists_every_chat_with_time_result_and_reason(hist):
    app, api, scn, acc, x = hist
    db(app, "update tg_chat set display_name='=HYPERLINK(\"http://evil\")', username='-x' where id=?", x["a"][0])
    r = api.get(f"{T}/runs/{x['runs'][0]}/export.csv")
    assert r.status_code == 200 and f"telegram-run-{x['runs'][0]}.csv" in r.headers["content-disposition"]
    rows = parse_csv(r.text)
    assert rows[0] == ["position", "chat", "username", "telegram_id", "result", "steps_done", "error_reason",
                       "started_at", "processed_at"]
    assert [row[0] for row in rows[1:]] == ["1", "2", "3"]
    assert rows[1][1] == "'=HYPERLINK(\"http://evil\")" and rows[1][2] == "'-x"       # no formula can run in Excel
    assert rows[2][1:5] == ["User2", "user2", "1002", "done"]
    assert rows[3][4:7] == ["error", "0", "The user has blocked this account"]
    assert all(row[7] and row[8] for row in rows[1:])
    skipped = parse_csv(api.get(f"{T}/runs/{x['runs'][1]}/export.csv").text)
    assert [row[4] for row in skipped[1:]] == ["done", "skipped", "skipped"] and skipped[2][8] == ""
    ok(api.get(f"{T}/runs/99999/export.csv"), 404)


def test_umlauts_survive_the_csv(hist):
    app, api, scn, acc, x = hist
    db(app, "update tg_chat set display_name='Jürgen Müller 🎤' where id=?", x["a"][1])
    assert "Jürgen Müller 🎤" in parse_csv(api.get(f"{T}/runs/{x['runs'][0]}/export.csv").content.decode("utf-8"))[2][1]


# --- cleanup and delete -------------------------------------------------------------------------------------

def test_cleanup_deletes_old_finished_runs_but_keeps_the_chats(hist):
    app, api, scn, acc, x = hist
    r1, r2, r3 = x["runs"]
    age(app, r1, 3), age(app, r2, 1.5), age(app, r3, 0.2)
    before = {c["id"]: (c["chat_status"], c["messages_sent"], c["notes"]) for c in chats(api)["items"]}
    assert ok(api.post(f"{T}/runs/cleanup", json={"days": 10})) == {"deleted": 0}
    assert ok(api.post(f"{T}/runs/cleanup", json={"days": 2})) == {"deleted": 1}      # only R1 ended more than 2 days ago
    ok(api.get(f"{T}/runs/{r1}"), 404)
    assert db(app, "select count(*) from tg_run_chat where run_id=?", r1) == [(0,)]
    assert db(app, "select count(*) from tg_run_chat where run_id in (?, ?)", r2, r3) == [(4,)]
    assert {c["id"]: (c["chat_status"], c["messages_sent"], c["notes"]) for c in chats(api)["items"]} == before
    assert ok(api.post(f"{T}/runs/cleanup", json={"days": 1})) == {"deleted": 1}      # R2; R3 ended a few hours ago
    assert [r["id"] for r in ok(api.get(f"{T}/runs"))["items"]] == [r3]
    assert stats(api)["chats"]["total"] == 7


def test_cleanup_never_touches_active_runs_and_checks_its_input(hist):
    app, api, scn, acc, x = hist
    old = on_day(40)
    age(app, x["runs"][0], 5), age(app, x["runs"][1], 0.2), age(app, x["runs"][2], 0.2)
    live = add_run(app, acc["id"], [(x["a"][4], "pending", "")], status="paused", ended=None)
    db(app, "update tg_run set created_at=?, started_at=? where id=?", stamp(old), stamp(old), live)
    assert ok(api.post(f"{T}/runs/cleanup", json={"days": 1})) == {"deleted": 1}      # the paused run is 40 days old and stays
    assert run(api, live)["status"] == "paused"
    for bad in ({"days": 0}, {"days": -3}, {"days": "x"}, {}):
        ok(api.post(f"{T}/runs/cleanup", json=bad), 422)


def test_delete_a_finished_run_only(hist):
    app, api, scn, acc, x = hist
    r1, r2, r3 = x["runs"]
    live = add_run(app, acc["id"], [(x["a"][4], "pending", "")], status="paused", ended=None)
    assert "still active" in ok(api.delete(f"{T}/runs/{live}"), 409)["detail"]
    assert run(api, live)["status"] == "paused"
    assert ok(api.delete(f"{T}/runs/{r1}")) == {"ok": True}
    ok(api.get(f"{T}/runs/{r1}"), 404)
    ok(api.delete(f"{T}/runs/{r1}"), 404)
    assert db(app, "select count(*) from tg_run_chat where run_id=?", r1) == [(0,)]
    assert chats(api)["total"] == 7 and run(api, r2)["id"] == r2


def test_a_run_started_for_real_can_be_deleted_after_it_ended(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("hi", 0)])
    r = start(api, acc, wf, chat_ids(api, acc, 1001))
    wait_status(api, r["id"], "done")
    ok(api.delete(f"{T}/runs/{r['id']}"))
    assert stats(api)["runs"] == 0 and chats(api)["total"] == 5
    assert chats(api, status="done")["total"] == 1       # the chat keeps its result


def test_the_new_routes_refuse_anonymous_callers(hist):
    app, api, scn, acc, x = hist
    calls = [("GET", "/stats"), ("GET", "/runs/export.csv"), ("GET", f"/runs/{x['runs'][0]}/export.csv"),
             ("POST", "/runs/cleanup"), ("DELETE", f"/runs/{x['runs'][0]}")]
    for method, path in calls:
        r = httpx.request(method, app.url + T + path, json={"days": 1} if method == "POST" else None)
        assert r.status_code == 401, (method, path, r.status_code)
    assert len(ok(api.get(f"{T}/runs"))["items"]) == 3
