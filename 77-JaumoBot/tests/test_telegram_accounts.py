"""Telegram account linking against the fake Telethon client (tests/fake_telegram.py)."""

import json
import os
import sqlite3
import threading
from pathlib import Path

import httpx
import pytest
from websockets.sync.client import connect

from conftest import ok, wait_until

ENV = {"TELEGRAM_CLIENT_FACTORY": "fake_telegram:FakeClient",
       "PYTHONPATH": str(Path(__file__).parent) + os.pathsep + os.environ.get("PYTHONPATH", "")}
CREDS = {"api_id": 12345, "api_hash": "abcdef0123456789"}
PHONE, PHONE_2FA = "+4915100000001", "+4915100000002"


@pytest.fixture
def tg(make_app):
    app = make_app(**ENV)
    return app, app.client()


def link(api, phone=PHONE, creds=CREDS):
    started = ok(api.post("/api/telegram/accounts/start", json={"phone": phone, **creds}))
    done = ok(api.post(f"/api/telegram/accounts/{started['id']}/code", json={"code": "12345"}))
    assert done["step"] == "done", done
    return done["account"]


def accounts(api):
    return {a["phone"]: a for a in ok(api.get("/api/telegram/accounts"))}


def test_needs_login(tg):
    app, _ = tg
    anon = httpx.Client(base_url=app.url)
    assert anon.post("/api/telegram/accounts/start", json={"phone": PHONE}).status_code in (401, 403)


def test_start_requires_api_credentials_the_first_time(tg):
    _, api = tg
    r = api.post("/api/telegram/accounts/start", json={"phone": PHONE})
    assert r.status_code == 422 and "API ID" in r.text
    assert ok(api.get("/api/telegram/accounts")) == []


def test_link_account_with_code(tg):
    _, api = tg
    started = ok(api.post("/api/telegram/accounts/start", json={"phone": "+49 151-0000 0001", **CREDS}))
    assert started["step"] == "code" and started["phone"] == PHONE
    # nothing is online until the code is accepted
    assert accounts(api)[PHONE]["status"] == "offline" and accounts(api)[PHONE]["login_pending"]
    r = api.post(f"/api/telegram/accounts/{started['id']}/code", json={"code": "00000"})
    assert r.status_code == 422 and r.json()["detail"] == "The code is wrong"
    done = ok(api.post(f"/api/telegram/accounts/{started['id']}/code", json={"code": "1 2 3 4 5"}))
    acc = done["account"]
    assert done["step"] == "done" and acc["status"] == "online" and acc["has_session"]
    assert acc["tg_username"] == "user0001" and acc["label"] == "Test 0001"
    assert not acc["login_pending"]


def test_secrets_never_leave_the_server(tg):
    _, api = tg
    acc = link(api)
    for payload in (acc, ok(api.get("/api/telegram/accounts"))[0]):
        assert "session_string" not in payload and "api_hash" not in payload
    assert "fake:" not in api.get("/api/telegram/accounts").text
    s = ok(api.get("/api/telegram/settings"))
    assert s == {"api_id": 12345, "api_hash_hint": "…6789", "configured": True}


def test_credentials_are_remembered_for_the_next_account(tg):
    _, api = tg
    assert ok(api.get("/api/telegram/settings"))["configured"] is False
    link(api)
    started = ok(api.post("/api/telegram/accounts/start", json={"phone": "+4915100000003"}))   # no credentials sent
    ok(api.post(f"/api/telegram/accounts/{started['id']}/code", json={"code": "12345"}))
    assert set(accounts(api)) == {PHONE, "+4915100000003"}


def test_two_step_password(tg):
    _, api = tg
    started = ok(api.post("/api/telegram/accounts/start", json={"phone": PHONE_2FA, **CREDS}))
    step = ok(api.post(f"/api/telegram/accounts/{started['id']}/code", json={"code": "12345"}))
    assert step == {"step": "password"}
    assert accounts(api)[PHONE_2FA]["status"] == "offline"
    r = api.post(f"/api/telegram/accounts/{started['id']}/password", json={"password": "nope"})
    assert r.status_code == 422 and "password" in r.json()["detail"]
    done = ok(api.post(f"/api/telegram/accounts/{started['id']}/password", json={"password": "secret"}))
    assert done["step"] == "done" and done["account"]["status"] == "online"


def test_password_before_code_is_refused(tg):
    _, api = tg
    started = ok(api.post("/api/telegram/accounts/start", json={"phone": PHONE, **CREDS}))
    r = api.post(f"/api/telegram/accounts/{started['id']}/password", json={"password": "secret"})
    assert r.status_code == 422


def test_bad_inputs_leave_no_account_behind(tg):
    _, api = tg
    assert api.post("/api/telegram/accounts/start", json={"phone": "abc", **CREDS}).status_code == 422
    r = api.post("/api/telegram/accounts/start", json={"phone": "+4915100000009", **CREDS})
    assert r.status_code == 422 and r.json()["detail"] == "Invalid phone number"
    r = api.post("/api/telegram/accounts/start", json={"phone": PHONE, "api_id": 1, "api_hash": "bad"})
    assert r.status_code == 422 and "API ID" in r.json()["detail"]
    assert ok(api.get("/api/telegram/accounts")) == []
    assert ok(api.get("/api/telegram/settings"))["configured"] is False   # rejected credentials are not kept


def test_code_without_pending_login(tg):
    _, api = tg
    acc = link(api)
    r = api.post(f"/api/telegram/accounts/{acc['id']}/code", json={"code": "12345"})
    assert r.status_code == 410
    assert api.post("/api/telegram/accounts/999/code", json={"code": "1"}).status_code == 404


