"""Telegram chat capture (import of existing dialogs, live incoming messages) and the /chats routes,
against the fake Telethon client and its FAKE_TG_DIR scenario folder (tests/fake_telegram.py)."""

import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from websockets.sync.client import connect

from conftest import ok, wait_until
from test_telegram_accounts import ENV, PHONE, accounts, link

BASE = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
OWN_ID = int(PHONE[1:])    # the fake account's own Telegram id


def dlg(i, days=0, **kw):
    """A private dialog; days = how long ago its last message was (relative to BASE)."""
    return {"id": 1000 + i, "access_hash": 5000 + i, "first_name": f"User{i}", "last_name": "", "username": f"user{i}",
            "last_message": f"hello {i}", "date": (BASE - timedelta(days=days)).isoformat(), **kw}


class Scenario:
    def __init__(self, folder):
        self.dir = folder
        folder.mkdir(exist_ok=True)

    def dialogs(self, items):
        (self.dir / "dialogs.json").write_text(json.dumps(items), encoding="utf-8")

    def incoming(self, **item):
        with open(self.dir / "inbox.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(item) + "\n")


@pytest.fixture
def scn(tmp_path):
    return Scenario(tmp_path / "fake_tg")


@pytest.fixture
def chats_app(make_app, scn):
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir))
    return app, app.client()


def wait_sync(api, phone=PHONE):
    """Wait until the account's background chat sync is over."""
    wait_until(lambda: accounts(api)[phone]["sync"] is None, msg="chat sync to finish")


def link_synced(api, phone=PHONE):
    acc = link(api, phone)
    wait_sync(api, phone)
    return acc


def chats(api, **params):
    return ok(api.get("/api/telegram/chats", params={"limit": 1000, **params}))


def db(app, sql, *args):
    with sqlite3.connect(app.storage / "db.sqlite") as c:
        return c.execute(sql, args).fetchall()


# --- import of existing dialogs ------------------------------------------------------------------

