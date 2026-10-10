"""Telegram data integrity and scale: no orphan rows after deletes, duplicate chats across syncs, a database with
older tg_ tables, 10,000 chats, a 1,000-chat run with 0 s pauses, a history of 500 runs and API calls while a run
is active (against the fake Telethon client, tests/fake_telegram.py)."""

import json
import re
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from conftest import ok, wait_until
from test_telegram_accounts import ENV, PHONE, accounts, link
from test_telegram_chats import BASE, Scenario, chats, db, dlg, link_synced, wait_sync
from test_telegram_runs import chat_ids, make_workflow, outbox, run, start, text_step

T = "/api/telegram"
PHONE_B = "+4915100000003"


@pytest.fixture
def scn(tmp_path):
    return Scenario(tmp_path / "fake_tg")


@pytest.fixture
def rig(make_app, scn):
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir))
    return app, app.client(), scn


# --- helpers ---------------------------------------------------------------------------------------------

ORPHAN_QUERIES = {
    "chats of a missing account": "select id from tg_chat where account_id not in (select id from tg_account)",
    "runs of a missing account": "select id from tg_run where account_id not in (select id from tg_account)",
    "runs of a missing workflow": "select id from tg_run where workflow_id is not null"
                                  " and workflow_id not in (select id from tg_workflow)",
    "run chats of a missing run": "select id from tg_run_chat where run_id not in (select id from tg_run)",
    "run chats of a missing chat": "select id from tg_run_chat where chat_id not in (select id from tg_chat)",
}


def assert_no_orphans(app):
    with sqlite3.connect(app.storage / "db.sqlite") as c:
        for what, sql in ORPHAN_QUERIES.items():
            assert c.execute(sql).fetchall() == [], f"orphan rows: {what}"
        assert c.execute("pragma foreign_key_check").fetchall() == [], "foreign key violations"


def count(app, table, where="1", *args):
    return db(app, f"select count(*) from {table} where {where}", *args)[0][0]


def wait_run(api, run_id, status="done", timeout=60):
    return wait_until(lambda: (r := run(api, run_id))["status"] == status and r, timeout=timeout,
                      msg=f"run {run_id} to be {status}")


def finished_run(api, acc, name, tids, wf=None):
    """A run over the given Telegram ids that ran to the end."""
    wf = wf or make_workflow(api, [text_step("hi")], name=name)
    r = start(api, acc, wf, chat_ids(api, acc, *tids))
    wait_run(api, r["id"])
    return wf, r["id"]


def rss_mb(pid):
    """Resident memory of a process in MB (no psutil here)."""
    if sys.platform == "win32":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
        return int(re.sub(r"\D", "", out.strip().splitlines()[0].split('","')[-1])) / 1024
    with open(f"/proc/{pid}/status") as f:
        return int(re.search(r"VmRSS:\s+(\d+)", f.read()).group(1)) / 1024


def timed(api, path, **params):
    t = time.perf_counter()
    r = api.get(f"{T}{path}", params=params)
    return r, time.perf_counter() - t


