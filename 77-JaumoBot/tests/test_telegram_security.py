"""Telegram security: secrets never leave the server, every upload vector, path traversal, auth of the routes and the
WebSocket, SQL injection through filters / sort / ids, JSON body limits and CSV formula injection.
Hostile input is written by strangers (chat names, messages) or by the operator (labels, workflow names), so every
route is probed the way an attacker or a clumsy client would use it. (XSS in the panel: test_telegram_security_ui.py)"""

import base64
import csv
import hashlib
import hmac
import io
import json
import os
import stat
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
from websockets.sync.client import connect

from conftest import jpeg_bytes, ok, wait_until
from test_telegram_accounts import ENV, PHONE, PHONE_2FA, accounts, link
from test_telegram_chats import Scenario, chats, db, dlg, link_synced
from test_telegram_history import add_run, on_day
from test_telegram_runs import chat_ids, make_workflow, start, text_step, wait_status
from test_telegram_workflows import AAC, M4A, MP3, ogg_opus, wav_bytes

T = "/api/telegram"
M = f"{T}/media"
HASH = "deadbeefcafe1234deadbeefcafe1234"          # a recognisable api_hash: any appearance of it is a leak
CREDS = {"api_id": 424242, "api_hash": HASH}
MB = 1024 * 1024


def jpg():
    return jpeg_bytes(3, (60, 40))


def png():
    return jpeg_bytes(1, (60, 40), "PNG")


def webp():
    return jpeg_bytes(2, (60, 40), "WEBP")


def stored_tree(app):
    """Every file the server keeps besides the database and the log (a rejected upload must add none)."""
    skip = {"db.sqlite", "db.sqlite-wal", "db.sqlite-shm", "server.log"}
    return sorted(str(p.relative_to(app.storage)) for p in app.storage.rglob("*") if p.is_file() and p.name not in skip)


def raw_upload(api, filename: bytes, data: bytes, field: bytes = b"files"):
    """A multipart upload with byte-exact control over the file name (httpx would sanitise it)."""
    boundary = b"----secBoundary7MA4YWxkTrZu0gW"
    body = (b"--" + boundary + b'\r\nContent-Disposition: form-data; name="' + field + b'"; filename="' + filename
            + b'"\r\nContent-Type: application/octet-stream\r\n\r\n' + data + b"\r\n--" + boundary + b"--\r\n")
    return api.post(M, content=body, headers={"Content-Type": "multipart/form-data; boundary=" + boundary.decode()})


def detail(r):
    return r.json()["detail"]


@pytest.fixture
def tg(make_app):
    app = make_app(**ENV)
    return app, app.client()


# --- WebSocket tap ----------------------------------------------------------------------------------------

class Tap:
    """Records every raw message of the Telegram module WebSocket."""

    def __init__(self, app, api):
        self.messages, self._stop = [], threading.Event()
        cookie = {"Cookie": f"jb_session={api.cookies['jb_session']}"}
        ready = threading.Event()

        def reader():
            with connect(app.url.replace("http", "ws") + "/ws/modules/telegram", additional_headers=cookie, open_timeout=10) as c:
                ready.set()
                while not self._stop.is_set():
                    try:
                        self.messages.append(c.recv(timeout=0.5))
                    except TimeoutError:
                        continue
                    except Exception:  # noqa: BLE001  connection closed at shutdown
                        return

        self.thread = threading.Thread(target=reader, daemon=True)
        self.thread.start()
        assert ready.wait(10)

    def close(self):
        self._stop.set()
        self.thread.join(5)

    @property
    def text(self):
        return "\n".join(self.messages)


# --- secrets -----------------------------------------------------------------------------------------------

@pytest.fixture
def sec(make_app, tmp_path):
    """A linked account (distinctive api_hash), chats, a workflow and a finished run with one failed chat,
    all while a WebSocket listener records every event."""
    scn = Scenario(tmp_path / "fake_tg")
    scn.dialogs([dlg(1, 1), dlg(2, 2), dlg(3, 3)])
    (scn.dir / "send_errors.json").write_text(json.dumps({"1002": {"error": "UserPrivacyRestrictedError"}}))
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir), TELEGRAM_RETRY_WAIT="0.2")
    api = app.client()
    tap = Tap(app, api)
    started = ok(api.post(f"{T}/accounts/start", json={"phone": PHONE_2FA, **CREDS}))
    assert api.post(f"{T}/accounts/{started['id']}/code", json={"code": "00000"}).status_code == 422     # wrong code
    ok(api.post(f"{T}/accounts/{started['id']}/code", json={"code": "12345"}))
    assert api.post(f"{T}/accounts/{started['id']}/password", json={"password": "WrongPw-Zq81"}).status_code == 422
    ok(api.post(f"{T}/accounts/{started['id']}/password", json={"password": "secret"}))
    wait_until(lambda: accounts(api)[PHONE_2FA]["sync"] is None, msg="sync")
    acc = accounts(api)[PHONE_2FA]
    wf = make_workflow(api, [text_step("Hallo", 0)])
    ids = chat_ids(api, acc, 1001, 1002, 1003)
    run = start(api, acc, wf, ids)
    wait_status(api, run["id"], "done")
    yield app, api, acc, run, tap
    tap.close()


def session_of(app):
    return db(app, "select session_string from tg_account")[0][0]


def leaks(text, app):
    session = session_of(app)
    return [n for n in (HASH, HASH[:12], session, "WrongPw-Zq81") if n and n in text]


def test_the_session_is_really_stored_so_the_leak_checks_mean_something(sec):
    app, *_ = sec
    assert session_of(app).startswith("fake:+49") and db(app, "select api_hash from tg_account") == [(HASH,)]


def test_no_route_returns_a_secret(sec):
    app, api, acc, run, _ = sec
    cid = chats(api)["items"][0]["id"]
    paths = [f"{T}/status", f"{T}/settings", f"{T}/accounts", f"{T}/chats", f"{T}/chats/ids", f"{T}/chats/summary",
             f"{T}/chats/{cid}", f"{T}/workflows", f"{T}/runs", f"{T}/runs/{run['id']}", f"{T}/runs/{run['id']}/chats",
             f"{T}/runs/export.csv", f"{T}/runs/{run['id']}/export.csv", f"{T}/media", f"{T}/media/unused", f"{T}/stats",
             f"{T}/stats?account_id={acc['id']}", "/api/modules", "/api/settings", "/api/accounts/export"]
    for path in paths:
        r = api.get(path)
        assert r.status_code == 200, (path, r.status_code)
        assert not leaks(r.text, app), f"{path} leaks {leaks(r.text, app)}"
        body = r.text
        assert not any(f'"{key}"' in body for key in ("session_string", "api_hash", "access_hash")), path