def test_cancel_removes_the_unfinished_account_but_keeps_a_linked_one(tg):
    _, api = tg
    started = ok(api.post("/api/telegram/accounts/start", json={"phone": PHONE, **CREDS}))
    ok(api.post(f"/api/telegram/accounts/{started['id']}/cancel"))
    assert ok(api.get("/api/telegram/accounts")) == []
    acc = link(api)
    ok(api.post(f"/api/telegram/accounts/{acc['id']}/disconnect"))
    restarted = ok(api.post("/api/telegram/accounts/start", json={"phone": PHONE}))   # "log in again"
    ok(api.post(f"/api/telegram/accounts/{restarted['id']}/cancel"))
    assert PHONE in accounts(api) and accounts(api)[PHONE]["has_session"]


def test_online_account_cannot_be_linked_twice(tg):
    _, api = tg
    link(api)
    assert api.post("/api/telegram/accounts/start", json={"phone": PHONE}).status_code == 409


def test_disconnect_and_connect(tg):
    _, api = tg
    acc = link(api)
    off = ok(api.post(f"/api/telegram/accounts/{acc['id']}/disconnect"))
    assert off["status"] == "offline" and off["has_session"] and not off["auto_connect"]
    on = ok(api.post(f"/api/telegram/accounts/{acc['id']}/connect"))
    assert on["status"] == "online" and on["auto_connect"]
    assert ok(api.get("/api/telegram/status"))["accounts_online"] == 1


def test_revoked_session_needs_a_new_login(tg):
    app, api = tg
    acc = link(api)
    ok(api.post(f"/api/telegram/accounts/{acc['id']}/disconnect"))
    with sqlite3.connect(app.storage / "db.sqlite") as db:
        db.execute("update tg_account set session_string='fake:revoked' where id=?", (acc["id"],))
    r = api.post(f"/api/telegram/accounts/{acc['id']}/connect")
    assert r.status_code == 422 and "log in again" in r.json()["detail"]
    a = accounts(api)[PHONE]
    assert a["status"] == "error" and not a["has_session"] and "log in again" in a["status_msg"]
    # connecting again explains what to do instead of retrying a dead session
    assert "not logged in" in api.post(f"/api/telegram/accounts/{acc['id']}/connect").json()["detail"]
    relinked = link(api)    # same phone: reuses the row
    assert relinked["id"] == acc["id"] and relinked["status"] == "online"


def test_network_error_is_reported_and_keeps_the_session(tg):
    app, api = tg
    acc = link(api)
    ok(api.post(f"/api/telegram/accounts/{acc['id']}/disconnect"))
    with sqlite3.connect(app.storage / "db.sqlite") as db:
        db.execute("update tg_account set session_string='fake:unreachable' where id=?", (acc["id"],))
    r = api.post(f"/api/telegram/accounts/{acc['id']}/connect")
    assert r.status_code == 502 and "network" in r.json()["detail"]
    a = accounts(api)[PHONE]
    assert a["status"] == "error" and a["has_session"]    # a network problem must not throw the login away


def test_rename_and_delete(tg):
    _, api = tg
    acc = link(api)
    assert ok(api.patch(f"/api/telegram/accounts/{acc['id']}", json={"label": "Sales 1"}))["label"] == "Sales 1"
    with sqlite3.connect(tg[0].storage / "db.sqlite") as db:
        db.execute("insert into tg_chat (account_id, telegram_id, username, display_name, last_message, chat_status,"
                   " messages_sent, error_reason, notes, created_at) values (?, '1', '', 'x', '', 'pending', 0, '', '',"
                   " '2026-01-01')", (acc["id"],))
    assert accounts(api)[PHONE]["chats"] == 1
    ok(api.delete(f"/api/telegram/accounts/{acc['id']}"))
    assert ok(api.get("/api/telegram/accounts")) == []
    assert ok(api.get("/api/telegram/status"))["chats"] == 0


def test_accounts_reconnect_after_a_server_restart(make_app):
    app = make_app(**ENV)
    api = app.client()
    link(api, PHONE)
    a2 = link(api, "+4915100000003")
    ok(api.post(f"/api/telegram/accounts/{a2['id']}/disconnect"))      # the operator turned this one off
    app.stop()
    app2 = make_app(storage=app.storage, **ENV)
    api2 = app2.client()
    wait_until(lambda: accounts(api2)[PHONE]["status"] == "online", msg="account to reconnect")
    assert accounts(api2)["+4915100000003"]["status"] == "offline"    # stays off, as the operator wanted


def test_status_changes_are_pushed_over_the_websocket(tg):
    app, api = tg
    acc = link(api)
    cookie = {"Cookie": f"jb_session={api.cookies['jb_session']}"}
    seen = []

    def reader():
        with connect(app.url.replace("http", "ws") + "/ws/modules/telegram", additional_headers=cookie,
                     open_timeout=10) as c:
            while (acc["id"], "online") not in seen:
                try:
                    msg = json.loads(c.recv(timeout=5))
                except Exception:
                    return
                if msg.get("type") == "account":
                    seen.append((msg["account_id"], msg["status"]))

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    import time
    time.sleep(0.5)
    ok(api.post(f"/api/telegram/accounts/{acc['id']}/disconnect"))
    ok(api.post(f"/api/telegram/accounts/{acc['id']}/connect"))
    t.join(10)
    assert [st for _, st in seen] == ["offline", "connecting", "online"]