def test_sync_imports_private_users_only(chats_app, scn):
    app, api = chats_app
    scn.dialogs([
        dlg(1, 2, first_name="Anna", last_name="Meier", username="anna_m", last_message="Hallo!"),
        dlg(2, 1, username=None),
        dlg(3, 3, first_name="", username="nameless"),
        dlg(4, 1, bot=True), dlg(5, 1, deleted=True),
        dlg(6, 1, id=OWN_ID),                      # Saved Messages
        dlg(7, 1, id=777000),                      # Telegram's service chat
        dlg(8, 1, kind="group"),                   # a group is not a contact
    ])
    link_synced(api)
    got = {c["telegram_id"]: c for c in chats(api)["items"]}
    assert set(got) == {"1001", "1002", "1003"}
    anna = got["1001"]
    assert anna["display_name"] == "Anna Meier" and anna["username"] == "anna_m" and anna["last_message"] == "Hallo!"
    assert anna["chat_status"] == "pending" and anna["messages_sent"] == 0
    assert anna["last_contact_at"] == (BASE - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert anna["first_contact_at"] == anna["last_contact_at"]    # the earliest date we know without extra calls
    assert got["1002"]["display_name"] == "User2" and got["1003"]["display_name"] == "nameless"
    assert ok(api.get("/api/telegram/accounts"))[0]["chats"] == 3


def test_access_hash_is_stored_but_never_sent(chats_app, scn):
    app, api = chats_app
    scn.dialogs([dlg(1)])
    link_synced(api)
    assert db(app, "select access_hash from tg_chat") == [("5001",)]
    cid = chats(api)["items"][0]["id"]
    for payload in (chats(api)["items"][0], ok(api.get(f"/api/telegram/chats/{cid}"))):
        assert "access_hash" not in payload and "search_text" not in payload
    assert "5001" not in api.get("/api/telegram/chats").text


def test_resync_updates_telegram_data_but_keeps_the_operators_work(chats_app, scn):
    app, api = chats_app
    scn.dialogs([dlg(1, 5), dlg(2, 5)])
    acc = link_synced(api)
    first = chats(api)["items"]
    c1 = next(c for c in first if c["telegram_id"] == "1001")
    ok(api.patch(f"/api/telegram/chats/{c1['id']}", json={"chat_status": "done", "notes": "VIP"}))
    db(app, "update tg_chat set messages_sent=7 where id=?", c1["id"])
    scn.dialogs([dlg(1, 0, first_name="Renamed", username="new_name", last_message="newer", access_hash=9999),
                 dlg(2, 5, access_hash=None), dlg(3, 0)])
    assert ok(api.post(f"/api/telegram/accounts/{acc['id']}/sync-chats"))["running"]
    wait_sync(api)
    items = {c["telegram_id"]: c for c in chats(api)["items"]}
    assert set(items) == {"1001", "1002", "1003"}                   # no duplicates
    c = items["1001"]
    assert c["id"] == c1["id"] and c["chat_status"] == "done" and c["notes"] == "VIP" and c["messages_sent"] == 7
    assert c["display_name"] == "Renamed" and c["username"] == "new_name" and c["last_message"] == "newer"
    assert c["last_contact_at"] > c1["last_contact_at"] and c["first_contact_at"] == c1["first_contact_at"]
    # a dialog without an access hash does not erase the stored one
    assert db(app, "select access_hash from tg_chat order by telegram_id") == [("9999",), ("5002",), ("5003",)]


def test_older_dialog_data_does_not_overwrite_a_newer_live_message(chats_app, scn):
    _, api = chats_app
    scn.dialogs([dlg(1, 5)])
    acc = link_synced(api)
    scn.incoming(id=1001, access_hash=5001, first_name="User1", username="user1", text="live!",
                 date=BASE.isoformat())
    wait_until(lambda: chats(api)["items"][0]["last_message"] == "live!", msg="live message")
    ok(api.post(f"/api/telegram/accounts/{acc['id']}/sync-chats"))     # the dialog list still says "hello 1"
    wait_sync(api)
    assert chats(api)["items"][0]["last_message"] == "live!"


def test_sync_needs_an_online_account(chats_app, scn):
    _, api = chats_app
    acc = link_synced(api)
    ok(api.post(f"/api/telegram/accounts/{acc['id']}/disconnect"))
    r = api.post(f"/api/telegram/accounts/{acc['id']}/sync-chats")
    assert r.status_code == 409 and r.json()["detail"] == "This account is not online"
    assert api.post("/api/telegram/accounts/999/sync-chats").status_code == 404


def test_a_second_sync_is_refused_while_one_runs(make_app, scn):
    scn.dialogs([dlg(i) for i in range(1, 21)])
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir), FAKE_TG_DIALOG_DELAY="0.05")
    api = app.client()
    acc = link(api)          # starts the automatic sync (about a second long)
    again = ok(api.post(f"/api/telegram/accounts/{acc['id']}/sync-chats"))
    assert again == {"started": False, "running": True}
    assert accounts(api)[PHONE]["sync"] is not None
    wait_sync(api)
    assert len(chats(api)["items"]) == 20
    assert ok(api.post(f"/api/telegram/accounts/{acc['id']}/sync-chats"))["started"] is True    # free again
    wait_sync(api)
    assert len(chats(api)["items"]) == 20


def test_disconnect_stops_a_running_sync(make_app, scn):
    scn.dialogs([dlg(i) for i in range(1, 41)])
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir), FAKE_TG_DIALOG_DELAY="0.1")
    api = app.client()
    acc = link(api)
    ok(api.post(f"/api/telegram/accounts/{acc['id']}/disconnect"))
    assert accounts(api)[PHONE]["sync"] is None and accounts(api)[PHONE]["status"] == "offline"
    time.sleep(0.5)
    assert len(chats(api)["items"]) < 40
    ok(api.post(f"/api/telegram/accounts/{acc['id']}/connect"))    # connecting imports again
    assert accounts(api)[PHONE]["sync"] is not None


def test_floodwait_is_waited_out(chats_app, scn):
    _, api = chats_app
    scn.dialogs([dlg(i) for i in range(1, 6)])
    (scn.dir / "flood_once.txt").write_text("1")
    link_synced(api)
    assert len(chats(api)["items"]) == 5 and not (scn.dir / "flood_once.txt").exists()


def test_large_import_is_written_in_batches(chats_app, scn):
    _, api = chats_app
    scn.dialogs([dlg(i, i % 30) for i in range(1, 1301)])
    link_synced(api)
    assert chats(api, limit=1)["total"] == 1300
    assert len(ok(api.get("/api/telegram/chats/ids"))["ids"]) == 1300


# --- live incoming messages ---------------------------------------------------------------------