def insert_chats(app, account_id, n, first=0, status=lambda i: "pending", access_hash="777"):
    """n chats straight into the database (fast): 'Kunde i', every 100th 'Müller i'; each i minutes older than BASE."""
    rows = []
    for i in range(first, first + n):
        name = f"Müller {i}" if i % 100 == 0 else f"Kunde {i}"
        stamp = (BASE - timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S.%f")
        rows.append((account_id, str(10 ** 9 + i), access_hash, f"{name} u{i} {10 ** 9 + i}".casefold(), f"u{i}", name,
                     stamp, stamp, f"msg {i}", status(i), 0, "", "", stamp))
    with sqlite3.connect(app.storage / "db.sqlite") as c:
        c.executemany("insert into tg_chat (account_id, telegram_id, access_hash, search_text, username, display_name,"
                      " first_contact_at, last_contact_at, last_message, chat_status, messages_sent, error_reason,"
                      " notes, created_at) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)


def clone_runs(app, run_id, n, age_days=lambda i: 0):
    """n copies of a run (and its per-chat results) as history, the i-th one finished age_days(i) days ago."""
    with sqlite3.connect(app.storage / "db.sqlite") as c:
        c.row_factory = sqlite3.Row
        src = dict(c.execute("select * from tg_run where id=?", (run_id,)).fetchone())
        rcs = [dict(r) for r in c.execute("select * from tg_run_chat where run_id=?", (run_id,))]
        for i in range(n):
            when = (datetime.now(timezone.utc) - timedelta(days=age_days(i), seconds=n - i)).strftime("%Y-%m-%d %H:%M:%S.%f")
            row = {**src, "created_at": when, "started_at": when, "finished_at": when}
            row.pop("id")
            new = c.execute(f"insert into tg_run ({','.join(row)}) values ({','.join('?' * len(row))})",
                            list(row.values())).lastrowid
            for rc in rcs:
                rc = {**rc, "run_id": new}
                rc.pop("id")
                c.execute(f"insert into tg_run_chat ({','.join(rc)}) values ({','.join('?' * len(rc))})", list(rc.values()))


# --- (1) deleting leaves no orphans ----------------------------------------------------------------------

def two_accounts_with_history(rig, scn):
    app, api, _ = rig
    scn.dialogs([dlg(i) for i in range(1, 5)])
    a = link_synced(api)
    b = link_synced(api, PHONE_B)
    wf_a, run_a = finished_run(api, a, "FlowA", [1001, 1002, 1003])
    wf_b, run_b = finished_run(api, b, "FlowB", [1001, 1002], wf=wf_a)      # the workflow is shared
    return app, api, a, b, wf_a, run_a, run_b


def test_deleting_an_account_removes_its_chats_runs_and_results_but_nothing_else(rig, scn):
    app, api, a, b, wf, run_a, run_b = two_accounts_with_history(rig, scn)
    assert count(app, "tg_chat") == 8 and count(app, "tg_run_chat") == 5
    ok(api.delete(f"{T}/accounts/{a['id']}"))
    assert_no_orphans(app)
    assert count(app, "tg_chat", "account_id=?", a["id"]) == 0 and count(app, "tg_run", "account_id=?", a["id"]) == 0
    assert db(app, "select id from tg_run") == [(run_b,)] and count(app, "tg_run_chat") == 2
    assert count(app, "tg_chat") == 4 and count(app, "tg_workflow") == 1       # workflows are not owned by an account
    assert run(api, run_b)["success"] == 2 and len(chats(api, account_id=b["id"])["items"]) == 4
    assert api.get(f"{T}/runs/{run_a}").status_code == 404
    assert ok(api.get(f"{T}/stats"))["runs"] == 1
    # the deleted account's chats are gone from every list, summary and id list
    assert ok(api.get(f"{T}/chats/summary"))["total"] == 4 and ok(api.get(f"{T}/chats/ids"))["total"] == 4
    ok(api.delete(f"{T}/accounts/{b['id']}"))
    assert_no_orphans(app)
    assert count(app, "tg_chat") == count(app, "tg_run") == count(app, "tg_run_chat") == 0


def test_deleting_the_last_account_then_linking_it_again_starts_clean(rig, scn):
    app, api, a, b, wf, run_a, run_b = two_accounts_with_history(rig, scn)
    ok(api.delete(f"{T}/accounts/{a['id']}"))
    again = link_synced(api)
    assert again["id"] != a["id"]                 # ids are not reused for a different row's data
    items = chats(api, account_id=again["id"])["items"]
    assert len(items) == 4 and all(c["messages_sent"] == 0 and c["chat_status"] == "pending" for c in items)
    assert ok(api.get(f"{T}/runs", params={"account_id": again["id"]}))["total"] == 0
    assert_no_orphans(app)


def test_an_account_with_an_active_run_cannot_be_deleted_not_even_when_paused(rig, scn):
    app, api, _ = rig
    scn.dialogs([dlg(i) for i in range(1, 4)])
    acc = link_synced(api)
    wf = make_workflow(api, [text_step("a", 30), text_step("b")])
    r = start(api, acc, wf, chat_ids(api, acc, 1001, 1002))
    wait_until(lambda: outbox(scn), msg="the first message")
    for paused in (False, True):
        if paused:
            ok(api.post(f"{T}/runs/{r['id']}/pause"))                   # a paused run is still active
        assert api.delete(f"{T}/accounts/{acc['id']}").status_code == 409
        assert api.delete(f"{T}/workflows/{wf['id']}").status_code == 409
        assert api.delete(f"{T}/runs/{r['id']}").status_code == 409
    assert count(app, "tg_chat") == 3 and count(app, "tg_run") == 1 and count(app, "tg_workflow") == 1
    ok(api.post(f"{T}/runs/{r['id']}/stop"))
    ok(api.delete(f"{T}/accounts/{acc['id']}"))
    assert_no_orphans(app)
    assert count(app, "tg_run") == count(app, "tg_run_chat") == count(app, "tg_chat") == 0


def test_deleting_a_workflow_keeps_finished_runs_with_name_and_snapshot(rig, scn):
    app, api, a, b, wf, run_a, run_b = two_accounts_with_history(rig, scn)
    ok(api.delete(f"{T}/workflows/{wf['id']}"))
    assert_no_orphans(app)
    for rid in (run_a, run_b):
        r = run(api, rid)
        assert r["workflow_id"] is None and r["workflow_name"] == "FlowA" and r["status"] == "done" and r["success"] > 0
    assert count(app, "tg_run") == 2 and count(app, "tg_run_chat") == 5
    snap = json.loads(db(app, "select workflow_snapshot from tg_run where id=?", run_a)[0][0])
    assert snap["steps"][0]["content"] == "hi"
    assert ok(api.get(f"{T}/runs/{run_a}/chats"))["total"] == 3
    # such a run can be repeated from its snapshot
    again = ok(api.post(f"{T}/runs/{run_a}/restart"))
    assert again["workflow_id"] is None and again["workflow_name"] == "FlowA"
    wait_run(api, again["id"])
    assert ok(api.get(f"{T}/runs", params={"workflow_id": wf["id"]}))["total"] == 0
    ok(api.get(f"{T}/runs/export.csv"))
    assert_no_orphans(app)


def test_deleting_a_run_removes_only_its_own_results(rig, scn):
    app, api, a, b, wf, run_a, run_b = two_accounts_with_history(rig, scn)
    _, run_a2 = finished_run(api, a, "FlowA2", [1001, 1002], wf=wf)
    before = chats(api, account_id=a["id"])["items"]
    ok(api.delete(f"{T}/runs/{run_a}"))
    assert_no_orphans(app)
    assert count(app, "tg_run_chat", "run_id=?", run_a) == 0
    assert count(app, "tg_run_chat", "run_id=?", run_a2) == 2 and count(app, "tg_run_chat", "run_id=?", run_b) == 2
    assert chats(api, account_id=a["id"])["items"] == before             # the chats keep status and message counts
    assert api.delete(f"{T}/runs/{run_a}").status_code == 404
    assert api.get(f"{T}/runs/{run_a}/chats").status_code == 404


def test_history_cleanup_removes_old_finished_runs_with_results_and_spares_the_rest(rig, scn):
    app, api, a, b, wf, run_a, run_b = two_accounts_with_history(rig, scn)
    clone_runs(app, run_a, 6, age_days=lambda i: 60 if i < 3 else 1)
    slow = make_workflow(api, [text_step("a", 30), text_step("b")], name="Slow")
    active = start(api, b, slow, chat_ids(api, b, 1003))
    wait_until(lambda: outbox(scn, PHONE_B), msg="the active run to send")
    db(app, "update tg_run set created_at='2020-01-01 00:00:00.000000' where id=?", active["id"])     # old, but active
    assert ok(api.post(f"{T}/runs/cleanup", json={"days": 30})) == {"deleted": 3}
    assert_no_orphans(app)
    assert count(app, "tg_run") == 2 + 3 + 1 and count(app, "tg_run", "id=?", active["id"]) == 1
    assert count(app, "tg_run_chat") == 3 + 2 + 3 * 3 + 1
    assert count(app, "tg_chat") == 8
    ok(api.post(f"{T}/runs/{active['id']}/stop"))


def test_deleting_an_account_while_its_chat_sync_runs_leaves_nothing_behind(make_app, scn):
    scn.dialogs([dlg(i) for i in range(1, 301)])
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir), FAKE_TG_DIALOG_DELAY="0.02")
    api = app.client()
    acc = link(api)
    wait_until(lambda: accounts(api)[PHONE]["sync"], msg="the sync to start")
    wait_until(lambda: accounts(api)[PHONE]["sync"] is None or accounts(api)[PHONE]["sync"]["imported"] >= 100, msg="a first batch")
    ok(api.delete(f"{T}/accounts/{acc['id']}"))
    time.sleep(2.5)         # a sync task that survived would keep writing chats now
    assert count(app, "tg_chat") == 0 and count(app, "tg_account") == 0
    assert_no_orphans(app)
    assert ok(api.get(f"{T}/status"))["chats"] == 0