def test_error_responses_never_echo_secrets(sec):
    app, api, acc, *_ = sec
    probes = [
        api.post(f"{T}/accounts/start", json={"phone": PHONE_2FA, **CREDS}),                       # already online
        api.post(f"{T}/accounts/start", json={"phone": "x", **CREDS}),
        api.post(f"{T}/accounts/start", json={"phone": PHONE, "api_id": "oops", "api_hash": HASH}),
        api.post(f"{T}/accounts/start", json={"phone": "+4915100000009", "api_id": 1, "api_hash": HASH}),
        api.post(f"{T}/accounts/{acc['id']}/code", json={"code": "12345"}),
        api.post(f"{T}/accounts/{acc['id']}/password", json={"password": "WrongPw-Zq81"}),
        api.put(f"{T}/settings", json={"api_id": 0, "api_hash": HASH}),
        api.patch(f"{T}/accounts/{acc['id']}", json={"nope": 1}),
    ]
    session = session_of(app)
    for r in probes:
        assert r.status_code >= 400, r.text
        text = r.text.replace(json.dumps({"phone": PHONE, "api_id": "oops", "api_hash": HASH}), "")
        # FastAPI's own 422 body repeats what the caller sent; secrets the caller did NOT just send must never show up
        assert session not in text and "fake:+49" not in text, r.text


def test_session_connect_failures_do_not_leak(sec):
    app, api, acc, *_ = sec
    ok(api.post(f"{T}/accounts/{acc['id']}/disconnect"))
    for session in ("fake:revoked", "fake:unreachable"):
        db(app, "update tg_account set session_string=?", session)
        r = api.post(f"{T}/accounts/{acc['id']}/connect")
        assert r.status_code >= 400 and session not in r.text and HASH not in r.text
        listing = api.get(f"{T}/accounts").text
        assert HASH not in listing and "fake:" not in listing


def test_websocket_events_never_carry_secrets(sec):
    app, api, acc, run, tap = sec
    ok(api.post(f"{T}/accounts/{acc['id']}/disconnect"))
    ok(api.post(f"{T}/accounts/{acc['id']}/connect"))
    ok(api.post(f"{T}/accounts/{acc['id']}/sync-chats"))
    time.sleep(1.5)
    assert len(tap.messages) >= 5, tap.messages          # login, sync and run events were really recorded
    assert {json.loads(m)["type"] for m in tap.messages} >= {"sync", "run"}
    text = tap.text
    for needle in (HASH, session_of(app), "WrongPw-Zq81", "session_string", "api_hash", "access_hash", "5001"):
        assert needle not in text, f"WebSocket carries {needle!r}"


def test_server_log_has_no_secrets(sec):
    app, api, acc, *_ = sec
    ok(api.post(f"{T}/accounts/{acc['id']}/disconnect"))
    db(app, "update tg_account set session_string='fake:unreachable'")
    api.post(f"{T}/accounts/{acc['id']}/connect")
    api.post(f"{T}/accounts/start", json={"phone": "+4915100000009", **CREDS})
    time.sleep(0.5)
    log = app.log.read_text(errors="replace")
    for needle in (HASH, "WrongPw-Zq81", "fake:+49"):
        assert needle not in log, f"server log contains {needle!r}"


def test_settings_only_show_the_hint(sec):
    _, api, *_ = sec
    s = ok(api.get(f"{T}/settings"))
    assert s == {"api_id": 424242, "api_hash_hint": "…1234", "configured": True}
    assert ok(api.put(f"{T}/settings", json={"api_id": 1, "api_hash": "  " + HASH.upper() + "  "}))["api_hash_hint"] == "…1234"


def test_account_public_fields_are_a_whitelist(sec):
    _, api, acc, *_ = sec
    got = set(accounts(api)[PHONE_2FA])
    assert got == {"id", "label", "phone", "api_id", "status", "status_msg", "auto_connect", "tg_user_id", "tg_username",
                   "created_at", "last_connected_at", "has_session", "login_pending", "chats", "sync"}


# --- authentication ----------------------------------------------------------------------------------------

ROUTES = [
    ("GET", "/status"), ("GET", "/settings"), ("PUT", "/settings"), ("GET", "/accounts"), ("POST", "/accounts/start"),
    ("POST", "/accounts/1/code"), ("POST", "/accounts/1/password"), ("POST", "/accounts/1/cancel"),
    ("POST", "/accounts/1/connect"), ("POST", "/accounts/1/disconnect"), ("PATCH", "/accounts/1"),
    ("DELETE", "/accounts/1"), ("POST", "/accounts/1/sync-chats"), ("GET", "/chats"), ("GET", "/chats/ids"),
    ("GET", "/chats/summary"), ("GET", "/chats/1"), ("PATCH", "/chats/1"), ("POST", "/chats/bulk-status"),
    ("POST", "/media"), ("GET", "/media"), ("GET", "/media/unused"), ("POST", "/media/cleanup"),
    ("GET", "/media/img-" + "0" * 32 + ".jpg"), ("DELETE", "/media/img-" + "0" * 32 + ".jpg"),
    ("GET", "/workflows"), ("POST", "/workflows"), ("GET", "/workflows/1"), ("PUT", "/workflows/1"),
    ("PATCH", "/workflows/1"), ("POST", "/workflows/1/duplicate"), ("DELETE", "/workflows/1"), ("POST", "/runs"),
    ("GET", "/runs"), ("GET", "/runs/export.csv"), ("POST", "/runs/cleanup"), ("GET", "/runs/1"),
    ("GET", "/runs/1/chats"), ("GET", "/runs/1/export.csv"), ("DELETE", "/runs/1"), ("POST", "/runs/1/pause"),
    ("POST", "/runs/1/resume"), ("POST", "/runs/1/stop"), ("POST", "/runs/1/restart"), ("GET", "/stats"),
]


def test_every_route_needs_login_and_the_list_is_complete(sec):
    app, api, *_ = sec
    anon = httpx.Client(base_url=app.url)
    for method, path in ROUTES:
        r = anon.request(method, T + path, json={})
        assert r.status_code in (401, 403), f"{method} {path} -> {r.status_code}"
        assert "chat" not in r.text.lower() or r.status_code == 401
    # a new route must be added to ROUTES (and so be checked): compare with what the app really serves
    spec = api.get("/openapi.json")
    if spec.status_code == 200:
        served = {(m.upper(), p[len(T):]) for p, ops in spec.json()["paths"].items() if p.startswith(T) for m in ops}
        known = {(m, p.replace("/1", "/{id_}").replace("/img-" + "0" * 32 + ".jpg", "/{name}")) for m, p in ROUTES}
        assert served == known, f"routes not covered: {served ^ known}"


def forged(user="admin", exp=None, secret="test-secret"):
    exp = exp if exp is not None else int(time.time()) + 3600
    payload = f"{user}|{exp}"
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(payload.encode()).decode() + "." + sig


def test_tokens_are_checked_for_signature_and_expiry(tg):
    app, api = tg
    good = httpx.Client(base_url=app.url, cookies={"jb_session": forged()})
    assert good.get(f"{T}/status").status_code == 200        # sanity: the forging recipe matches the server's
    bad = {
        "expired": forged(exp=int(time.time()) - 5),
        "wrong secret": forged(secret="other"),
        "empty": "",
        "no dot": "abc",
        "garbage": "!!!.???",
        "tampered": forged(user="admin").rsplit(".", 1)[0] + "." + "0" * 64,
        "stripped signature": forged().rsplit(".", 1)[0] + ".",
        "swapped payload": base64.urlsafe_b64encode(f"root|{int(time.time()) + 999}".encode()).decode() + "." + forged().rsplit(".", 1)[1],
    }
    for why, token in bad.items():
        c = httpx.Client(base_url=app.url, cookies={"jb_session": token})
        assert c.get(f"{T}/status").status_code == 401, why
        assert c.get(f"{T}/accounts").status_code == 401, why