def test_incoming_message_creates_and_updates_a_chat(chats_app, scn):
    app, api = chats_app
    link_synced(api)
    assert chats(api)["total"] == 0
    scn.incoming(id=2001, access_hash=777, first_name="Bob", last_name="Builder", username="bob", text="first",
                 date=(BASE - timedelta(hours=2)).isoformat())
    wait_until(lambda: chats(api)["total"] == 1, msg="chat from the live message")
    c = chats(api)["items"][0]
    assert c["display_name"] == "Bob Builder" and c["last_message"] == "first" and c["chat_status"] == "pending"
    assert c["first_contact_at"] == c["last_contact_at"] == "2026-03-01T10:00:00Z"
    assert db(app, "select access_hash from tg_chat") == [("777",)]
    ok(api.patch(f"/api/telegram/chats/{c['id']}", json={"chat_status": "done"}))
    scn.incoming(id=2001, access_hash=777, first_name="Bob", last_name="Builder", username="bobby", text="second",
                 date=BASE.isoformat())
    wait_until(lambda: chats(api)["items"][0]["last_message"] == "second", msg="chat update")
    c2 = chats(api)["items"][0]
    assert chats(api)["total"] == 1 and c2["username"] == "bobby" and c2["id"] == c["id"]
    assert c2["first_contact_at"] == c["first_contact_at"] and c2["last_contact_at"] == "2026-03-01T12:00:00Z"
    assert c2["chat_status"] == "done"          # a new message never resets the operator's status


def test_incoming_messages_of_non_contacts_are_ignored(chats_app, scn):
    _, api = chats_app
    link_synced(api)
    scn.incoming(id=3001, first_name="Bot", bot=True, text="x")
    scn.incoming(id=3002, first_name="Gone", deleted=True, text="x")
    scn.incoming(id=777000, first_name="Telegram", text="Login code")
    scn.incoming(id=3003, first_name="Me", out=True, text="sent by the account itself")
    scn.incoming(id=OWN_ID, first_name="Self", text="saved message")
    scn.incoming(id=3004, first_name="Group", kind="group", text="x")
    scn.incoming(id=3005, first_name="Real", text="marker")
    wait_until(lambda: chats(api)["total"] == 1, msg="marker chat")
    assert chats(api)["items"][0]["telegram_id"] == "3005"


def test_chat_without_username_or_name_falls_back_to_the_id(chats_app, scn):
    _, api = chats_app
    link_synced(api)
    scn.incoming(id=3010, first_name="", username=None, text="")
    wait_until(lambda: chats(api)["total"] == 1, msg="chat")
    c = chats(api)["items"][0]
    assert c["display_name"] == "3010" and c["username"] == "" and c["last_message"] == ""


def test_messages_go_to_the_right_account(make_app, scn):
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir))
    api = app.client()
    link_synced(api)
    link_synced(api, "+4915100000003")
    scn.incoming(id=4001, first_name="OnlyFirst", text="hi", to=PHONE)
    wait_until(lambda: chats(api)["total"] == 1, msg="chat")
    by_phone = {a["phone"]: a for a in ok(api.get("/api/telegram/accounts"))}
    assert chats(api, account_id=by_phone[PHONE]["id"])["total"] == 1
    assert chats(api, account_id=by_phone["+4915100000003"]["id"])["total"] == 0


def test_live_events_reach_the_websocket(chats_app, scn):
    app, api = chats_app
    scn.dialogs([dlg(1), dlg(2)])
    (scn.dir / "flood_once.txt").write_text("1")
    cookie = {"Cookie": f"jb_session={api.cookies['jb_session']}"}
    seen = []
    ready = threading.Event()

    def reader():
        with connect(app.url.replace("http", "ws") + "/ws/modules/telegram", additional_headers=cookie,
                     open_timeout=10) as c:
            ready.set()
            while not any(m["type"] == "chat" for m in seen):
                try:
                    seen.append(json.loads(c.recv(timeout=8)))
                except Exception:
                    return

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    assert ready.wait(10)
    link(api)
    wait_sync(api)
    scn.incoming(id=5001, first_name="Live", text="hey")
    t.join(15)
    syncs = [m for m in seen if m["type"] == "sync"]
    assert [m["state"] for m in syncs if m["state"] != "running"] == ["waiting", "done"]
    assert syncs[-1]["imported"] == 2 and syncs[-1]["scanned"] == 2
    chat = next(m for m in seen if m["type"] == "chat")
    assert chat["new"] is True and chat["chat_id"]


# --- list, search, filter, sort, paging ------------------------------------------------------------

@pytest.fixture
def populated(chats_app, scn):
    """30 chats (user1..user30); user N last wrote N days before BASE. Names include umlauts."""
    items = [dlg(i, i) for i in range(1, 31)]
    items[0].update(first_name="Jürgen", last_name="Müller", username="jm")
    items[1].update(first_name="Ünal", username="ueber")
    items[2].update(first_name="100%_Sure", username="pct")
    scn.dialogs(items)
    app, api = chats_app
    link_synced(api)
    return app, api


def names(r):
    return [c["display_name"] for c in r["items"]]