def test_deleting_an_account_with_many_runs_and_chats(rig, scn):
    app, api, _ = rig
    acc = link_synced(api)
    insert_chats(app, acc["id"], 3000)
    first = chat_ids(api, acc, 10 ** 9, 10 ** 9 + 1)
    wf = make_workflow(api, [text_step("hi")])
    r = start(api, acc, wf, first)
    wait_run(api, r["id"])
    clone_runs(app, r["id"], 1500)
    assert count(app, "tg_run") == 1501
    t = time.perf_counter()
    ok(api.delete(f"{T}/accounts/{acc['id']}"))
    assert time.perf_counter() - t < 30
    assert_no_orphans(app)
    assert count(app, "tg_run") == count(app, "tg_run_chat") == count(app, "tg_chat") == 0


# --- (2) duplicates across repeated syncs ----------------------------------------------------------------

def test_repeated_syncs_never_duplicate_chats_and_keep_their_ids(rig, scn):
    app, api, _ = rig
    scn.dialogs([dlg(i, i) for i in range(1, 251)])
    acc = link_synced(api)
    before = {c["telegram_id"]: c["id"] for c in chats(api, account_id=acc["id"])["items"]}
    assert len(before) == 250
    for _ in range(3):
        assert ok(api.post(f"{T}/accounts/{acc['id']}/sync-chats"))["running"]
        wait_sync(api)
    after = {c["telegram_id"]: c["id"] for c in chats(api, account_id=acc["id"])["items"]}
    assert after == before                                              # the same rows, so run history links stay valid
    assert db(app, "select count(*), count(distinct telegram_id) from tg_chat") == [(250, 250)]
    assert accounts(api)[PHONE]["chats"] == 250


def test_the_same_dialog_twice_in_one_sync_makes_one_chat(rig, scn):
    app, api, _ = rig
    items = [dlg(i, i) for i in range(1, 151)]
    items.append(dlg(1, 0, first_name="Renamed", last_message="newest"))     # the same user again, past a batch boundary
    items.insert(5, dlg(120, 3))
    scn.dialogs(items)
    link_synced(api)
    assert db(app, "select count(*), count(distinct telegram_id) from tg_chat") == [(150, 150)]
    one = next(c for c in chats(api)["items"] if c["telegram_id"] == "1001")
    assert one["last_message"] in ("newest", "hello 1")


def test_the_same_contact_on_two_accounts_is_two_separate_chats(rig, scn):
    app, api, _ = rig
    scn.dialogs([dlg(i) for i in range(1, 4)])
    a, b = link_synced(api), link_synced(api, PHONE_B)
    assert db(app, "select count(*), count(distinct telegram_id) from tg_chat") == [(6, 3)]
    ids_a = {c["id"] for c in chats(api, account_id=a["id"])["items"]}
    ids_b = {c["id"] for c in chats(api, account_id=b["id"])["items"]}
    assert len(ids_a) == len(ids_b) == 3 and not ids_a & ids_b
    ok(api.patch(f"{T}/chats/{next(iter(ids_a))}", json={"chat_status": "done", "notes": "mine"}))
    assert ok(api.get(f"{T}/chats/summary", params={"account_id": b["id"]}))["by_status"]["done"] == 0
    assert chats(api)["total"] == 6