def test_login_cookie_is_httponly_and_samesite(tg):
    app, _ = tg
    r = httpx.post(app.url + "/api/login", json={"username": "admin", "password": "test-pass-123"})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie or "samesite=strict" in cookie


def ws_url(app, path="/ws/modules/telegram"):
    return app.url.replace("http", "ws") + path


def test_websocket_without_a_valid_cookie_is_refused(tg):
    app, api = tg
    cases = {"none": {}, "garbage": {"Cookie": "jb_session=abc.def"}, "expired": {"Cookie": f"jb_session={forged(exp=1)}"},
             "wrong secret": {"Cookie": f"jb_session={forged(secret='x')}"}, "other cookie": {"Cookie": "session=abc"}}
    for why, headers in cases.items():
        with pytest.raises(Exception):
            with connect(ws_url(app), additional_headers=headers, open_timeout=5) as c:
                c.recv(timeout=3)          # a refused handshake raises on connect, a late close raises here
        # and no data frame may arrive before the refusal
    cookie = {"Cookie": f"jb_session={api.cookies['jb_session']}"}
    with connect(ws_url(app), additional_headers=cookie, open_timeout=5):
        pass                                # sanity: with the cookie it works


def test_websocket_query_string_tokens_do_not_authenticate(tg):
    app, _ = tg
    with pytest.raises(Exception):
        with connect(ws_url(app) + f"?jb_session={forged()}&token={forged()}", open_timeout=5) as c:
            c.recv(timeout=3)


def test_websocket_unknown_module_and_odd_paths_are_refused_even_when_logged_in(tg):
    app, api = tg
    cookie = {"Cookie": f"jb_session={api.cookies['jb_session']}"}
    for path in ("/ws/modules/nope", "/ws/modules/..", "/ws/modules/telegram%00", "/ws/modules/TELEGRAM", "/ws/modules/",
                 "/ws/modules/telegram/extra"):
        with pytest.raises(Exception):
            with connect(ws_url(app, path), additional_headers=cookie, open_timeout=5) as c:
                c.recv(timeout=2)


def test_websocket_with_cookie_receives_events_of_its_module_only(tg):
    app, api = tg
    cookie = {"Cookie": f"jb_session={api.cookies['jb_session']}"}
    with connect(ws_url(app), additional_headers=cookie, open_timeout=5) as c:
        link(api)
        msg = json.loads(c.recv(timeout=10))
        assert msg["type"] in ("sync", "chat", "run", "account", "ping")
    assert "jaumo" not in json.dumps(msg).lower()


# --- SQL injection, filters, sort ---------------------------------------------------------------------------

@pytest.fixture
def seeded(make_app, tmp_path):
    scn = Scenario(tmp_path / "fake_tg")
    scn.dialogs([dlg(1, 1, first_name="100% Real", username="pct"), dlg(2, 2, first_name="under_score", username="us_er"),
                 dlg(3, 3, first_name="O'Brien", username="obrien"), dlg(4, 4, first_name="back\\slash", username="bs"),
                 dlg(5, 5, first_name="plain", username="plain")])
    app = make_app(**ENV, FAKE_TG_DIR=str(scn.dir))
    api = app.client()
    link_synced(api)
    assert chats(api)["total"] == 5
    return app, api


INJECTIONS = ["' OR '1'='1", "'; DROP TABLE tg_chat; --", '" OR ""="', "1) OR (1=1", "%' OR 1=1 --", "\\' OR 1=1 --",
              "' UNION SELECT session_string,api_hash,1,1,1,1,1,1,1,1,1,1,1,1,1,1 FROM tg_account --", "x'; PRAGMA writable_schema=1; --",
              "ａ’ OR 1=1 --", "\u202e", "`; select 1", "${7*7}", "{{7*7}}"]


@pytest.mark.parametrize("payload", INJECTIONS, ids=range(len(INJECTIONS)))
def test_search_text_is_data_never_sql(seeded, payload):
    app, api = seeded
    for path in ("chats", "chats/ids"):
        r = api.get(f"{T}/{path}", params={"q": payload})
        assert r.status_code == 200, (path, r.text)
        assert r.json()["total"] == 0, f"{payload!r} matched rows via {path}"
        assert "api_hash" not in r.text and "fake:" not in r.text
    assert db(app, "select count(*) from tg_chat") == [(5,)]
    assert db(app, "select count(*) from tg_account") == [(1,)]


def test_like_wildcards_match_literally(seeded):
    _, api = seeded
    names = lambda q: sorted(c["display_name"] for c in chats(api, q=q)["items"])  # noqa: E731
    assert names("%") == ["100% Real"]
    assert names("_") == ["under_score"]
    assert names("\\") == ["back\\slash"]
    assert names("'") == ["O'Brien"]
    assert names("r_al") == []                      # _ is not "any one character"
    assert names("100%real") == []
    assert names("  %  ") == ["100% Real"]


def test_search_with_a_huge_needle_is_fine(seeded):
    _, api = seeded
    r = api.get(f"{T}/chats", params={"q": "a" * 30_000})
    assert r.status_code == 200 and r.json()["total"] == 0


@pytest.mark.parametrize("params", [
    {"status": "pending' OR '1'='1"}, {"status": "pending;DROP TABLE tg_chat"}, {"status": "PENDING"}, {"status": "x"},
    {"date_from": "2026-01-01' OR 1=1"}, {"date_to": "'; --"}, {"date_from": "yesterday"}, {"date_to": "2026-13-45"},
    {"account_id": "1 OR 1=1"}, {"account_id": "abc"}, {"limit": "1;DROP"}, {"limit": 0}, {"limit": 1001}, {"limit": -1},
    {"offset": -1}, {"offset": "x"},
    {"sort": "id; DROP TABLE tg_chat"}, {"sort": "ID"}, {"sort": "search_text"}, {"sort": "access_hash"}, {"sort": "notes"},
    {"sort": "error_reason"}, {"sort": "telegram_id"}, {"sort": "(select 1)"}, {"sort": "id desc"}, {"sort": "id,notes"},
    {"sort": "tg_account.session_string"}, {"sort": "1"}, {"sort": ""}, {"order": "desc;--"}, {"order": "DESC"},
    {"order": "asc,id"}, {"order": "random()"}, {"order": ""},
], ids=lambda p: "-".join(f"{k}={v}" for k, v in p.items()))
def test_bad_filter_parameters_are_refused_not_executed(seeded, params):
    app, api = seeded
    r = api.get(f"{T}/chats", params=params)
    assert r.status_code == 422, (params, r.status_code, r.text[:200])
    assert db(app, "select count(*) from tg_chat") == [(5,)]


def test_every_whitelisted_sort_works_in_both_directions(seeded):
    _, api = seeded
    for sort in ("id", "last_contact_at", "first_contact_at", "display_name", "chat_status", "messages_sent"):
        for order in ("asc", "desc"):
            r = api.get(f"{T}/chats", params={"sort": sort, "order": order})
            assert r.status_code == 200 and r.json()["total"] == 5, (sort, order)