def test_search_is_case_insensitive_over_name_username_and_id(populated):
    _, api = populated
    assert names(chats(api, q="JÜRGEN")) == ["Jürgen Müller"]
    assert names(chats(api, q="ünal")) == ["Ünal"]
    assert names(chats(api, q="müLLer")) == ["Jürgen Müller"]
    assert names(chats(api, q="@JM")) == ["Jürgen Müller"]          # username with the @
    assert names(chats(api, q="1004")) == ["User4"]                  # telegram id
    assert chats(api, q="user1")["total"] == 10                      # user10..user19 (the first three were renamed)
    assert names(chats(api, q="%_")) == ["100%_Sure"]                # LIKE wildcards are literal
    assert chats(api, q="no such chat")["total"] == 0


def test_status_and_date_filters(populated):
    _, api = populated
    ids = [c["id"] for c in chats(api)["items"]]
    ok(api.post("/api/telegram/chats/bulk-status", json={"ids": ids[:5], "status": "done"}))
    ok(api.post("/api/telegram/chats/bulk-status", json={"ids": ids[5:8], "status": "error"}))
    assert chats(api, status="done")["total"] == 5
    assert chats(api, status="done,error")["total"] == 8
    assert chats(api, status="pending")["total"] == 22
    assert chats(api, status="")["total"] == 30
    day = lambda days: (BASE - timedelta(days=days)).strftime("%Y-%m-%d")  # noqa: E731
    # chat N last wrote N days ago: 3..6 days ago are 100%_Sure, User4, User5, User6
    assert sorted(names(chats(api, date_from=day(6), date_to=day(3)))) == ["100%_Sure", "User4", "User5", "User6"]
    assert chats(api, date_from=day(3), date_to=day(3))["total"] == 1       # a date as upper bound covers the whole day
    assert chats(api, date_to=day(28))["total"] == 3
    assert chats(api, date_from=day(0))["total"] == 0
    assert chats(api, date_from=(BASE - timedelta(days=1, hours=1)).isoformat())["total"] == 1   # datetime with offset
    assert chats(api, status="done", q="user")["total"] <= 5            # filters combine


def test_sort_and_paging(populated):
    _, api = populated
    assert names(chats(api, limit=3)) == ["Jürgen Müller", "Ünal", "100%_Sure"]    # newest contact first by default
    assert names(chats(api, sort="last_contact_at", order="asc", limit=2)) == ["User30", "User29"]
    by_name = names(chats(api, sort="display_name", order="asc"))
    assert by_name[:3] == ["100%_Sure", "Jürgen Müller", "User10"]
    assert names(chats(api, sort="display_name", order="desc", limit=2)) == ["Ünal", "User9"]   # case-insensitive, umlauts last
    ids = [c["id"] for c in chats(api, sort="id", order="desc")["items"]]
    assert ids == sorted(ids, reverse=True)
    ok(api.post("/api/telegram/chats/bulk-status", json={"ids": ids[:2], "status": "paused"}))
    assert [c["chat_status"] for c in chats(api, sort="chat_status", order="asc")["items"]][:2] == ["paused"] * 2   # "paused" < "pending"
    assert chats(api, sort="messages_sent")["total"] == 30 and chats(api, sort="first_contact_at")["total"] == 30
    # paging walks through everything exactly once
    seen = []
    for offset in range(0, 30, 7):
        page = chats(api, sort="id", order="asc", limit=7, offset=offset)
        assert page["total"] == 30
        seen += [c["id"] for c in page["items"]]
    assert seen == sorted(seen) and len(set(seen)) == 30
    assert len(chats(api, limit=7, offset=28)["items"]) == 2 and chats(api, offset=500)["items"] == []


def test_ids_and_summary(make_app, scn):
    scn.dialogs([dlg(i, i) for i in range(1, 13)])
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir))
    api = app.client()
    link_synced(api)
    link_synced(api, "+4915100000003")                        # same dialogs, second account -> 24 chats
    by_phone = {a["phone"]: a["id"] for a in ok(api.get("/api/telegram/accounts"))}
    everything = chats(api)["items"]
    assert len(everything) == 24
    ok(api.post("/api/telegram/chats/bulk-status", json={"ids": [c["id"] for c in everything[:10]], "status": "done"}))

    all_ids = ok(api.get("/api/telegram/chats/ids"))
    assert all_ids["total"] == 24 and sorted(all_ids["ids"]) == sorted(c["id"] for c in everything)
    done = ok(api.get("/api/telegram/chats/ids", params={"status": "done"}))
    assert done["total"] == 10 and set(done["ids"]) == {c["id"] for c in everything[:10]}
    mine = ok(api.get("/api/telegram/chats/ids", params={"account_id": by_phone[PHONE], "q": "user1"}))
    assert mine["total"] == len(chats(api, account_id=by_phone[PHONE], q="user1")["items"]) == 4   # user1, 10, 11, 12
    assert ok(api.get("/api/telegram/chats/ids", params={"q": "nobody"})) == {"total": 0, "ids": []}

    summary = ok(api.get("/api/telegram/chats/summary"))
    assert summary == {"total": 24, "by_status": {"pending": 14, "in_progress": 0, "done": 10, "error": 0, "paused": 0}}
    one = ok(api.get("/api/telegram/chats/summary", params={"account_id": by_phone["+4915100000003"]}))
    assert one["total"] == 12 and sum(one["by_status"].values()) == 12