def test_a_live_message_from_a_synced_contact_updates_the_chat_instead_of_adding_one(rig, scn):
    app, api, _ = rig
    scn.dialogs([dlg(1, 5, first_name="Anna", username="anna")])
    acc = link_synced(api)
    cid = chats(api)["items"][0]["id"]
    ok(api.patch(f"{T}/chats/{cid}", json={"notes": "keep me", "chat_status": "done"}))
    scn.incoming(id=1001, access_hash=5001, first_name="Anna", last_name="Neu", username="anna_neu", text="again",
                 date=BASE.isoformat())
    wait_until(lambda: chats(api)["items"][0]["last_message"] == "again", msg="the live message")
    # an old message that arrives late must not move the last contact backwards
    scn.incoming(id=1001, access_hash=5001, first_name="Anna", last_name="Neu", username="anna_neu", text="ancient",
                 date=(BASE - timedelta(days=90)).isoformat())
    time.sleep(1.0)
    got = chats(api)
    assert got["total"] == 1 and got["items"][0]["id"] == cid
    c = got["items"][0]
    assert c["last_message"] == "again" and c["notes"] == "keep me" and c["chat_status"] == "done"
    assert c["display_name"] == "Anna Neu" and c["username"] == "anna_neu"
    assert c["first_contact_at"].startswith("2026-01-") or c["first_contact_at"] < c["last_contact_at"]
    assert count(app, "tg_chat") == 1


def test_live_messages_during_a_slow_sync_do_not_create_duplicates(make_app, scn):
    scn.dialogs([dlg(i) for i in range(1, 121)])
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir), FAKE_TG_DIALOG_DELAY="0.02")
    api = app.client()
    link(api)
    wait_until(lambda: accounts(api)[PHONE]["sync"], msg="the sync to start")
    for i in (5, 60, 110, 119):           # contacts the sync has not imported yet (or just did)
        scn.incoming(id=1000 + i, access_hash=5000 + i, first_name=f"User{i}", username=f"user{i}", text="live",
                     date=BASE.isoformat())
        time.sleep(0.4)
    wait_sync(api)
    time.sleep(0.5)
    assert db(app, "select count(*), count(distinct telegram_id) from tg_chat") == [(120, 120)]


def test_a_renamed_contact_is_found_under_the_new_name_after_a_resync(rig, scn):
    app, api, _ = rig
    scn.dialogs([dlg(1, first_name="Anna", username="anna_old")])
    acc = link_synced(api)
    assert chats(api, q="anna_old")["total"] == 1
    scn.dialogs([dlg(1, first_name="Bärbel", username="baerbel_new")])
    ok(api.post(f"{T}/accounts/{acc['id']}/sync-chats"))
    wait_sync(api)
    assert chats(api, q="anna_old")["total"] == 0 and chats(api, q="Anna")["total"] == 0
    assert chats(api, q="BÄRBEL")["total"] == 1 and chats(api, q="@baerbel_new")["total"] == 1 and chats(api)["total"] == 1


# --- (3) a database with older tg_ tables ----------------------------------------------------------------

OLD_COLUMNS = {
    "tg_account": ["auto_connect", "tg_username", "last_connected_at", "tg_user_id"],
    "tg_chat": ["access_hash", "search_text", "notes", "error_reason", "first_contact_at"],
    "tg_run": ["retries", "wait_kind", "status_msg", "auto_resume", "peer_floods", "on_error", "current_step_index",
               "paused_at"],
}


def downgrade(app):
    """Make the tg_ tables look like an older release's: drop the newest columns."""
    with sqlite3.connect(app.storage / "db.sqlite") as c:
        for table, cols in OLD_COLUMNS.items():
            for col in cols:
                c.execute(f'alter table {table} drop column "{col}"')


def test_the_app_starts_on_older_tg_tables_and_old_data_keeps_working(make_app, scn):
    scn.dialogs([dlg(i, i, first_name=f"Anna{i}") for i in range(1, 4)])
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir))
    api = app.client()
    acc = link_synced(api)
    wf, run_id = finished_run(api, acc, "Old", [1001, 1002])
    ok(api.patch(f"{T}/chats/{chat_ids(api, acc, 1003)[0]}", json={"chat_status": "paused"}))
    app.stop()
    downgrade(app)
    names = {t: {r[1] for r in db(app, f'pragma table_info("{t}")')} for t in OLD_COLUMNS}
    assert not names["tg_chat"] & {"access_hash", "search_text"}
    scn.dialogs([])                                        # nothing to refresh the chats from yet
    app2 = make_app(storage=app.storage, **ENV, FAKE_TG_DIR=str(scn.dir))
    api2 = app2.client()
    for table, cols in OLD_COLUMNS.items():
        have = {r[1] for r in db(app2, f'pragma table_info("{table}")')}
        assert set(cols) <= have, f"{table}: columns not re-added"
    a = wait_until(lambda: (x := accounts(api2)[PHONE])["status"] == "online" and x, msg="account to reconnect")
    assert a["chats"] == 3
    r = run(api2, run_id)
    assert (r["status"], r["success"], r["retries"], r["on_error"], r["peer_floods"], r["auto_resume"]) == \
           ("done", 2, 3, "next", 0, False)
    assert ok(api2.get(f"{T}/runs"))["total"] == 1 and len(ok(api2.get(f"{T}/runs/{run_id}/chats"))["items"]) == 2
    ok(api2.get(f"{T}/runs/export.csv")), ok(api2.get(f"{T}/runs/{run_id}/export.csv"))
    st = ok(api2.get(f"{T}/stats"))
    assert st["chats"]["total"] == 3 and st["sends"]["successful"] == 2 and st["last_run"]["id"] == run_id
    items = chats(api2)["items"]
    assert len(items) == 3 and all(c["notes"] == "" and c["error_reason"] == "" for c in items)
    assert {c["chat_status"] for c in items} == {"done", "paused"} and ok(api2.get(f"{T}/status"))["chats"] == 3
    assert_no_orphans(app2)