@pytest.mark.parametrize("path", ["runs", "runs/export.csv"])
@pytest.mark.parametrize("params", [
    {"status": "done' OR '1'='1"}, {"status": "nope"}, {"status": "done,nope"}, {"date_from": "x'--"}, {"date_to": "9999-99-99"},
    {"account_id": "1;--"}, {"workflow_id": "abc"}, {"limit": 0}, {"limit": 501}, {"offset": -5}, {"workflow_id": "1 or 1=1"},
], ids=lambda p: "-".join(f"{k}={v}" for k, v in p.items()))
def test_bad_run_filters_are_refused(seeded, path, params):
    _, api = seeded
    if path.endswith(".csv") and ({"limit", "offset"} & set(params)):
        pytest.skip("the export has no paging")
    r = api.get(f"{T}/{path}", params=params)
    assert r.status_code == 422, (path, params, r.status_code)


def test_run_chat_status_filter_is_a_bound_parameter(seeded):
    app, api = seeded
    acc = accounts(api)[PHONE]
    wf = make_workflow(api, [text_step("x")])
    run = start(api, acc, wf, chat_ids(api, acc, 1001))
    wait_status(api, run["id"], "done", "error")
    for payload in ("done' OR '1'='1", "'; DROP TABLE tg_run_chat; --", "done) OR (1=1"):
        r = api.get(f"{T}/runs/{run['id']}/chats", params={"status": payload})
        assert r.status_code == 200 and r.json()["total"] == 0, payload
    assert db(app, "select count(*) from tg_run_chat") == [(1,)]


def test_stats_parameters(seeded):
    _, api = seeded
    for params in ({"days": 0}, {"days": 91}, {"days": "x"}, {"account_id": "1;--"}):
        assert api.get(f"{T}/stats", params=params).status_code == 422, params
    assert api.get(f"{T}/stats", params={"account_id": 999}).status_code == 404


def test_huge_integers_are_client_errors_not_server_errors(seeded):
    """SQLite binds at most 64-bit integers: a larger id used to be an OverflowError, i.e. a 500 with a traceback."""
    app, api = seeded
    big = 2 ** 70
    calls = [
        ("GET", f"{T}/chats/{big}", None), ("PATCH", f"{T}/chats/{big}", {"notes": "x"}),
        ("GET", f"{T}/chats?account_id={big}", None), ("GET", f"{T}/chats?offset={big}", None),
        ("GET", f"{T}/chats/ids?account_id={big}", None), ("GET", f"{T}/chats/summary?account_id={big}", None),
        ("POST", f"{T}/chats/bulk-status", {"ids": [big], "status": "done"}),
        ("GET", f"{T}/workflows/{big}", None), ("PUT", f"{T}/workflows/{big}", {"name": "x", "steps": []}),
        ("DELETE", f"{T}/workflows/{big}", None), ("GET", f"{T}/runs/{big}", None), ("GET", f"{T}/runs/{big}/chats", None),
        ("GET", f"{T}/runs?workflow_id={big}", None), ("GET", f"{T}/runs?offset={big}", None),
        ("POST", f"{T}/runs/{big}/stop", None), ("DELETE", f"{T}/runs/{big}", None),
        ("POST", f"{T}/runs", {"account_id": big, "workflow_id": 1, "chat_ids": [1]}),
        ("POST", f"{T}/runs", {"account_id": 1, "workflow_id": 1, "chat_ids": [big]}),
        ("GET", f"{T}/stats?account_id={big}", None), ("POST", f"{T}/accounts/{big}/code", {"code": "1"}),
        ("PATCH", f"{T}/accounts/{big}", {"label": "x"}), ("DELETE", f"{T}/accounts/{big}", None),
    ]
    server_errors = []
    for method, path, body in calls:
        r = api.request(method, path, json=body)
        if r.status_code >= 500:
            server_errors.append(f"{method} {path.replace(str(big), '2**70')} -> {r.status_code}")
    assert not server_errors, "\n".join(server_errors)


# --- uploads --------------------------------------------------------------------------------------------------

def reject(api, app, filename, data, status=(422,), fragment=None):
    before = stored_tree(app)
    r = raw_upload(api, filename if isinstance(filename, bytes) else filename.encode(), data)
    assert r.status_code in status, f"{filename!r}: {r.status_code} {r.text[:200]}"
    if fragment:
        assert fragment in r.text, r.text
    assert stored_tree(app) == before, f"{filename!r} left a file behind"