# --- editing ------------------------------------------------------------------------------------

def test_patch_chat(populated):
    app, api = populated
    c = chats(api)["items"][0]
    out = ok(api.patch(f"/api/telegram/chats/{c['id']}", json={"chat_status": "in_progress", "notes": "call back"}))
    assert out["chat_status"] == "in_progress" and out["notes"] == "call back"
    assert ok(api.get(f"/api/telegram/chats/{c['id']}"))["notes"] == "call back"
    db(app, "update tg_chat set error_reason='boom', chat_status='error' where id=?", c["id"])
    assert ok(api.patch(f"/api/telegram/chats/{c['id']}", json={"notes": "only notes"}))["error_reason"] == "boom"
    assert ok(api.patch(f"/api/telegram/chats/{c['id']}", json={"chat_status": "pending"}))["error_reason"] == ""
    assert api.patch(f"/api/telegram/chats/{c['id']}", json={"chat_status": "weird"}).status_code == 422
    assert api.patch(f"/api/telegram/chats/{c['id']}", json={"notes": "x" * 2001}).status_code == 422
    assert api.patch("/api/telegram/chats/99999", json={"notes": "x"}).status_code == 404
    assert api.get("/api/telegram/chats/99999").status_code == 404


def test_bulk_status(populated):
    _, api = populated
    ids = [c["id"] for c in chats(api)["items"]]
    assert ok(api.post("/api/telegram/chats/bulk-status", json={"ids": ids[:4] + [424242], "status": "paused"})) == {"updated": 4}
    assert chats(api, status="paused")["total"] == 4
    assert api.post("/api/telegram/chats/bulk-status", json={"ids": [], "status": "done"}).status_code == 422
    assert api.post("/api/telegram/chats/bulk-status", json={"ids": ids[:2], "status": "nope"}).status_code == 422
    assert chats(api, status="paused")["total"] == 4


def test_bulk_status_handles_more_ids_than_one_sql_statement(chats_app, scn):
    _, api = chats_app
    scn.dialogs([dlg(i) for i in range(1, 1301)])
    link_synced(api)
    ids = ok(api.get("/api/telegram/chats/ids"))["ids"]
    assert ok(api.post("/api/telegram/chats/bulk-status", json={"ids": ids, "status": "done"})) == {"updated": 1300}
    assert ok(api.get("/api/telegram/chats/summary"))["by_status"]["done"] == 1300


def test_bad_query_parameters(populated):
    _, api = populated
    for params in ({"limit": 1001}, {"limit": 0}, {"offset": -1}, {"sort": "notes"}, {"order": "sideways"},
                   {"status": "pending,bogus"}, {"date_from": "yesterday"}, {"date_to": "2026-13-45"}):
        assert api.get("/api/telegram/chats", params=params).status_code == 422, params
    assert api.get("/api/telegram/chats/ids", params={"status": "bogus"}).status_code == 422
    assert chats(api, account_id=999)["total"] == 0


def test_chat_routes_need_a_login(chats_app):
    app, _ = chats_app
    anon = httpx.Client(base_url=app.url)
    for method, path in (("get", "/chats"), ("get", "/chats/ids"), ("get", "/chats/summary"), ("get", "/chats/1"),
                         ("patch", "/chats/1"), ("post", "/chats/bulk-status"), ("post", "/accounts/1/sync-chats")):
        assert getattr(anon, method)("/api/telegram" + path).status_code in (401, 403), path


def test_deleting_an_account_removes_its_chats(chats_app, scn):
    _, api = chats_app
    scn.dialogs([dlg(1), dlg(2)])
    acc = link_synced(api)
    assert chats(api)["total"] == 2
    ok(api.delete(f"/api/telegram/accounts/{acc['id']}"))
    assert chats(api)["total"] == 0