def test_chats_stored_before_the_search_column_existed_are_found_by_the_search(make_app, scn):
    scn.dialogs([dlg(i, i, first_name=f"Anna{i}") for i in range(1, 4)])
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir))
    link_synced(app.client())
    app.stop()
    downgrade(app)
    scn.dialogs([])
    api = make_app(storage=app.storage, **ENV, FAKE_TG_DIR=str(scn.dir)).client()
    assert chats(api, q="anna2")["total"] == 1
    assert chats(api, q="1003")["total"] == 1
    assert [c["display_name"] for c in chats(api, sort="display_name", order="asc")["items"]] == ["Anna1", "Anna2", "Anna3"]


def test_old_chats_without_an_access_key_fail_cleanly_and_a_sync_repairs_them(make_app, scn):
    scn.dialogs([dlg(i, i, first_name=f"Anna{i}") for i in range(1, 4)])
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir))
    api = app.client()
    link_synced(api)
    app.stop()
    downgrade(app)
    scn.dialogs([])
    app2 = make_app(storage=app.storage, **ENV, FAKE_TG_DIR=str(scn.dir))
    api2 = app2.client()
    acc = wait_until(lambda: (x := accounts(api2)[PHONE])["status"] == "online" and x, msg="account to reconnect")
    wf = make_workflow(api2, [text_step("hi")])
    r = start(api2, acc, wf, chat_ids(api2, acc, 1001, 1002))
    done = wait_run(api2, r["id"])
    assert (done["errors"], done["success"], done["processed"]) == (2, 0, 2)
    assert outbox(scn) == []
    assert all("access key" in c["error_reason"] for c in chats(api2)["items"] if c["telegram_id"] in ("1001", "1002"))
    scn.dialogs([dlg(i, i, first_name=f"Anna{i}") for i in range(1, 4)])
    ok(api2.post(f"{T}/accounts/{acc['id']}/sync-chats"))
    wait_sync(api2)
    assert chats(api2, q="anna3")["total"] == 1 and count(app2, "tg_chat") == 3          # repaired in place, no copies
    again = ok(api2.post(f"{T}/runs/{r['id']}/restart"))
    final = wait_run(api2, again["id"])
    assert (final["success"], final["errors"]) == (2, 0) and len(outbox(scn)) == 2


def test_migrating_twice_is_harmless(make_app, scn):
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir))
    api = app.client()
    link(api)
    app.stop()
    downgrade(app)
    app2 = make_app(storage=app.storage, **ENV, FAKE_TG_DIR=str(scn.dir))
    app2.stop()
    app3 = make_app(storage=app.storage, **ENV, FAKE_TG_DIR=str(scn.dir))
    assert ok(app3.client().get(f"{T}/status"))["accounts"] == 1


# --- (4) scale -------------------------------------------------------------------------------------------

@pytest.fixture
def big(rig, scn):
    app, api, _ = rig
    acc = link_synced(api)
    insert_chats(app, acc["id"], 10000, status=lambda i: ("pending", "done", "error", "paused", "in_progress")[i % 5])
    other = link_synced(api, PHONE_B)
    insert_chats(app, other["id"], 300, first=20000)
    return app, api, acc, other


def test_importing_ten_thousand_dialogs(rig, scn):
    app, api, _ = rig
    scn.dialogs([dlg(i, i % 400) for i in range(1, 10001)])
    t = time.perf_counter()
    acc = link(api)
    wait_until(lambda: accounts(api)[PHONE]["sync"] is None and accounts(api)[PHONE]["chats"] == 10000, timeout=120,
               msg="10,000 chats to be imported")
    took = time.perf_counter() - t
    assert took < 90, f"import took {took:.1f} s"
    assert db(app, "select count(*), count(distinct telegram_id) from tg_chat") == [(10000, 10000)]
    assert chats(api, limit=1)["total"] == 10000
    # panel stays usable while a re-import runs, and a re-import adds nothing
    ok(api.post(f"{T}/accounts/{acc['id']}/sync-chats"))
    t0 = time.perf_counter()
    while accounts(api)[PHONE]["sync"] is not None:
        _, dt = timed(api, "/chats", limit=50)
        assert dt < 3
        time.sleep(0.1)
        assert time.perf_counter() - t0 < 120
    assert count(app, "tg_chat") == 10000