SPOOFS = [
    ("jpeg named png", "a.png", jpg()), ("png named jpg", "a.jpg", png()), ("webp named jpg", "a.jpg", webp()),
    ("jpeg named webp", "a.webp", jpg()), ("ogg named jpg", "a.jpg", ogg_opus(1)), ("jpeg named ogg", "a.ogg", jpg()),
    ("jpeg named mp3", "a.mp3", jpg()), ("png named wav", "a.wav", png()), ("html named png", "a.png", b"<html><script>alert(1)</script></html>"),
    ("html named jpg", "a.jpg", b"<!doctype html><script>alert(1)</script>"), ("php named jpg", "a.jpg", b"<?php system($_GET[0]); ?>"),
    ("svg named png", "a.png", b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>'),
    ("svg", "a.svg", b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>'),
    ("gif", "a.gif", b"GIF89a\x01\x00\x01\x00\x00\x00\x00;"), ("gif named jpg", "a.jpg", b"GIF89a\x01\x00\x01\x00\x00\x00\x00;"),
    ("exe", "a.exe", b"MZ\x90\x00\x03\x00\x00\x00"), ("exe named jpg", "a.jpg", b"MZ\x90\x00\x03\x00\x00\x00" + b"\0" * 100),
    ("elf named ogg", "a.ogg", b"\x7fELF\x02\x01\x01" + b"\0" * 100), ("zip named png", "a.png", b"PK\x03\x04" + b"\0" * 100),
    ("pdf named jpg", "a.jpg", b"%PDF-1.7\n" + b"\0" * 100), ("txt", "a.txt", b"hello"), ("html", "a.html", b"<script>1</script>"),
    ("no magic", "a.jpg", b"just text, not an image"), ("shell script named ogg", "a.ogg", b"#!/bin/sh\nrm -rf /\n"),
    ("jpeg header only", "a.jpg", b"\xff\xd8\xff\xe0" + b"junk" * 20), ("png signature only", "a.png", b"\x89PNG\r\n\x1a\n" + b"junk" * 20),
    ("webp stub", "a.webp", b"RIFF\x00\x00\x00\x00WEBPjunkjunkjunk"), ("truncated jpeg", "a.jpg", jpg()[:60]),
    ("1 byte", "a.jpg", b"\xff"), ("2 bytes", "a.jpg", b"\xff\xd8"), ("3 bytes jpeg magic", "a.jpg", b"\xff\xd8\xff"),
    ("11 bytes riff", "a.wav", b"RIFF\0\0\0\0WAV"), ("one NUL", "a.png", b"\0"),
]


@pytest.mark.parametrize("why,filename,data", SPOOFS, ids=[s[0] for s in SPOOFS])
def test_spoofed_and_damaged_uploads_are_rejected(tg, why, filename, data):
    app, api = tg
    reject(api, app, filename, data, status=(422, 503))        # 503 = a real-looking audio file but no ffmpeg here


def test_a_png_with_html_appended_is_stored_as_an_image_and_served_safely(tg):
    app, api = tg
    data = png() + b"<script>alert(1)</script>"
    r = raw_upload(api, b"poly.png", data)
    name = ok(r, 200)["saved"][0]["name"]
    got = api.get(f"{M}/{name}")
    assert got.status_code == 200 and got.headers["content-type"] == "image/png"
    assert got.headers["x-content-type-options"] == "nosniff"
    assert "content-disposition" not in got.headers or "attachment" in got.headers["content-disposition"]


FILENAMES = ["a.jpg.php", "shell.php.png", "a.jpg.exe", "x.tar.gz", "a.jpg.", "a.jpg ", ".jpg", "jpg",
             "a", "", "..jpg", "a..jpg", "....", ".", "..", "../a.jpg", "..\\a.jpg", "a/b.jpg", "a\\b.jpg", "/etc/passwd.jpg",
             "C:a.jpg", "a.jpg:stream", "a.jpg::$DATA", "....//a.jpg", "%2e%2e%2fa.jpg\u0000", "a\x00.jpg",
             "a.jpg\x00.php", "a\x01.jpg", "a\x1f.jpg", "a\t.jpg", "ａ.ｊｐｇ", "a.jpg\u200b", "a." + "j" * 300, "a" * 300 + ".jpg",
             "con.jpg.", "a.jpg/", "a.jpg\\"]


@pytest.mark.parametrize("filename", FILENAMES, ids=[repr(f)[:30] for f in FILENAMES])
def test_dangerous_file_names_are_rejected(tg, filename):
    app, api = tg
    before = stored_tree(app)
    r = raw_upload(api, filename.encode("utf-8"), jpg())
    assert 400 <= r.status_code < 500, f"{filename!r} -> {r.status_code} {r.text[:200]}"
    assert stored_tree(app) == before
    outside = [p for p in app.storage.parent.rglob("evil*")]
    assert not outside


@pytest.mark.parametrize("filename", [b"a\r\n.jpg", b"a\r\nContent-Type: text/html\r\n\r\n<script>.jpg", b'a".jpg', b"a\n.jpg"])
def test_header_injection_in_file_names_never_stores_anything(tg, filename):
    app, api = tg
    before = stored_tree(app)
    r = raw_upload(api, filename, jpg())
    assert r.status_code < 500, r.text[:200]
    # either refused outright, or (if the parser tolerated the name) stored only under a generated name
    for f in set(stored_tree(app)) - set(before):
        assert f.startswith(str(Path("telegram", "media"))) and Path(f).name.startswith(("img-", "voice-"))


def test_file_name_length_boundary(tg):
    app, api = tg
    ok(raw_upload(api, ("a" * 251 + ".jpg").encode(), jpg()), 200)         # 255 characters: allowed
    assert raw_upload(api, ("a" * 252 + ".jpg").encode(), jpg()).status_code == 422


def test_unicode_names_are_accepted_but_never_reach_the_disk(tg):
    app, api = tg
    names = ["bild-üöä-😀.jpg", "写真.JPG", "photo\u202egpj.jpg", "Ünal Weiß.jpeg", "a b c.jpg", " lead.jpg", "a'b.jpg"]
    for n in names:
        res = ok(raw_upload(api, n.encode(), jpg()), 200)
        assert res["saved"][0]["name"].isascii() and res["saved"][0]["name"].startswith("img-")
    files = (app.storage / "telegram" / "media").iterdir()
    assert all(f.name.isascii() and f.name.startswith("img-") for f in files)
    assert all("\u202e" not in f for f in stored_tree(app))


def test_extension_case_is_normalised_not_trusted(tg):
    _, api = tg
    for n in ("A.JPG", "a.JpEg", "a.Jpg"):
        assert ok(raw_upload(api, n.encode(), jpg()), 200)["saved"][0]["name"].endswith(".jpg")
    assert ok(raw_upload(api, b"a.PNG", png()), 200)["saved"][0]["name"].endswith(".png")


def test_the_stored_name_is_random_and_ignores_the_upload_name(tg):
    _, api = tg
    names = {ok(raw_upload(api, b"same.jpg", jpg()), 200)["saved"][0]["name"] for _ in range(5)}
    assert len(names) == 5 and all("same" not in n for n in names)
    assert all(len(n) == len("img-") + 32 + len(".jpg") for n in names)


def test_empty_and_missing_uploads(tg):
    app, api = tg
    before = stored_tree(app)
    assert raw_upload(api, b"a.jpg", b"").status_code == 422
    assert raw_upload(api, b"a.ogg", b"").status_code == 422
    assert raw_upload(api, b"a.jpg", jpg(), field=b"file").status_code == 422        # wrong form field name
    assert raw_upload(api, b"a.jpg", jpg(), field=b"").status_code == 422
    assert api.post(M).status_code == 422
    assert api.post(M, json={"files": []}).status_code == 422
    assert api.post(M, content=b"x", headers={"Content-Type": "multipart/form-data"}).status_code in (400, 422)
    assert api.post(M, content=b"--x\r\n", headers={"Content-Type": "multipart/form-data; boundary=x"}).status_code in (400, 422)
    assert api.post(M, files=[("files", ("", b"data"))]).status_code == 422          # empty file name
    assert stored_tree(app) == before


def test_image_size_boundary(tg):
    app, api = tg
    exact = jpg() + b"\0" * (10 * MB - len(jpg()))
    assert len(exact) == 10 * MB
    ok(raw_upload(api, b"big.jpg", exact), 200)                      # exactly 10 MB is allowed
    before = stored_tree(app)
    r = raw_upload(api, b"big.jpg", exact + b"\0")
    assert r.status_code == 413 and "too large" in detail(r)
    assert stored_tree(app) == before


def test_voice_oversize_is_refused_before_conversion(make_app, tmp_path):
    marker = tmp_path / "ffmpeg-called"
    script = tmp_path / "ffmpeg_marker.py"
    script.write_text(f"open({str(marker)!r}, 'w').write('x')\n")
    launcher = tmp_path / ("ffmpeg.cmd" if os.name == "nt" else "ffmpeg")
    launcher.write_text(f'@"{sys.executable}" "{script}" %*\r\n' if os.name == "nt" else f'#!/bin/sh\nexec "{sys.executable}" "{script}"\n')
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC)
    app = make_app(**ENV, FFMPEG_BIN=str(launcher))
    api = app.client()
    before = stored_tree(app)
    for name, data in (("a.ogg", ogg_opus(1) + b"\0" * (50 * MB)), ("a.wav", wav_bytes() + b"\0" * (50 * MB)),
                       ("a.mp3", MP3 + b"\0" * (50 * MB))):
        r = raw_upload(api, name.encode(), data)
        assert r.status_code == 413, (name, r.status_code, r.text[:200])
    assert not marker.exists(), "an oversized file reached ffmpeg"
    assert stored_tree(app) == before


def test_many_files_in_one_request_do_not_break_the_server(tg):
    app, api = tg
    files = [("files", (f"p{i}.jpg", jpeg_bytes(i % 7, (30, 20)), "image/jpeg")) for i in range(150)]
    r = api.post(M, files=files, timeout=120)
    assert r.status_code == 200 and len(r.json()["saved"]) == 150
    assert api.get(f"{T}/status").status_code == 200


def test_pillow_pixel_bomb_is_a_client_error(tg):
    """A 10 KB PNG that declares 400 000 x 400 000 pixels must not make the server decode (or crash on) it."""
    import struct
    import zlib

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    w = h = 400_000
    ihdr = struct.pack(">IIBBBBB", w, h, 1, 0, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"\0" * 1000)) + chunk(b"IEND", b"")
    app, api = tg
    before = stored_tree(app)
    t0 = time.time()
    r = raw_upload(api, b"bomb.png", data)
    assert time.time() - t0 < 10 and r.status_code == 422, (r.status_code, r.text[:200])
    assert stored_tree(app) == before
    assert api.get(f"{T}/status").status_code == 200


# --- media serving and deleting: path traversal -----------------------------------------------------------------

TRAVERSALS = ["..", "...", "../db.sqlite", "..%2fdb.sqlite", "..%2f..%2fdb.sqlite", "%2e%2e%2f%2e%2e%2fdb.sqlite",
              "..%5cdb.sqlite", "..%5c..%5cdb.sqlite", "%2e%2e", "....//....//db.sqlite", "db.sqlite", "server.log",
              "img-" + "0" * 32 + ".jpg", "IMG-" + "A" * 32 + ".JPG", "img-" + "a" * 32 + ".jpg%0a", "img-" + "a" * 32 + ".jpg%20",
              "img-" + "a" * 32 + ".jpg%00", "img-" + "a" * 32 + ".jpg%00.png", "img-" + "a" * 31 + ".jpg", "img-" + "a" * 33 + ".jpg",
              "img-" + "g" * 32 + ".jpg", "img-%2e%2e%2f" + "a" * 20 + ".jpg", "img-..%2f..%2fdb.sqlite", "notes.txt", "planted.html",
              "img-short.jpg", "voice-" + "a" * 32 + ".exe", "%00", "%0a", "%ff", "img-" + "a" * 32 + ".jpg/..%2f..%2fdb.sqlite",
              "img-" + "a" * 32 + ".jpg%2f..%2f..%2fdb.sqlite"]


@pytest.mark.parametrize("name", TRAVERSALS, ids=[t[:40] for t in TRAVERSALS])
def test_media_get_and_delete_cannot_leave_the_media_folder(tg, name):
    app, api = tg
    media = app.storage / "telegram" / "media"
    media.mkdir(parents=True, exist_ok=True)
    (media / "notes.txt").write_text("not a media file")
    (media / "planted.html").write_text("<script>alert(1)</script>")
    (media / "img-short.jpg").write_bytes(jpg())
    (app.storage / "telegram" / "outside.txt").write_text("outside")
    real = ok(raw_upload(api, b"a.jpg", jpg()), 200)["saved"][0]["name"]
    for method in ("GET", "DELETE"):
        r = api.request(method, f"{M}/{name}")
        assert r.status_code in (404, 405, 422), (method, name, r.status_code)
        assert b"SQLite format 3" not in r.content and "not a media file" not in r.text and "outside" not in r.text
        assert "<script>" not in r.text
    assert (app.storage / "db.sqlite").exists() and (app.storage / "telegram" / "outside.txt").exists()
    assert (media / "notes.txt").exists() and (media / "planted.html").exists() and (media / real).exists()


def test_media_list_ignores_foreign_files_in_the_folder(tg):
    app, api = tg
    media = app.storage / "telegram" / "media"
    media.mkdir(parents=True, exist_ok=True)
    for n in ("notes.txt", "planted.html", "img-short.jpg", "img-" + "A" * 32 + ".jpg", "voice-" + "a" * 32 + ".exe"):
        (media / n).write_bytes(b"x")
    real = ok(raw_upload(api, b"a.jpg", jpg()), 200)["saved"][0]["name"]
    assert [m["name"] for m in ok(api.get(M))] == [real]
    assert [m["name"] for m in ok(api.get(f"{M}/unused?min_age_minutes=0"))["items"]] == [real]
    ok(api.post(f"{M}/cleanup", json={"min_age_minutes": 0}))
    assert (media / "notes.txt").exists() and (media / "planted.html").exists()      # cleanup touches only media names


def test_media_get_headers(tg):
    _, api = tg
    for name, data, ctype in (("a.jpg", jpg(), "image/jpeg"), ("a.png", png(), "image/png"), ("a.webp", webp(), "image/webp"),
                              ("a.ogg", ogg_opus(2), "audio/ogg")):
        stored = ok(raw_upload(api, name.encode(), data), 200)["saved"][0]["name"]
        r = api.get(f"{M}/{stored}")
        assert r.content == data and r.headers["content-type"] == ctype
        assert r.headers["x-content-type-options"] == "nosniff"
        assert "private" in r.headers["cache-control"]                 # never cached by a shared proxy


def test_error_pages_for_media_are_json_not_html(tg):
    _, api = tg
    r = api.get(f"{M}/<script>alert(1)</script>")
    assert r.status_code in (404, 422) and r.headers["content-type"].startswith("application/json")
    assert "<script>" not in r.text


def test_module_static_files_are_not_a_file_browser(tg):
    app, api = tg
    for path in ("/modules-static/telegram/../../api/main.py", "/modules-static/telegram/..%2f..%2fapi%2fmain.py",
                 "/modules-static/telegram/engine.py", "/modules-static/telegram/api.py", "/modules-static/telegram/__init__.py",
                 "/modules-static/telegram/panel.js/../engine.py", "/modules-static/../api/main.py", "/modules-static/%2e%2e/api/main.py",
                 "/modules-static/telegram/", "/modules-static/nope/panel.js", "/static/../api/main.py", "/static/..%2fapi%2fmain.py",
                 "/static/%2e%2e/.env", "/static/../.env", "/modules-static/telegram/../../.env"):
        r = api.get(path)
        assert "FastAPI(" not in r.text and "session_string" not in r.text and "TELEGRAM_CLIENT_FACTORY" not in r.text, path
        assert "def start_login" not in r.text and "JAUMO_SIGN_SECRET" not in r.text, path
        assert r.status_code in (200, 404, 307, 400), (path, r.status_code)
        if r.status_code == 200:
            assert "text/html" in r.headers["content-type"], path       # the SPA fallback, never a source file


def test_panel_js_contains_no_secret_values(sec):
    app, api, *_ = sec
    js = api.get("/modules-static/telegram/panel.js").text
    assert HASH not in js and session_of(app) not in js


# --- ffmpeg as an attack surface ------------------------------------------------------------------------------------

def fake_ffmpeg(tmp_path, body: str) -> Path:
    """A stand-in ffmpeg whose behaviour is `body` (Python; `args` = argv, `out` = the output path)."""
    script = tmp_path / "fake_ffmpeg.py"
    script.write_text("import sys, json, time\nargs = sys.argv[1:]\nout = args[-1]\n"
                      f"json.dump(args, open({str(tmp_path / 'args.json')!r}, 'w'))\n" + body)
    launcher = tmp_path / ("ffmpeg.cmd" if os.name == "nt" else "ffmpeg")
    launcher.write_text(f'@"{sys.executable}" "{script}" %*\r\n' if os.name == "nt" else f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC)
    return launcher


def opus_file(tmp_path, size=0):
    (tmp_path / "ok.ogg").write_bytes(ogg_opus(3) + b"\0" * size)
    return repr(str(tmp_path / "ok.ogg"))