def test_listing_searching_sorting_and_paging_ten_thousand_chats(big):
    app, api, acc, other = big
    aid = acc["id"]
    r, dt = timed(api, "/chats", account_id=aid)
    assert r.status_code == 200 and r.json()["total"] == 10000 and len(r.json()["items"]) == 100 and dt < 2, dt
    assert chats(api)["total"] == 10300
    # every sort key, both orders: paging walks all rows exactly once, also over many equal sort values
    for sort in ("id", "last_contact_at", "first_contact_at", "display_name", "chat_status", "messages_sent"):
        for order in ("asc", "desc"):
            seen = []
            t = time.perf_counter()
            for offset in range(0, 10000, 1000):
                seen += [c["id"] for c in chats(api, account_id=aid, sort=sort, order=order, offset=offset)["items"]]
            assert len(seen) == len(set(seen)) == 10000, (sort, order, len(seen), len(set(seen)))
            assert time.perf_counter() - t < 20, (sort, order)
    deep, dt = timed(api, "/chats", account_id=aid, offset=9950, limit=100, sort="display_name")
    assert len(deep.json()["items"]) == 50 and dt < 2
    assert chats(api, account_id=aid, offset=10000)["items"] == []
    first = chats(api, account_id=aid, sort="last_contact_at", order="desc", limit=3)["items"]
    assert [c["telegram_id"] for c in first] == [str(10 ** 9 + i) for i in range(3)]          # newest contact first
    # search: case-insensitive, umlauts, @username, id fragments, % and _ are literal
    for q, n in (("müller", 100), ("MÜLLER 4200", 1), ("@u7777", 1), ("1000009999", 1), ("kunde 99", 110),
                 ("  Kunde  ", 9900), ("nobody", 0)):
        r, dt = timed(api, "/chats", account_id=aid, q=q)
        assert r.status_code == 200 and r.json()["total"] == n and dt < 2, (q, r.json()["total"], dt)
    with sqlite3.connect(app.storage / "db.sqlite") as c:
        c.execute("update tg_chat set display_name='100% Fan', search_text='100% fan u1 1000000001' where telegram_id=?",
                  (str(10 ** 9 + 1),))
        c.execute("update tg_chat set display_name='a_b', search_text='a_b u2 1000000002' where telegram_id=?",
                  (str(10 ** 9 + 2),))
    assert [c["telegram_id"] for c in chats(api, account_id=aid, q="%")["items"]] == [str(10 ** 9 + 1)]
    assert [c["telegram_id"] for c in chats(api, account_id=aid, q="_")["items"]] == [str(10 ** 9 + 2)]
    # filters: status (one and several), dates, and combined with search and paging
    assert chats(api, account_id=aid, status="done")["total"] == 2000
    assert chats(api, account_id=aid, status="done,error", limit=1)["total"] == 4000
    assert chats(api, account_id=aid, status="pending", q="müller")["total"] == 100
    assert api.get(f"{T}/chats", params={"status": "nonsense"}).status_code == 422
    day = (BASE - timedelta(days=1)).date().isoformat()
    assert chats(api, account_id=aid, date_from=day, date_to=day, limit=1)["total"] == 1440     # one contact per minute
    assert chats(api, account_id=aid, date_to=day, limit=1)["total"] + \
           chats(api, account_id=aid, date_from=(BASE.date()).isoformat(), limit=1)["total"] == 10000
    assert api.get(f"{T}/chats", params={"limit": 1001}).status_code == 422


def test_chat_ids_and_bulk_actions_on_ten_thousand_chats(big):
    app, api, acc, other = big
    aid = acc["id"]
    r, dt = timed(api, "/chats/ids", account_id=aid)
    ids = r.json()["ids"]
    assert r.status_code == 200 and r.json()["total"] == len(ids) == len(set(ids)) == 10000 and dt < 3, dt
    assert ids == sorted(ids)
    done = ok(api.get(f"{T}/chats/ids", params={"account_id": aid, "status": "done", "q": "kunde"}))
    assert done["total"] == len(done["ids"]) == 2000
    assert ok(api.get(f"{T}/chats/ids", params={"q": "zzz"})) == {"total": 0, "ids": []}
    assert {i for i in ids} & {i for i in ok(api.get(f"{T}/chats/ids", params={"account_id": other["id"]}))["ids"]} == set()
    r, dt = timed(api, "/chats/summary", account_id=aid)
    assert r.json() == {"total": 10000, "by_status": {"pending": 2000, "in_progress": 2000, "done": 2000, "error": 2000,
                                                      "paused": 2000}} and dt < 1.5
    t = time.perf_counter()
    res = ok(api.post(f"{T}/chats/bulk-status", json={"ids": ids, "status": "pending"}))
    assert res["updated"] == 10000 and time.perf_counter() - t < 15
    assert ok(api.get(f"{T}/chats/summary", params={"account_id": aid}))["by_status"]["pending"] == 10000
    assert ok(api.get(f"{T}/chats/summary", params={"account_id": other["id"]}))["total"] == 300
    assert count(app, "tg_chat", "chat_status='error' and error_reason!=''") == 0
    assert ok(api.post(f"{T}/chats/bulk-status", json={"ids": ids + [10 ** 9], "status": "done"}))["updated"] == 10000
    st, dt = timed(api, "/stats", account_id=aid)
    assert st.json()["chats"]["processed"] == 10000 and dt < 2


def test_a_run_over_ten_thousand_chats_is_created_and_stopped_cleanly(big):
    app, api, acc, other = big
    ids = ok(api.get(f"{T}/chats/ids", params={"account_id": acc["id"]}))["ids"]
    wf = make_workflow(api, [text_step("hi", 5)])
    t = time.perf_counter()
    r = start(api, acc, wf, ids)
    assert time.perf_counter() - t < 20 and r["total"] == 10000
    assert count(app, "tg_run_chat", "run_id=?", r["id"]) == 10000
    stopped = ok(api.post(f"{T}/runs/{r['id']}/stop"))
    assert stopped["status"] == "stopped" and stopped["processed"] + stopped["skipped"] == 10000
    left = dict(db(app, "select status, count(*) from tg_run_chat where run_id=? group by status", r["id"]))
    assert left.get("pending", 0) == left.get("running", 0) == 0 and left.get("skipped", 0) + left.get("done", 0) \
           + left.get("error", 0) == 10000
    assert count(app, "tg_chat", "chat_status in ('in_progress')") == 2000          # only the untouched rows (as inserted)
    assert api.post(f"{T}/runs", json={"account_id": acc["id"], "workflow_id": wf["id"], "chat_ids": ids[:3] + [10 ** 9]}) \
        .status_code == 422
    assert_no_orphans(app)