def test_ffmpeg_errors_do_not_leak_paths_or_command_lines(make_app, tmp_path):
    app = make_app(**ENV, FFMPEG_BIN=str(fake_ffmpeg(tmp_path, "sys.stderr.write('LEAKME /srv/secret/path in.mp3: Invalid data\\n'); sys.exit(1)\n")))
    api = app.client()
    r = raw_upload(api, b"song.mp3", MP3)
    assert r.status_code == 422
    for needle in ("LEAKME", "/srv", "in.mp3", "ffmpeg", "libopus", str(tmp_path)):
        assert needle not in r.text, r.text


def test_ffmpeg_gets_only_a_safe_temp_name_and_no_stdin(make_app, tmp_path):
    ff = fake_ffmpeg(tmp_path, f"import shutil\nshutil.copy({opus_file(tmp_path)}, out)\n")
    app = make_app(**ENV, FFMPEG_BIN=str(ff))
    api = app.client()
    for name in ("-evil -f lavfi.mp3", "$(touch pwned).wav", "a;b|c&d.m4a", "ü.aac", "-i.mp3"):
        data = {"mp3": MP3, "wav": wav_bytes(), "m4a": M4A, "aac": AAC}[name.rsplit(".", 1)[1]]
        ok(raw_upload(api, name.encode(), data), 200)
        args = json.loads((tmp_path / "args.json").read_text())
        joined = " ".join(args)
        assert "evil" not in joined and "pwned" not in joined and "ü" not in joined and "a;b" not in joined, args
        src = Path(args[args.index("-i") + 1])
        assert src.name.startswith("in.") and src.suffix[1:] in ("mp3", "wav", "m4a", "aac"), src
        assert "-nostdin" in args and "-map_metadata" in args           # no interactive prompts, no tags copied over
        assert not (tmp_path / "pwned").exists() and not Path("pwned").exists()


def test_a_converted_file_larger_than_the_voice_limit_is_not_stored(make_app, tmp_path):
    """Compressed audio can expand a lot: whatever ffmpeg produces must obey the same size limit as an upload."""
    ff = fake_ffmpeg(tmp_path, f"import shutil\nshutil.copy({opus_file(tmp_path, 52 * MB)}, out)\n")
    app = make_app(**ENV, FFMPEG_BIN=str(ff))
    api = app.client()
    r = raw_upload(api, b"bomb.mp3", MP3)
    assert r.status_code in (413, 422), f"{r.status_code} {r.text[:200]}"
    media = app.storage / "telegram" / "media"
    stored = list(media.iterdir()) if media.exists() else []       # nothing was stored, so the folder may not even exist
    assert not [p for p in stored if p.stat().st_size > 50 * MB], "a >50 MB voice file was stored"


def test_slow_conversions_do_not_block_the_server(make_app, tmp_path):
    ff = fake_ffmpeg(tmp_path, f"import shutil\ntime.sleep(3)\nshutil.copy({opus_file(tmp_path)}, out)\n")
    app = make_app(**ENV, FFMPEG_BIN=str(ff))
    api = app.client()
    results = []
    threads = [threading.Thread(target=lambda: results.append(raw_upload(app.client(), b"s.mp3", MP3).status_code)) for _ in range(6)]
    for t in threads:
        t.start()
    time.sleep(1.0)
    t0 = time.time()
    assert api.get(f"{T}/status").status_code == 200 and httpx.get(app.url + "/health").status_code == 200
    assert time.time() - t0 < 2.0, "the server stalled while audio was being converted"
    for t in threads:
        t.join(60)
    assert results == [200] * 6


def test_a_failed_conversion_leaves_no_temp_files_behind(make_app, tmp_path):
    ff = fake_ffmpeg(tmp_path, "sys.exit(1)\n")
    app = make_app(**ENV, FFMPEG_BIN=str(ff))
    api = app.client()
    import tempfile
    before = set(Path(tempfile.gettempdir()).glob("tmp*"))
    for _ in range(3):
        assert raw_upload(api, b"x.mp3", MP3).status_code == 422
    assert not [p for p in set(Path(tempfile.gettempdir()).glob("tmp*")) - before if (p / "in.mp3").exists()]
    assert stored_tree(app) == []


# --- JSON bodies: sizes and garbage ---------------------------------------------------------------------------------

def test_oversized_text_fields_are_refused(sec):
    app, api, acc, *_ = sec
    big = "x" * 1_000_000
    assert api.post(f"{T}/workflows", json={"name": big, "steps": [text_step("a")]}).status_code == 422
    assert api.post(f"{T}/workflows", json={"name": "ok", "steps": [text_step(big)]}).status_code == 422
    cid = chats(api)["items"][0]["id"]
    assert api.patch(f"{T}/chats/{cid}", json={"notes": big}).status_code == 422
    r = api.patch(f"{T}/accounts/{acc['id']}", json={"label": big})
    assert r.status_code == 422, "a 1 MB account label was accepted (it is sent with every account list and WebSocket event)"


def test_note_boundary_counts_characters(sec):
    _, api, *_ = sec
    cid = chats(api)["items"][0]["id"]
    assert api.patch(f"{T}/chats/{cid}", json={"notes": "😀" * 2000}).status_code == 200
    assert api.patch(f"{T}/chats/{cid}", json={"notes": "😀" * 2001}).status_code == 422


def test_a_workflow_with_an_absurd_number_of_steps_is_refused(tg):
    _, api = tg
    steps = [text_step("x")] * 100_000
    r = api.post(f"{T}/workflows", json={"name": "huge", "steps": steps}, timeout=120)
    assert 400 <= r.status_code < 500, f"{r.status_code}: a 100,000-step workflow was accepted"
    assert api.get(f"{T}/workflows").status_code == 200


def test_large_id_lists_are_handled(seeded):
    _, api = seeded
    ids = list(range(1, 200_001))
    r = api.post(f"{T}/chats/bulk-status", json={"ids": ids, "status": "paused"}, timeout=120)
    assert r.status_code == 200 and r.json()["updated"] == 5
    acc = accounts(api)[PHONE]
    wf = make_workflow(api, [text_step("x")])
    r = api.post(f"{T}/runs", json={"account_id": acc["id"], "workflow_id": wf["id"], "chat_ids": ids}, timeout=120)
    assert r.status_code == 422


def test_deeply_nested_json_is_a_client_error(tg):
    _, api = tg
    deep = "[" * 100_000 + "]" * 100_000
    r = api.post(f"{T}/workflows", content=b'{"name": "x", "steps": ' + deep.encode() + b"}", headers={"Content-Type": "application/json"})
    assert 400 <= r.status_code < 500, f"deep nesting gave {r.status_code}"
    assert api.get(f"{T}/status").status_code == 200


GARBAGE = [b"", b"null", b"[]", b"{}", b'"x"', b"1", b"true", b"{", b'{"a":', b"\xff\xfe\x00", b'{"name": null, "steps": null}', b'{"name": [], "steps": {}}', b'{"steps": "x", "name": 1}', b'{"ids": "abc", "status": 5}',
           b'{"days": "1; DROP TABLE tg_run"}',
           b'{"api_id": "x", "api_hash": 5}', b'{"code": 12345}', b'{"password": null}', b'{"label": 5}', b'{"chat_status": 5, "notes": []}',
           b'{"min_age_minutes": -1}', b'{"min_age_minutes": 99999999999999999999}']