def test_a_thousand_chat_run_with_no_pauses_finishes_with_exact_counters_and_bounded_memory(rig, scn):
    app, api, _ = rig
    acc = link_synced(api)
    insert_chats(app, acc["id"], 1000)
    scn_errors = {str(10 ** 9 + i): {"error": "UserPrivacyRestrictedError"} for i in range(0, 1000, 10)}
    (scn.dir / "send_errors.json").write_text(json.dumps(scn_errors), encoding="utf-8")
    wf = make_workflow(api, [text_step("one", 0), text_step("two", 0), text_step("three", 0)])
    ids = ok(api.get(f"{T}/chats/ids", params={"account_id": acc["id"]}))["ids"]
    mem0 = rss_mb(app.proc.pid)
    peak = mem0
    r = start(api, acc, wf, ids)
    t0 = time.time()
    last = -1
    while True:
        cur = run(api, r["id"])
        assert cur["processed"] >= last and cur["success"] + cur["errors"] == cur["processed"] <= 1000, cur   # never goes back
        last = cur["processed"]
        peak = max(peak, rss_mb(app.proc.pid))
        if cur["status"] != "running":
            break
        assert time.time() - t0 < 240, f"stuck at {cur['processed']}"
        time.sleep(0.5)
    final = run(api, r["id"])
    took = time.time() - t0
    assert final["status"] == "done", final
    assert (final["total"], final["processed"], final["success"], final["errors"], final["percent"]) == (1000, 1000, 900, 100, 100)
    assert took < 200, took
    assert peak - mem0 < 150, f"memory grew from {mem0:.0f} to {peak:.0f} MB"
    assert dict(db(app, "select status, count(*) from tg_run_chat where run_id=? group by status", r["id"])) == \
           {"done": 900, "error": 100}
    assert dict(db(app, "select chat_status, count(*) from tg_chat group by chat_status")) == {"done": 900, "error": 100}
    assert db(app, "select min(messages_sent), max(messages_sent) from tg_chat where chat_status='done'") == [(3, 3)]
    assert db(app, "select sum(messages_sent) from tg_chat") == [(2700,)]
    sent = outbox(scn)
    assert len(sent) == 2700                                       # 900 chats x 3 steps; the 100 failing chats sent nothing
    order = [m["chat_id"] for m in sent if m["content"] == "one"]
    assert order == [10 ** 9 + i for i in range(1000) if i % 10]   # the chats in the order given, none twice, none lost
    assert all(c["error_reason"].startswith("The user's privacy") for c in chats(api, status="error")["items"])
    assert ok(api.get(f"{T}/stats"))["sends"] == {"successful": 900, "failed": 100, "messages": 2700}
    assert ok(api.get(f"{T}/runs/{r['id']}/chats", params={"limit": 1000}))["total"] == 1000
    assert_no_orphans(app)