WRITES = [("POST", "/accounts/start"), ("POST", "/accounts/{a}/code"), ("POST", "/accounts/{a}/password"), ("PATCH", "/accounts/{a}"),
          ("PUT", "/settings"), ("PATCH", "/chats/{c}"), ("POST", "/chats/bulk-status"), ("POST", "/workflows"),
          ("PUT", "/workflows/{w}"), ("PATCH", "/workflows/{w}"), ("POST", "/runs"), ("POST", "/runs/cleanup"),
          ("POST", "/media/cleanup")]


NON_FINITE = [b'{"name": NaN}', b'{"ids": NaN}', b'{"x": Infinity}', b'{"account_id": 1e999, "workflow_id": -Infinity, "chat_ids": [NaN]}']


@pytest.mark.parametrize("bodies", [GARBAGE, NON_FINITE], ids=["garbage", "nan-and-infinity"])
def test_garbage_bodies_never_cause_a_server_error(sec, bodies):
    app, api, acc, *_ = sec
    wf = make_workflow(api, [text_step("x")], name="fuzz")
    ids = {"a": acc["id"], "c": chats(api)["items"][0]["id"], "w": wf["id"]}
    bad = []
    for method, path in WRITES:
        for body in bodies:
            r = api.request(method, T + path.format(**ids), content=body, headers={"Content-Type": "application/json"})
            if r.status_code >= 500:
                bad.append(f"{method} {path} {body!r} -> {r.status_code}")
    assert not bad, "\n".join(bad)


def test_wrong_content_types_are_client_errors(sec):
    _, api, acc, *_ = sec
    for ctype in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data", "application/xml", ""):
        r = api.post(f"{T}/workflows", content=b'{"name": "x", "steps": []}', headers={"Content-Type": ctype} if ctype else {})
        assert r.status_code < 500, ctype


# --- CSV formula injection -----------------------------------------------------------------------------------------------

DANGEROUS = ["=cmd|' /C calc'!A0", "+SUM(1+1)", "-2+3", "@SUM(A1)", "\t=1+1", "\r=1+1", "=HYPERLINK(\"http://evil\",\"x\")",
             "=1+1", "+1", "-1", "@a"]


@pytest.fixture
def csv_rig(make_app):
    app = make_app(**ENV)
    api = app.client()
    acc = link(api)
    ok(api.patch(f"{T}/accounts/{acc['id']}", json={"label": "=HYPERLINK(\"http://evil\",\"label\")"}))
    for i, bad in enumerate(DANGEROUS):
        db(app, "insert into tg_chat (account_id, telegram_id, access_hash, search_text, username, display_name, last_message,"
                " chat_status, messages_sent, error_reason, notes, created_at) values (?, ?, '1', ?, ?, ?, ?, 'error', 0, ?, ?, ?)",
           acc["id"], str(7000 + i), bad.casefold(), bad, bad, bad, bad, bad, "2026-01-01 00:00:00.000000")
    ids = [r[0] for r in db(app, "select id from tg_chat order by id")]
    wf = ok(api.post(f"{T}/workflows", json={"name": "=WORKFLOW()", "steps": [text_step("hi")]}))
    run_id = add_run(app, acc["id"], [(c, "error", DANGEROUS[n]) for n, c in enumerate(ids)], status="done", ended=on_day(1),
                     name="+SUM(workflow)", workflow_id=wf["id"])
    return app, api, run_id


def cells(text):
    assert text.startswith("\ufeff")
    return [row for row in csv.reader(io.StringIO(text[1:]))]


def assert_neutral(rows):
    for row in rows[1:]:
        for cell in row:
            assert not cell or cell[0] not in "=+-@\t\r", f"formula-capable cell: {cell!r} in {row}"


def test_run_export_neutralises_formulas_but_keeps_the_text(csv_rig):
    _, api, run_id = csv_rig
    r = api.get(f"{T}/runs/{run_id}/export.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"].startswith("attachment")
    rows = cells(r.text)
    assert len(rows) == 1 + len(DANGEROUS)
    assert_neutral(rows)
    for row, bad in zip(rows[1:], DANGEROUS):
        # chat, username and error reason each still contain the original text (only prefixed)
        assert bad in row[1] and bad in row[2] and bad in row[6], (bad, row)


def test_runs_export_neutralises_workflow_and_account_names(csv_rig):
    _, api, _ = csv_rig
    rows = cells(api.get(f"{T}/runs/export.csv").text)
    assert_neutral(rows)
    assert "+SUM(workflow)" in rows[1][2] and "HYPERLINK" in rows[1][1]


def test_csv_round_trips_awkward_but_harmless_text(make_app):
    app = make_app(**ENV)
    api = app.client()
    acc = link(api)
    names = ["Anna, \"the\" Meier", "line1\nline2", "Jürgen 😀", "plain", "a=b", "x+y", "mail@home", "5-3", "  spaced  "]
    for i, n in enumerate(names):
        db(app, "insert into tg_chat (account_id, telegram_id, access_hash, search_text, username, display_name, last_message,"
                " chat_status, messages_sent, error_reason, notes, created_at) values (?, ?, '1', ?, '', ?, '', 'done', 0, '', '', '2026-01-01')",
           acc["id"], str(8000 + i), n.casefold(), n)
    ids = [r[0] for r in db(app, "select id from tg_chat order by id")]
    run_id = add_run(app, acc["id"], [(c, "done", "") for c in ids], ended=on_day(1))
    rows = cells(api.get(f"{T}/runs/{run_id}/export.csv").text)
    assert [r[1] for r in rows[1:]] == names                      # nothing harmless is altered


def test_csv_header_row_and_filename_are_fixed(csv_rig):
    _, api, run_id = csv_rig
    r = api.get(f"{T}/runs/{run_id}/export.csv")
    assert f'filename="telegram-run-{run_id}.csv"' in r.headers["content-disposition"]
    assert cells(r.text)[0][:3] == ["position", "chat", "username"]
    r = api.get(f"{T}/runs/export.csv")
    assert 'filename="telegram-runs.csv"' in r.headers["content-disposition"]


# --- hostile text through the JSON API -------------------------------------------------------------------------------------

def test_hostile_text_is_stored_verbatim_and_served_as_json(sec):
    app, api, acc, *_ = sec
    evil = '<img src=x onerror="alert(1)"><script>alert(2)</script>&amp;'     # short enough for a label (60 characters)
    r = api.patch(f"{T}/accounts/{acc['id']}", json={"label": evil})
    assert r.status_code == 200 and r.json()["label"] == evil and r.headers["content-type"].startswith("application/json")
    w = ok(api.post(f"{T}/workflows", json={"name": evil, "steps": [text_step(evil)]}))
    assert w["name"] == evil and w["steps"][0]["content"] == evil
    cid = chats(api)["items"][0]["id"]
    assert ok(api.patch(f"{T}/chats/{cid}", json={"notes": evil}))["notes"] == evil
    for path in ("accounts", "workflows", "chats"):
        r = api.get(f"{T}/{path}")
        assert r.headers["content-type"].startswith("application/json") and "text/html" not in r.headers["content-type"]