def test_a_history_of_five_hundred_runs_loads_quickly_and_pages_correctly(rig, scn):
    app, api, _ = rig
    scn.dialogs([dlg(i) for i in range(1, 4)])
    acc = link_synced(api)
    wf, run_id = finished_run(api, acc, "Hist", [1001, 1002, 1003])
    clone_runs(app, run_id, 499, age_days=lambda i: i // 10)
    db(app, "select 1")
    with sqlite3.connect(app.storage / "db.sqlite") as c:
        c.execute("update tg_run set status='error' where id % 7 = 0")
    r, dt = timed(api, "/runs")
    assert r.json()["total"] == 500 and len(r.json()["items"]) == 50 and dt < 2, dt
    r, dt = timed(api, "/runs", limit=500)
    items = r.json()["items"]
    assert len(items) == 500 and dt < 5, dt
    stamps = [i["created_at"] for i in items]
    assert stamps == sorted(stamps, reverse=True)
    paged = []
    for off in range(0, 500, 50):
        paged += [i["id"] for i in ok(api.get(f"{T}/runs", params={"offset": off}))["items"]]
    assert paged == [i["id"] for i in items] and len(set(paged)) == 500
    n_err = count(app, "tg_run", "status='error'")
    assert ok(api.get(f"{T}/runs", params={"status": "error", "limit": 1}))["total"] == n_err
    assert ok(api.get(f"{T}/runs", params={"status": "done,error", "limit": 1}))["total"] == 500
    week = (datetime.now(timezone.utc) - timedelta(days=20)).date().isoformat()
    assert 0 < ok(api.get(f"{T}/runs", params={"date_from": week, "limit": 1}))["total"] < 500
    t = time.perf_counter()
    csv_text = ok(api.get(f"{T}/runs/export.csv"))
    assert time.perf_counter() - t < 8 and len(csv_text.strip().splitlines()) == 501
    for path, kw in (("/stats", {}), ("/status", {}), ("/runs/%d/chats" % items[-1]["id"], {})):
        r, dt = timed(api, path, **kw)
        assert r.status_code == 200 and dt < 2, (path, dt)
    stats = ok(api.get(f"{T}/stats"))
    assert stats["runs"] == 500 and stats["sends"]["successful"] + stats["sends"]["failed"] >= 0
    assert ok(api.post(f"{T}/runs/cleanup", json={"days": 25}))["deleted"] > 0
    assert_no_orphans(app)


# --- (5) API calls while a run is active -------------------------------------------------------------------

def test_the_api_stays_responsive_and_consistent_during_a_busy_run_and_pause_resume_works(rig, scn):
    app, api, _ = rig
    acc = link_synced(api)
    insert_chats(app, acc["id"], 700)
    wf = make_workflow(api, [text_step("a", 0), text_step("b", 0)])
    ids = ok(api.get(f"{T}/chats/ids", params={"account_id": acc["id"]}))["ids"]
    r = start(api, acc, wf, ids)
    stop_flag, problems, slowest = threading.Event(), [], [0.0]

    def hammer(name, path, params):
        c = app.client()
        while not stop_flag.is_set():
            t = time.perf_counter()
            try:
                resp = c.get(f"{T}{path}", params=params)
            except Exception as e:  # noqa: BLE001
                problems.append((name, repr(e)))
                return
            dt = time.perf_counter() - t
            slowest[0] = max(slowest[0], dt)
            if resp.status_code != 200:
                problems.append((name, resp.status_code, resp.text[:200]))
                return
            body = resp.json()
            if name == "run" and not (body["success"] + body["errors"] == body["processed"] <= body["total"]):
                problems.append((name, "inconsistent", body))
            if name == "stats":
                ch = body["chats"]
                if ch["total"] != 700 or sum(ch[k] for k in ("unprocessed", "processed", "errors", "in_progress", "paused")) != 700:
                    problems.append((name, "chat totals", ch))
            if name == "chats" and (body["total"] != 700 or len(body["items"]) != 100):
                problems.append((name, "list", body["total"], len(body["items"])))
            if name == "summary" and body["total"] != 700:
                problems.append((name, "summary", body))
            time.sleep(0.02)

    threads = [threading.Thread(target=hammer, args=a, daemon=True) for a in (
        ("run", f"/runs/{r['id']}", {}), ("runs", "/runs", {}), ("stats", "/stats", {}),
        ("chats", "/chats", {"account_id": acc["id"], "q": "u", "status": "pending,in_progress,done,paused,error"}),
        ("summary", "/chats/summary", {}), ("accounts", "/accounts", {}))]
    for th in threads:
        th.start()
    wait_until(lambda: run(api, r["id"])["processed"] >= 30, timeout=60, msg="the run to get going")
    t = time.perf_counter()
    paused = ok(api.post(f"{T}/runs/{r['id']}/pause"))
    assert time.perf_counter() - t < 5
    assert paused["status"] == "paused"
    time.sleep(1.0)
    frozen = run(api, r["id"])
    time.sleep(1.5)
    assert run(api, r["id"])["processed"] == frozen["processed"] and frozen["status"] == "paused"   # really stopped
    assert 30 <= frozen["processed"] < 700
    assert count(app, "tg_chat", "chat_status='paused'") <= 1
    assert api.post(f"{T}/runs/{r['id']}/pause").status_code == 409
    back = ok(api.post(f"{T}/runs/{r['id']}/resume"))
    assert back["status"] == "running"
    wait_until(lambda: run(api, r["id"])["processed"] > frozen["processed"] + 20, timeout=60, msg="progress after resume")
    final_wait = wait_run(api, r["id"], timeout=240)
    stop_flag.set()
    for th in threads:
        th.join(10)
    assert problems == [], problems[:3]
    assert slowest[0] < 10, f"slowest request took {slowest[0]:.1f} s"
    assert (final_wait["processed"], final_wait["success"], final_wait["errors"]) == (700, 700, 0)
    assert len(outbox(scn)) == 1400 and len({(m["chat_id"], m["content"]) for m in outbox(scn)}) == 1400   # no step sent twice
    assert_no_orphans(app)


def test_stop_and_deletes_while_the_run_is_busy_leave_consistent_data(rig, scn):
    app, api, _ = rig
    acc = link_synced(api)
    insert_chats(app, acc["id"], 600)
    wf = make_workflow(api, [text_step("a", 0)])
    ids = ok(api.get(f"{T}/chats/ids", params={"account_id": acc["id"]}))["ids"]
    r = start(api, acc, wf, ids)
    wait_until(lambda: run(api, r["id"])["processed"] >= 10, msg="progress")
    # edits of chats and workflows during the run must not disturb it
    ok(api.patch(f"{T}/chats/{ids[-1]}", json={"notes": "edited while running"}))
    ok(api.put(f"{T}/workflows/{wf['id']}", json={"name": "Renamed", "steps": [text_step("different")]}))
    assert api.delete(f"{T}/workflows/{wf['id']}").status_code == 409
    stopped = ok(api.post(f"{T}/runs/{r['id']}/stop"))
    assert stopped["status"] == "stopped" and stopped["processed"] < 600
    assert stopped["processed"] + stopped["skipped"] == 600
    assert {m["content"] for m in outbox(scn)} == {"a"}
    states = dict(db(app, "select status, count(*) from tg_run_chat where run_id=? group by status", r["id"]))
    assert states.get("pending", 0) == states.get("running", 0) == 0
    assert states.get("done", 0) == stopped["success"] and len(outbox(scn)) == stopped["success"]
    assert db(app, "select notes from tg_chat where id=?", ids[-1]) == [("edited while running",)]
    ok(api.delete(f"{T}/workflows/{wf['id']}"))
    ok(api.delete(f"{T}/runs/{r['id']}"))
    assert_no_orphans(app)
