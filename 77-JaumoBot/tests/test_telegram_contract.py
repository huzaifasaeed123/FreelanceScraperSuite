"""Telegram HTTP contract: every route refuses an anonymous caller (the list of routes is read from the running app, so
new routes are covered automatically), negative input for every endpoint (unknown ids, malformed bodies, wrong state,
huge / negative / unicode / SQL-looking values), response shapes (no secrets, iso dates, same field names for the same
thing) and pagination bounds. One shared server (module scope) with two linked accounts and 130 chats each."""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from websockets.sync.client import connect

from api.auth import COOKIE_NAME
from conftest import ROOT, AppServer, jpeg_bytes, ok, wait_until
from test_telegram_accounts import CREDS, ENV, PHONE, accounts, link
from test_telegram_chats import BASE, Scenario, dlg, wait_sync

T = "/api/telegram"
PHONE_B = "+4915100000003"
SECRET_KEYS = {"session_string", "api_hash", "access_hash", "search_text"}
BAD_STATES = (500, 501, 502, 503)
STEP = {"type": "text", "content": "hello", "pause_after": 0}
HOLD = {"type": "text", "content": "hold", "pause_after": 3600}     # keeps a run active


# --- the shared server ------------------------------------------------------------------------------

class World:
    """Server + a logged-in client + the ids the tests need."""

    def __init__(self, app, api, scn):
        self.app, self.api, self.scn = app, api, scn
        self.a = self.b = None            # account A is online, account B is linked and then disconnected
        self.chats_a, self.chats_b = [], []
        self.special = {}                 # display name -> chat id (A)
        self.wf = None                    # a one-step text workflow
        self.hold_wf = None               # a workflow whose first step is followed by a long pause

    def get(self, path, **params):
        return self.api.get(T + path, params=params)

    def stop_active(self):
        for r in ok(self.api.get(f"{T}/runs", params={"status": "queued,running,paused", "limit": 500}))["items"]:
            self.api.post(f"{T}/runs/{r['id']}/stop")

    def new_run(self, workflow=None, ids=None, **kw):
        body = {"account_id": self.a["id"], "workflow_id": (workflow or self.hold_wf)["id"],
                "chat_ids": ids or self.chats_a[:2], **kw}
        return ok(self.api.post(f"{T}/runs", json=body), 200)


SPECIAL_NAMES = ["Alice Müller", "100% Bob", "a_b", "🎉 Party 🎉", "'; DROP TABLE tg_chat;--", "Ünal Çelik", "Привет мир", "back\\slash"]


@pytest.fixture(scope="module")
def world(tmp_path_factory, jaumo):
    root = tmp_path_factory.mktemp("contract")
    scn = Scenario(root / "fake_tg")
    items = [dlg(i + 1, days=i, first_name=name, username=f"special{i}") for i, name in enumerate(SPECIAL_NAMES)]
    items += [dlg(i, days=i % 40) for i in range(10, 132)]          # 130 chats in all
    scn.dialogs(items)
    env = {**ENV, "FAKE_TG_DIR": str(scn.dir)}
    app = AppServer(root / "storage", jaumo.base, env).start()
    api = app.client()
    w = World(app, api, scn)
    w.a = link(api, PHONE)
    wait_sync(api, PHONE)
    w.b = link(api, PHONE_B)
    wait_sync(api, PHONE_B)
    ok(api.post(f"{T}/accounts/{w.b['id']}/disconnect"))
    listing = lambda acc: ok(api.get(f"{T}/chats", params={"account_id": acc["id"], "limit": 1000}))["items"]  # noqa: E731
    items_a, items_b = listing(w.a), listing(w.b)
    w.chats_a, w.chats_b = [c["id"] for c in items_a], [c["id"] for c in items_b]
    w.special = {c["display_name"]: c["id"] for c in items_a}
    w.wf = ok(api.post(f"{T}/workflows", json={"name": "Plain", "steps": [STEP]}))
    w.hold_wf = ok(api.post(f"{T}/workflows", json={"name": "Holding", "steps": [HOLD, STEP]}))
    yield w
    w.stop_active()
    app.stop()


@pytest.fixture(autouse=True)
def _settle(request):
    """No test may leave a run active: they all share account A."""
    yield
    if "world" in request.fixturenames:
        w = request.getfixturevalue("world")
        w.stop_active()
        w.api.put(f"{T}/settings", json=CREDS)         # a test that stored bad credentials must not break the next one


def walk(value, path=""):
    """Every (path, key, value) of a JSON document."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield path, k, v
            yield from walk(v, f"{path}/{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from walk(v, f"{path}[{i}]")


# --- 1. every route refuses an anonymous caller -----------------------------------------------------------

ROUTE_DUMP = """
import json
from fastapi.routing import APIRoute
from starlette.routing import WebSocketRoute
from api.main import app
out = []
def walk(routes, prefix=''):
    for r in routes:
        if hasattr(r, 'original_router'):        # an included router: its own routes under its prefix
            walk(r.original_router.routes, prefix + r.include_context.prefix)
        elif isinstance(r, APIRoute):
            out.extend(['http', m, prefix + r.path] for m in sorted(r.methods - {'HEAD', 'OPTIONS'}))
        elif isinstance(r, WebSocketRoute):
            out.append(['ws', 'GET', prefix + r.path])
walk(app.routes)
print(json.dumps([o for o in out if o[2].startswith(('/api/telegram', '/api/modules', '/ws/modules'))]))
"""


@pytest.fixture(scope="module")
def routes(tmp_path_factory):
    """Every route the app mounts for the Telegram module, read from the app itself."""
    env = {**os.environ, **ENV, "STORAGE_DIR": str(tmp_path_factory.mktemp("routes")), "ADMIN_USER": "admin",
           "ADMIN_PASS": "x", "SECRET_KEY": "x", "JAUMO_CLIENT_ID": "", "JAUMO_SIGN_SECRET": "", "PYTHONIOENCODING": "utf-8"}
    out = subprocess.run([sys.executable, "-c", ROUTE_DUMP], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def fill(path):
    return (path.replace("{id_}", "1").replace("{name}", "img-" + "0" * 32 + ".jpg")
            .replace("{key}", "telegram").replace("{account_id}", "1").replace("{run_id}", "1"))


def test_route_list_is_complete(routes):
    """Guards the generic test below: it must see the routes that exist."""
    http = {(m, p) for kind, m, p in routes if kind == "http"}
    assert len([p for p in http if p[1].startswith("/api/telegram")]) >= 45
    for expected in [("GET", "/api/telegram/status"), ("POST", "/api/telegram/accounts/start"), ("GET", "/api/telegram/chats"),
                     ("POST", "/api/telegram/runs"), ("GET", "/api/telegram/stats"), ("POST", "/api/telegram/media"),
                     ("DELETE", "/api/telegram/workflows/{id_}"), ("GET", "/api/modules")]:
        assert expected in http, expected
    assert ["ws", "GET", "/ws/modules/{key}"] in routes


def test_every_http_route_refuses_an_anonymous_caller(make_app, routes):
    app = make_app(**ENV)
    cookies = [{}, {COOKIE_NAME: "garbage"}, {COOKIE_NAME: "a.b.c"}, {COOKIE_NAME: ""}]
    checked = 0
    for kind, method, path in routes:
        if kind != "http":
            continue
        url = fill(path)
        for cookie in cookies:
            anon = httpx.Client(base_url=app.url, timeout=30, cookies=cookie)
            for body in (None, {}, {"name": "x", "steps": [STEP], "ids": [1], "status": "done", "phone": PHONE, **CREDS}):
                kw = {"json": body} if body is not None and method != "GET" else {}
                r = anon.request(method, url, **kw)
                assert r.status_code == 401, f"{method} {url} cookie={cookie} body={body} -> {r.status_code} {r.text[:200]}"
                assert "detail" in r.json()
                checked += 1
    assert checked >= 45 * 12
    # a refused write changed nothing
    api = app.client()
    assert ok(api.get(f"{T}/status")) == {"module": "telegram", "accounts": 0, "accounts_online": 0, "chats": 0, "runs": 0}
    assert ok(api.get(f"{T}/workflows")) == []


def test_anonymous_file_upload_and_downloads_are_refused(make_app):
    app = make_app(**ENV)
    anon = httpx.Client(base_url=app.url)
    r = anon.post(f"{T}/media", files=[("files", ("a.jpg", jpeg_bytes(1)))])
    assert r.status_code == 401
    assert not (app.storage / "telegram" / "media").exists() or not list((app.storage / "telegram" / "media").iterdir())
    for url in ("/runs/export.csv", "/runs/1/export.csv", "/media/img-" + "0" * 32 + ".jpg"):
        assert anon.get(T + url).status_code == 401, url


def test_every_websocket_route_refuses_an_anonymous_caller(make_app, routes):
    app = make_app(**ENV)
    ws_routes = [p for kind, _, p in routes if kind == "ws"]
    assert ws_routes
    for path in ws_routes:
        url = "ws://" + app.url.split("//")[1] + fill(path)
        for headers in ({}, {"Cookie": f"{COOKIE_NAME}=garbage"}):
            try:
                with connect(url, additional_headers=headers, open_timeout=10) as ws:
                    msg = ws.recv(timeout=5)
                pytest.fail(f"{path} let an anonymous caller in and sent {msg!r}")
            except Exception as e:  # noqa: BLE001  a refused handshake or an immediate close are both fine
                assert "TimeoutError" not in type(e).__name__, f"{path}: nothing refused the caller ({e!r})"


def test_openapi_schema_is_not_public(make_app):
    """The panel has no use for it and it lists every route."""
    app = make_app(**ENV)
    anon = httpx.Client(base_url=app.url)
    for url in ("/openapi.json", "/docs", "/redoc"):
        r = anon.get(url)
        assert r.status_code in (401, 404), f"{url} -> {r.status_code}"


def test_a_logged_in_client_is_not_refused(world):
    for path in ("/status", "/settings", "/accounts", "/chats", "/chats/ids", "/chats/summary", "/workflows", "/runs",
                 "/runs/export.csv", "/stats", "/media", "/media/unused"):
        assert world.get(path).status_code == 200, path


# --- 2. negative input: unknown ids, malformed bodies, wrong state ----------------------------------------------

WF_BODY = {"name": "x", "steps": [STEP]}
UNKNOWN_ID_ROUTES = [   # (method, path with {id}, json body or None) - the body is valid so only the id is wrong
    ("POST", "/accounts/{id}/code", {"code": "12345"}), ("POST", "/accounts/{id}/password", {"password": "x"}),
    ("POST", "/accounts/{id}/cancel", None), ("POST", "/accounts/{id}/connect", None),
    ("POST", "/accounts/{id}/disconnect", None), ("PATCH", "/accounts/{id}", {"label": "x"}),
    ("DELETE", "/accounts/{id}", None), ("POST", "/accounts/{id}/sync-chats", None),
    ("GET", "/chats/{id}", None), ("PATCH", "/chats/{id}", {"notes": "x"}),
    ("GET", "/workflows/{id}", None), ("PUT", "/workflows/{id}", WF_BODY), ("PATCH", "/workflows/{id}", {"name": "x"}),
    ("POST", "/workflows/{id}/duplicate", None), ("DELETE", "/workflows/{id}", None),
    ("GET", "/runs/{id}", None), ("GET", "/runs/{id}/chats", None), ("GET", "/runs/{id}/export.csv", None),
    ("DELETE", "/runs/{id}", None), ("POST", "/runs/{id}/pause", None), ("POST", "/runs/{id}/resume", None),
    ("POST", "/runs/{id}/stop", None), ("POST", "/runs/{id}/restart", None),
]


@pytest.mark.parametrize("bad_id", [999999, 0, -1])
@pytest.mark.parametrize("method,path,body", UNKNOWN_ID_ROUTES, ids=[f"{m} {p}" for m, p, _ in UNKNOWN_ID_ROUTES])
def test_unknown_id_is_404(world, method, path, body, bad_id):
    r = world.api.request(method, T + path.replace("{id}", str(bad_id)), **({"json": body} if body is not None else {}))
    assert r.status_code == 404, r.text
    assert isinstance(r.json()["detail"], str) and "not found" in r.json()["detail"].lower()


@pytest.mark.parametrize("method,path,body", UNKNOWN_ID_ROUTES, ids=[f"{m} {p}" for m, p, _ in UNKNOWN_ID_ROUTES])
def test_non_numeric_id_is_422(world, method, path, body):
    r = world.api.request(method, T + path.replace("{id}", "abc"), **({"json": body} if body is not None else {}))
    assert r.status_code == 422, r.text


def test_unknown_foreign_keys_in_bodies_and_filters(world):
    wf, a = world.wf["id"], world.a["id"]
    assert world.api.post(f"{T}/runs", json={"account_id": 999999, "workflow_id": wf, "chat_ids": [1]}).status_code == 404
    assert world.api.post(f"{T}/runs", json={"account_id": a, "workflow_id": 999999, "chat_ids": [1]}).status_code == 404
    assert world.get("/stats", account_id=999999).status_code == 404
    # filters on an unknown id are just empty
    assert ok(world.get("/chats", account_id=999999)) == {"total": 0, "items": []}
    assert ok(world.get("/runs", account_id=999999, workflow_id=999999)) == {"total": 0, "items": []}


@pytest.mark.parametrize("name", ["nope", "img-" + "0" * 32 + ".jpg", "voice-" + "f" * 32 + ".ogg", "IMG-" + "0" * 32 + ".JPG",
                                  "..", "%2e%2e%2f%2e%2e%2fetc%2fpasswd", "..%5c..%5cwindows%5cwin.ini", "img-" + "0" * 32 + ".jpg%00.png",
                                  "x" * 3000, "%F0%9F%8E%89", "'%20OR%201=1--"])
def test_media_names_that_do_not_exist_are_404(world, name):
    assert world.api.get(f"{T}/media/{name}").status_code == 404
    assert world.api.delete(f"{T}/media/{name}").status_code in (404, 405)


@pytest.mark.parametrize("big", [2 ** 63, 2 ** 64, 2 ** 70, 10 ** 40])
def test_huge_integer_ids_do_not_crash_the_server(world, big):
    """SQLite integers are 64 bit: an id beyond that is simply 'not found', never a 500."""
    wrong = []
    for method, path, body in UNKNOWN_ID_ROUTES:
        r = world.api.request(method, T + path.replace("{id}", str(big)), **({"json": body} if body is not None else {}))
        if r.status_code not in (404, 422):
            wrong.append(f"{method} {path} -> {r.status_code}")
    assert not wrong, f"id={big}: {wrong}"
    assert world.get("/chats", account_id=big).status_code in (200, 422)
    assert world.get("/runs", account_id=big, workflow_id=big).status_code in (200, 422)
    assert world.get("/stats", account_id=big).status_code in (404, 422)
    assert world.api.post(f"{T}/runs", json={"account_id": big, "workflow_id": big, "chat_ids": [big]}).status_code in (404, 422)
    assert world.api.post(f"{T}/runs", json={"account_id": world.a["id"], "workflow_id": world.wf["id"],
                                             "chat_ids": [big]}).status_code in (404, 422)
    assert world.api.post(f"{T}/chats/bulk-status", json={"ids": [big, -big], "status": "pending"}).status_code in (200, 422)
    assert world.get("/chats", limit=big).status_code == 422
    assert world.get("/chats", offset=big).status_code in (200, 422)
    assert world.get("/runs", offset=big).status_code in (200, 422)
    assert world.get("/runs/1/chats", offset=big).status_code in (200, 404, 422)


def malformed(method, path, bodies, expect=422):
    return [pytest.param(method, path, b, expect, id=f"{method} {path} {json.dumps(b, ensure_ascii=False)[:40]}") for b in bodies]


RAW = object()    # marker: send the value as a raw text body
MALFORMED = [
    *malformed("PUT", "/settings", [{}, {"api_id": 1}, {"api_hash": "x"}, {"api_id": "abc", "api_hash": "x"}, {"api_id": 0, "api_hash": "x"},
                                    {"api_id": 1, "api_hash": ""}, {"api_id": 1, "api_hash": "   "}, {"api_id": None, "api_hash": None},
                                    {"api_id": 1.5, "api_hash": "x"}, {"api_id": [1], "api_hash": "x"}, {"api_id": -5, "api_hash": "abc"},
                                    {"api_id": 1, "api_hash": ["x"]}, [], "text", 5, None]),
    *malformed("POST", "/accounts/start", [{}, {"phone": ""}, {"phone": "   "}, {"phone": None}, {"phone": 4915100000001}, {"phone": "abc"},
                                           {"phone": "+49"}, {"phone": "123456"}, {"phone": "1" * 16}, {"phone": "1" * 5000},
                                           {"phone": "'; DROP TABLE tg_account;--"}, {"phone": "🎉🎉🎉"}, {"phone": ["+4915100000009"]},
                                           {"phone": PHONE_B, "api_id": "abc"}, {"phone": PHONE_B, "api_id": [1]}, [], "x"]),
    *malformed("PATCH", "/accounts/{a}", [{}, {"label": None}, {"label": 5}, {"label": ["x"]}, {"label": {"a": 1}}, [], "x", None]),
    *malformed("PATCH", "/chats/{c}", [{"chat_status": "bogus"}, {"chat_status": ""}, {"chat_status": "DONE"}, {"chat_status": " done"},
                                       {"chat_status": 5}, {"chat_status": ["done"]}, {"chat_status": "done;--"}, {"chat_status": "🎉"},
                                       {"notes": 5}, {"notes": ["x"]}, {"notes": "x" * 2001}, {"notes": "🎉" * 2001}, {"notes": "x" * 100000}]),
    *malformed("POST", "/chats/bulk-status", [{}, {"ids": [1]}, {"status": "done"}, {"ids": [], "status": "done"}, {"ids": None, "status": "done"},
                                              {"ids": "1", "status": "done"}, {"ids": ["a"], "status": "done"}, {"ids": [1.5], "status": "done"},
                                              {"ids": [None], "status": "done"}, {"ids": [[1]], "status": "done"}, {"ids": [1], "status": "bogus"},
                                              {"ids": [1], "status": ""}, {"ids": [1], "status": None}, {"ids": [1], "status": 5},
                                              {"ids": [1], "status": "done' OR '1'='1"}, [], "x"]),
    *malformed("POST", "/workflows", [{}, {"name": "x"}, {"steps": [STEP]}, {"name": "", "steps": [STEP]}, {"name": "   ", "steps": [STEP]},
                                      {"name": "\t\n", "steps": [STEP]}, {"name": None, "steps": [STEP]}, {"name": 5, "steps": [STEP]},
                                      {"name": "n" * 81, "steps": [STEP]}, {"name": "🎉" * 81, "steps": [STEP]},
                                      {"name": "x", "steps": []}, {"name": "x", "steps": None}, {"name": "x", "steps": "text"},
                                      {"name": "x", "steps": {"type": "text"}}, {"name": "x", "steps": [1]}, {"name": "x", "steps": ["text"]},
                                      {"name": "x", "steps": [None]}, {"name": "x", "steps": [[]]}, {"name": "x", "steps": [{}]},
                                      {"name": "x", "steps": [{"type": "text"}]},
                                      {"name": "x", "steps": [{"type": "video", "content": "x"}]},
                                      {"name": "x", "steps": [{"type": None, "content": "x"}]},
                                      {"name": "x", "steps": [{"type": 5, "content": "x"}]},
                                      {"name": "x", "steps": [{"type": ["text"], "content": "x"}]},
                                      {"name": "x", "steps": [{"type": "TEXT", "content": "x"}]},
                                      {"name": "x", "steps": [{"type": "text", "content": ""}]},
                                      {"name": "x", "steps": [{"type": "text", "content": "  \n "}]},
                                      {"name": "x", "steps": [{"type": "text", "content": None}]},
                                      {"name": "x", "steps": [{"type": "text", "content": 5}]},
                                      {"name": "x", "steps": [{"type": "text", "content": ["a"]}]},
                                      {"name": "x", "steps": [{"type": "text", "content": "a" * 4097}]},
                                      {"name": "x", "steps": [{"type": "text", "content": "🎉" * 4097}]},
                                      {"name": "x", "steps": [{**STEP, "pause_after": -1}]},
                                      {"name": "x", "steps": [{**STEP, "pause_after": 86401}]},
                                      {"name": "x", "steps": [{**STEP, "pause_after": 10 ** 12}]},
                                      {"name": "x", "steps": [{**STEP, "pause_after": 2 ** 70}]},
                                      {"name": "x", "steps": [{**STEP, "pause_after": "5"}]},
                                      {"name": "x", "steps": [{**STEP, "pause_after": 1.5}]},
                                      {"name": "x", "steps": [{**STEP, "pause_after": True}]},
                                      {"name": "x", "steps": [{**STEP, "pause_after": None}]},
                                      {"name": "x", "steps": [{**STEP, "pause_after": [1]}]},
                                      {"name": "x", "steps": [STEP, {"type": "text", "content": ""}]},
                                      {"name": "x", "steps": [{"type": "image"}]}, {"name": "x", "steps": [{"type": "voice"}]},
                                      {"name": "x", "steps": [{"type": "image", "file": ""}]},
                                      {"name": "x", "steps": [{"type": "image", "file": None}]},
                                      {"name": "x", "steps": [{"type": "image", "file": 5}]},
                                      {"name": "x", "steps": [{"type": "image", "file": "../../etc/passwd"}]},
                                      {"name": "x", "steps": [{"type": "image", "file": "..\\..\\x.jpg"}]},
                                      {"name": "x", "steps": [{"type": "image", "file": "/etc/passwd"}]},
                                      {"name": "x", "steps": [{"type": "image", "file": "img-" + "0" * 32 + ".jpg"}]},
                                      {"name": "x", "steps": [{"type": "voice", "file": "img-" + "0" * 32 + ".jpg"}]},
                                      {"name": "x", "steps": [{"type": "image", "file": "voice-" + "0" * 32 + ".ogg"}]},
                                      {"name": "x", "steps": [{"type": "image", "file": "x" * 5000}]},
                                      {"name": "x", "steps": [{"type": "image", "file": "'; DROP TABLE tg_workflow;--"}]},
                                      [], "x", None]),
    *malformed("POST", "/runs", [{}, {"account_id": "{a}"}, {"account_id": "{a}", "workflow_id": "{w}"}, {"workflow_id": "{w}", "chat_ids": [1]},
                                 {"account_id": "x", "workflow_id": "{w}", "chat_ids": [1]}, {"account_id": "{a}", "workflow_id": "x", "chat_ids": [1]},
                                 {"account_id": None, "workflow_id": "{w}", "chat_ids": [1]}, {"account_id": "{a}", "workflow_id": "{w}", "chat_ids": None},
                                 {"account_id": "{a}", "workflow_id": "{w}", "chat_ids": "1"}, {"account_id": "{a}", "workflow_id": "{w}", "chat_ids": ["a"]},
                                 {"account_id": "{a}", "workflow_id": "{w}", "chat_ids": [1.5]}, {"account_id": "{a}", "workflow_id": "{w}", "chat_ids": [None]},
                                 {"account_id": "{a}", "workflow_id": "{w}", "chat_ids": [1], "on_error": "bogus"},
                                 {"account_id": "{a}", "workflow_id": "{w}", "chat_ids": [1], "on_error": ""},
                                 {"account_id": "{a}", "workflow_id": "{w}", "chat_ids": [1], "on_error": None},
                                 {"account_id": "{a}", "workflow_id": "{w}", "chat_ids": [1], "on_error": "NEXT"},
                                 {"account_id": "{a}", "workflow_id": "{w}", "chat_ids": [1], "retries": 0},
                                 {"account_id": "{a}", "workflow_id": "{w}", "chat_ids": [1], "retries": 6},
                                 {"account_id": "{a}", "workflow_id": "{w}", "chat_ids": [1], "retries": -1},
                                 {"account_id": "{a}", "workflow_id": "{w}", "chat_ids": [1], "retries": 10 ** 12},
                                 {"account_id": "{a}", "workflow_id": "{w}", "chat_ids": [1], "retries": "x"},
                                 {"account_id": "{a}", "workflow_id": "{w}", "chat_ids": [1], "retries": 2.5},
                                 {"account_id": "{a}", "workflow_id": "{w}", "chat_ids": [1], "auto_resume": "maybe"},
                                 {"account_id": "{a}", "workflow_id": "{w}", "chat_ids": [1], "auto_resume": [1]},
                                 [], "x", None]),
    *malformed("POST", "/runs/cleanup", [{}, {"days": 0}, {"days": -1}, {"days": 36501}, {"days": 10 ** 12}, {"days": 2 ** 70}, {"days": "x"},
                                         {"days": None}, {"days": 1.5}, {"days": [1]}, None, [], "x"]),
    *malformed("POST", "/media/cleanup", [{"min_age_minutes": -1}, {"min_age_minutes": 525601}, {"min_age_minutes": 10 ** 12},
                                          {"min_age_minutes": "x"}, {"min_age_minutes": None}, {"min_age_minutes": 1.5}, {"min_age_minutes": [1]},
                                          [], "x"]),
    *malformed("POST", "/accounts/{b}/code", [{}, {"code": None}, {"code": 12345}, {"code": ["1"]}, [], "x", None]),
    *malformed("POST", "/accounts/{b}/password", [{}, {"password": None}, {"password": 5}, {"password": ["x"]}, [], "x", None]),
    *malformed("PUT", "/workflows/{w}", [{}, {"name": "x"}, {"steps": [STEP]}, {"name": "", "steps": [STEP]}, {"name": "x", "steps": []},
                                         {"name": "x", "steps": [{"type": "bogus"}]}, {"name": "n" * 81, "steps": [STEP]}, [], "x", None]),
    *malformed("PATCH", "/workflows/{w}", [{}, {"name": ""}, {"name": "  "}, {"name": None}, {"name": 5}, {"name": "n" * 81}, [], "x", None]),
]


def subst(world, value):
    ids = {"{a}": world.a["id"], "{b}": world.b["id"], "{w}": world.wf["id"], "{c}": world.chats_a[0]}
    if isinstance(value, str):
        return ids.get(value, value)
    if isinstance(value, dict):
        return {k: subst(world, v) for k, v in value.items()}
    if isinstance(value, list):
        return [subst(world, v) for v in value]
    return value


@pytest.mark.parametrize("method,path,body,expect", MALFORMED)
def test_malformed_body_is_rejected(world, method, path, body, expect):
    before = (ok(world.get("/workflows")), ok(world.get("/accounts")), ok(world.get("/settings")))
    url = T + path
    for token, key in (("{a}", "a"), ("{b}", "b")):
        url = url.replace(token, str(getattr(world, key)["id"]))
    url = url.replace("{w}", str(world.wf["id"])).replace("{c}", str(world.chats_a[0]))
    r = world.api.request(method, url, json=subst(world, body))
    assert r.status_code == expect, f"{r.status_code} {r.text[:300]}"
    assert "detail" in r.json()
    # a refused request changes nothing
    assert (ok(world.get("/workflows")), ok(world.get("/accounts")), ok(world.get("/settings"))) == before


WRITE_ROUTES = [("/settings", "PUT"), ("/accounts/start", "POST"), ("/workflows", "POST"), ("/runs", "POST"),
                ("/chats/bulk-status", "POST"), ("/runs/cleanup", "POST"), ("/media/cleanup", "POST"),
                ("/accounts/{a}", "PATCH"), ("/chats/{c}", "PATCH"), ("/workflows/{w}", "PUT")]


@pytest.mark.parametrize("path,method", WRITE_ROUTES)
@pytest.mark.parametrize("raw,ctype", [(b"{", "application/json"), (b"", "application/json"), (b"not json", "application/json"),
                                       (b'{"a": 1}', "text/plain"), (b"[" * 5000, "application/json"),
                                       (b'{"a":' * 3000, "application/json")])
def test_unparsable_bodies_are_422(world, path, method, raw, ctype):
    url = T + path.replace("{a}", str(world.a["id"])).replace("{c}", str(world.chats_a[0])).replace("{w}", str(world.wf["id"]))
    r = world.api.request(method, url, content=raw, headers={"Content-Type": ctype})
    assert r.status_code == 422, f"{r.status_code} {r.text[:200]}"


def test_bodies_with_nan_or_lone_surrogates_or_bad_utf8_are_4xx_on_every_write_route(world):
    """They parse in Python but cannot be echoed in the error response: that must not become a 500.
    Two routes have no required field, so an unrelated bad key is simply ignored there (200)."""
    all_optional = {("/media/cleanup", "POST"), ("/chats/{c}", "PATCH")}
    wrong = []
    for path, method in WRITE_ROUTES:
        url = T + path.replace("{a}", str(world.a["id"])).replace("{c}", str(world.chats_a[0])).replace("{w}", str(world.wf["id"]))
        for raw in (b'{"a":NaN}', b"\xff\xfe\x00", b'{"name": "\\ud800"}', b'{"name": "x", "steps": [{"type":"\\ud800"}]}'):
            r = world.api.request(method, url, content=raw, headers={"Content-Type": "application/json"})
            if r.status_code >= 500 or (r.status_code == 200 and (path, method) not in all_optional):
                wrong.append(f"{method} {path} {raw[:20]!r} -> {r.status_code}")
    assert not wrong, wrong


def test_a_huge_request_body_does_not_crash_the_server(world):
    blob = "A" * (12 * 1024 * 1024)
    for path, method in (("/workflows", "POST"), ("/accounts/start", "POST"), ("/settings", "PUT")):
        r = world.api.request(method, T + path, json={"name": blob, "steps": [STEP], "phone": blob, "api_id": 1, "api_hash": blob})
        assert r.status_code < 500 and r.status_code >= 400, f"{path} -> {r.status_code}"
    assert world.get("/status").status_code == 200
    assert ok(world.get("/settings"))["api_id"] == CREDS["api_id"]


def test_the_limit_of_workflow_name_and_step_text_is_exact(world):
    api = world.api
    w = ok(api.post(f"{T}/workflows", json={"name": "🎉" * 80, "steps": [{**STEP, "content": "😀" * 4096}]}))
    assert w["name"] == "🎉" * 80 and w["steps"][0]["content"] == "😀" * 4096
    assert api.get(f"{T}/workflows/{w['id']}").json()["name"] == "🎉" * 80
    ok(api.delete(f"{T}/workflows/{w['id']}"))
    w = ok(api.post(f"{T}/workflows", json={"name": "n" * 80, "steps": [{**STEP, "pause_after": 86400}]}))
    assert w["steps"][0]["pause_after"] == 86400
    ok(api.delete(f"{T}/workflows/{w['id']}"))


def test_notes_limit_is_exact_and_unicode_survives(world):
    cid = world.chats_a[0]
    note = "ä🎉'\"; DROP TABLE tg_chat;--\n\t\\ <script>alert(1)</script> 日本語"
    assert ok(world.api.patch(f"{T}/chats/{cid}", json={"notes": note}))["notes"] == note
    assert ok(world.get(f"/chats/{cid}"))["notes"] == note
    assert ok(world.api.patch(f"{T}/chats/{cid}", json={"notes": "🎉" * 2000}))["notes"] == "🎉" * 2000
    assert world.api.patch(f"{T}/chats/{cid}", json={"notes": "x" * 2001}).status_code == 422
    assert ok(world.get(f"/chats/{cid}"))["notes"] == "🎉" * 2000          # the refusal did not clear it
    assert ok(world.api.patch(f"{T}/chats/{cid}", json={"notes": ""}))["notes"] == ""
    assert ok(world.api.patch(f"{T}/chats/{cid}", json={}))["notes"] == ""            # an empty patch is a no-op


@pytest.mark.parametrize("text", ["'; DROP TABLE tg_workflow;--", "\" OR 1=1 --", "Robert'); DROP TABLE tg_chat;--", "%", "_", "\\", "a\u0000b",
                                  "🎉👨‍👩‍👧‍👦🇩🇪", "Привет", "日本語テキスト", "العربية", "e\u0301", "ß", "<b>x</b>", "${7*7}", "{{7*7}}", "\u202eevil", "a\r\nb"])
def test_tricky_strings_round_trip_in_workflows(world, text):
    r = world.api.post(f"{T}/workflows", json={"name": f"n-{text}"[:80], "steps": [{**STEP, "content": text}]})
    if r.status_code == 422:           # a refusal is acceptable for control characters, a crash is not
        return
    assert r.status_code == 200, r.text
    w = r.json()
    assert w["steps"][0]["content"] == text, "text must be stored exactly as typed"
    assert ok(world.get(f"/workflows/{w['id']}"))["steps"][0]["content"] == text
    ok(world.api.delete(f"{T}/workflows/{w['id']}"))
    assert ok(world.get("/status"))["chats"] == 260


def test_lone_surrogate_and_null_in_strings_are_not_a_500(world):
    for body in (b'{"name": "x\\ud800y", "steps": [{"type":"text","content":"a","pause_after":0}]}',
                 b'{"name": "x", "steps": [{"type":"text","content":"a\\ud800","pause_after":0}]}',
                 b'{"name": "nul\\u0000l", "steps": [{"type":"text","content":"a\\u0000b","pause_after":0}]}'):
        r = world.api.post(f"{T}/workflows", content=body, headers={"Content-Type": "application/json"})
        assert r.status_code in (200, 422), f"{r.status_code} {r.text[:200]}"
        if r.status_code == 200:
            ok(world.api.delete(f"{T}/workflows/{r.json()['id']}"))
    r = world.api.patch(f"{T}/chats/{world.chats_a[0]}", content=b'{"notes": "x\\ud800"}', headers={"Content-Type": "application/json"})
    assert r.status_code in (200, 422), r.text[:200]
    r = world.api.patch(f"{T}/accounts/{world.a['id']}", content=b'{"label": "x\\ud800"}', headers={"Content-Type": "application/json"})
    assert r.status_code in (200, 422), r.text[:200]
    assert world.get("/status").status_code == 200


def test_account_label_edge_cases(world):
    a = world.a["id"]
    assert ok(world.api.patch(f"{T}/accounts/{a}", json={"label": "  Hans 🎉  "}))["label"] == "Hans 🎉"
    assert ok(world.api.patch(f"{T}/accounts/{a}", json={"label": "'; DROP TABLE tg_account;--"}))["label"] == "'; DROP TABLE tg_account;--"
    assert ok(world.api.patch(f"{T}/accounts/{a}", json={"label": "   "}))["label"] == PHONE         # blank falls back to the phone
    assert ok(world.api.patch(f"{T}/accounts/{a}", json={"label": ""}))["label"] == PHONE
    r = world.api.patch(f"{T}/accounts/{a}", json={"label": "x" * 500000})
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        assert len(r.json()["label"]) <= 500000
    ok(world.api.patch(f"{T}/accounts/{a}", json={"label": "Test 0001"}))


def test_settings_validation_does_not_clobber_saved_credentials(world):
    saved = ok(world.get("/settings"))
    for body in ({"api_id": -5, "api_hash": "abc"}, {"api_id": 0, "api_hash": "abc"}, {"api_id": 5, "api_hash": ""}):
        r = world.api.put(f"{T}/settings", json=body)
        if r.status_code == 200:
            ok(world.api.put(f"{T}/settings", json=CREDS))          # restore before failing
        assert r.status_code == 422, f"{body} was accepted"
    assert ok(world.get("/settings")) == saved
    r = ok(world.api.put(f"{T}/settings", json={"api_id": CREDS["api_id"], "api_hash": "  " + CREDS["api_hash"] + "  "}))
    assert r == saved                                                    # stripped, same hint


def test_phone_numbers_are_normalized_and_bounded(world):
    for phone in ("+49 (151) 000-00009", "+49-151-000 000 09", "++4915100000009", "tel: +49 151 00000009"):
        r = world.api.post(f"{T}/accounts/start", json={"phone": phone})
        assert r.status_code == 422                                      # +4915100000009 is the fake's invalid number
    assert PHONE_B in accounts(world.api) and "+4915100000009" not in accounts(world.api)
    for phone in ("1" * 6, "1" * 16, "", "+", "abc"):
        assert world.api.post(f"{T}/accounts/start", json={"phone": phone}).status_code == 422, phone
    assert "+4915100000009" not in accounts(world.api)                  # a refused start leaves no half-created account


# --- wrong state: 409 ---------------------------------------------------------------------------------------

def test_linking_an_online_account_again_is_409(world):
    r = world.api.post(f"{T}/accounts/start", json={"phone": PHONE})
    assert r.status_code == 409, r.text


def test_login_steps_without_a_pending_login_are_refused(world):
    for path, body in (("code", {"code": "12345"}), ("password", {"password": "secret"})):
        r = world.api.post(f"{T}/accounts/{world.a['id']}/{path}", json=body)
        assert r.status_code in (409, 410), f"{path}: {r.status_code} {r.text}"
        assert world.get("/accounts").json()[0]["status"] == "online"


def test_password_before_code_and_wrong_code_flow(world):
    started = ok(world.api.post(f"{T}/accounts/start", json={"phone": "+4915100000002"}))
    pid = started["id"]
    r = world.api.post(f"{T}/accounts/{pid}/password", json={"password": "secret"})
    assert r.status_code == 422 and "code" in r.json()["detail"].lower()
    for code in ("", "   ", "0", "x" * 5000, "'; --", "🎉", "1" * 40):
        r = world.api.post(f"{T}/accounts/{pid}/code", json={"code": code})
        assert r.status_code in (422, 410), f"code {code[:10]!r}: {r.status_code} {r.text[:100]}"
    ok(world.api.post(f"{T}/accounts/{pid}/code", json={"code": "12345"}))          # right code -> asks for the password
    for pw in ("", "wrong", "p" * 10000, "'; --"):
        r = world.api.post(f"{T}/accounts/{pid}/password", json={"password": pw})
        assert r.status_code in (422, 410), f"password {pw[:10]!r}: {r.status_code} {r.text[:100]}"
    ok(world.api.post(f"{T}/accounts/{pid}/cancel"))
    assert "+4915100000002" not in accounts(world.api)                              # cancel removed the half-linked account
    assert world.api.post(f"{T}/accounts/{pid}/cancel").status_code == 404           # and a second cancel is a plain 404


def test_cancel_never_deletes_a_linked_account(world):
    ok(world.api.post(f"{T}/accounts/{world.a['id']}/cancel"))
    assert PHONE in accounts(world.api) and accounts(world.api)[PHONE]["has_session"]


def test_account_actions_on_an_offline_account_are_409(world):
    b = world.b["id"]
    assert accounts(world.api)[PHONE_B]["status"] == "offline"
    r = world.api.post(f"{T}/accounts/{b}/sync-chats")
    assert r.status_code == 409, r.text
    r = world.api.post(f"{T}/runs", json={"account_id": b, "workflow_id": world.wf["id"], "chat_ids": world.chats_b[:1]})
    assert r.status_code == 409, r.text
    assert ok(world.get("/runs", account_id=b))["total"] == 0


def test_disconnect_twice_and_connect_twice_are_harmless(world):
    b = world.b["id"]
    assert ok(world.api.post(f"{T}/accounts/{b}/disconnect"))["status"] == "offline"
    assert ok(world.api.post(f"{T}/accounts/{b}/disconnect"))["status"] == "offline"
    assert ok(world.api.post(f"{T}/accounts/{b}/connect"))["status"] == "online"
    assert ok(world.api.post(f"{T}/accounts/{b}/connect"))["status"] == "online"
    ok(world.api.post(f"{T}/accounts/{b}/disconnect"))


def test_run_state_machine_refusals(world):
    api = world.api
    run = world.new_run()
    rid = run["id"]
    assert run["status"] == "running"
    refused = lambda path, method="post": getattr(api, method)(f"{T}/runs/{rid}{path}")  # noqa: E731
    assert refused("/resume").status_code == 409                    # running cannot be resumed
    assert refused("", "delete").status_code == 409                 # an active run cannot be deleted
    assert refused("/restart").status_code == 409                   # nor restarted
    assert api.post(f"{T}/runs", json={"account_id": world.a["id"], "workflow_id": world.wf["id"],
                                       "chat_ids": world.chats_a[:1]}).status_code == 409      # one run per account
    assert api.delete(f"{T}/accounts/{world.a['id']}").status_code == 409                   # account with an active run
    assert api.delete(f"{T}/workflows/{world.hold_wf['id']}").status_code == 409            # workflow with an active run
    assert accounts(api)[PHONE]["status"] == "online"
    assert ok(refused("/pause"))["status"] == "paused"
    assert refused("/pause").status_code == 409                     # paused cannot be paused
    assert refused("", "delete").status_code == 409
    assert refused("/restart").status_code == 409
    assert ok(refused("/resume"))["status"] == "running"
    assert ok(refused("/stop"))["status"] == "stopped"
    for path in ("/pause", "/resume", "/stop"):
        r = refused(path)
        assert r.status_code == 409 and "stopped" in r.json()["detail"], (path, r.text)
    # a finished run is deletable, restartable, and then gone
    again = ok(refused("/restart"))
    assert again["id"] != rid and again["status"] == "running" and again["total"] == run["total"]
    ok(api.post(f"{T}/runs/{again['id']}/stop"))
    ok(refused("", "delete"))
    assert refused("", "delete").status_code == 404
    assert refused("", "get").status_code == 404
    assert refused("/chats", "get").status_code == 404


def test_run_creation_refusals(world):
    api, a, wf = world.api, world.a["id"], world.wf["id"]
    post = lambda **kw: api.post(f"{T}/runs", json={"account_id": a, "workflow_id": wf, "chat_ids": world.chats_a[:2], **kw})  # noqa: E731
    assert post(chat_ids=[]).status_code == 422
    assert post(chat_ids=[999999]).status_code == 422                                   # unknown chat
    assert post(chat_ids=[world.chats_a[0], 999999]).status_code == 422                 # one unknown spoils all
    assert post(chat_ids=[-1]).status_code == 422
    assert post(chat_ids=[0]).status_code == 422
    assert post(chat_ids=world.chats_b[:1]).status_code == 422                          # the other account's chat
    assert post(chat_ids=[world.chats_a[0], world.chats_b[0]]).status_code == 422
    assert ok(world.get("/runs"))["total"] == 0 or all(r["status"] != "running" for r in ok(world.get("/runs"))["items"])
    dup = ok(post(chat_ids=[world.chats_a[1], world.chats_a[0], world.chats_a[1], world.chats_a[0]]))
    assert dup["total"] == 2                                                              # duplicates are dropped
    items = ok(world.get(f"/runs/{dup['id']}/chats"))["items"]
    assert [i["chat_id"] for i in items] == [world.chats_a[1], world.chats_a[0]]        # first occurrence keeps its place


def test_run_with_more_chats_than_one_database_batch(world):
    big = ok(world.api.post(f"{T}/workflows", json={"name": "Quick", "steps": [STEP]}))
    run = world.new_run(big, ids=world.chats_a)
    assert run["total"] == len(world.chats_a) == 130
    done = wait_until(lambda: (lambda r: r if r["status"] == "done" else None)(ok(world.get(f"/runs/{run['id']}"))), timeout=60, msg="run done")
    assert done["success"] == 130 and done["processed"] == 130


def test_workflow_name_conflicts_are_409(world):
    api = world.api
    assert api.post(f"{T}/workflows", json={"name": "Plain", "steps": [STEP]}).status_code == 409
    assert api.post(f"{T}/workflows", json={"name": "  PLAIN  ", "steps": [STEP]}).status_code == 409      # case and spaces
    other = ok(api.post(f"{T}/workflows", json={"name": "Straße", "steps": [STEP]}))
    assert api.post(f"{T}/workflows", json={"name": "STRASSE", "steps": [STEP]}).status_code == 409         # casefold
    assert api.patch(f"{T}/workflows/{other['id']}", json={"name": "plain"}).status_code == 409
    assert api.put(f"{T}/workflows/{other['id']}", json={"name": "plain", "steps": [STEP]}).status_code == 409
    assert api.post(f"{T}/workflows/{other['id']}/duplicate", json={"name": "plain"}).status_code == 409
    assert ok(api.patch(f"{T}/workflows/{other['id']}", json={"name": "STRASSE"}))["name"] == "STRASSE"      # keeping its own name is fine
    assert ok(api.put(f"{T}/workflows/{other['id']}", json={"name": "Straße", "steps": [STEP]}))["name"] == "Straße"
    assert api.post(f"{T}/workflows/{other['id']}/duplicate", json={"name": ""}).status_code == 422
    assert api.post(f"{T}/workflows/{other['id']}/duplicate", json={"name": "n" * 81}).status_code == 422
    assert api.post(f"{T}/workflows/{other['id']}/duplicate", json={"name": 5}).status_code == 422
    ok(api.delete(f"{T}/workflows/{other['id']}"))
    assert ok(world.get("/workflows")) and len(ok(world.get("/workflows"))) == 3         # Plain, Holding, Quick


def test_duplicate_names_stay_within_80_characters_and_do_not_collide(world):
    api = world.api
    long = ok(api.post(f"{T}/workflows", json={"name": "L" * 80, "steps": [STEP]}))
    names = [ok(api.post(f"{T}/workflows/{long['id']}/duplicate"))["name"] for _ in range(3)]
    assert len(set(names)) == 3 and all(len(n) <= 80 for n in names), names
    body = [ok(api.post(f"{T}/workflows/{long['id']}/duplicate", json=None))["name"]]
    assert len(set(names + body)) == 4
    for w in ok(world.get("/workflows")):
        if w["name"].startswith("L" * 20):
            ok(api.delete(f"{T}/workflows/{w['id']}"))


def test_bulk_status_ignores_unknown_ids_and_chunks_large_lists(world):
    ids = world.chats_a[:3]
    r = ok(world.api.post(f"{T}/chats/bulk-status", json={"ids": ids + [999999, 888888, -4, 0], "status": "paused"}))
    assert r == {"updated": 3}
    many = world.chats_a + list(range(2_000_000, 2_005_000))
    assert ok(world.api.post(f"{T}/chats/bulk-status", json={"ids": many, "status": "pending"})) == {"updated": 130}
    assert ok(world.api.post(f"{T}/chats/bulk-status", json={"ids": ids * 3, "status": "pending"}))["updated"] == 3      # duplicates
    assert ok(world.get("/chats/summary", account_id=world.a["id"]))["by_status"]["pending"] == 130


def test_error_reason_is_cleared_when_a_chat_leaves_the_error_state(world):
    cid = world.chats_a[5]
    ok(world.api.patch(f"{T}/chats/{cid}", json={"chat_status": "error"}))
    ok(world.api.patch(f"{T}/chats/{cid}", json={"chat_status": "pending"}))
    assert ok(world.get(f"/chats/{cid}"))["error_reason"] == ""


def test_media_in_use_cannot_be_deleted(world):
    name = ok(world.api.post(f"{T}/media", files=[("files", ("p.jpg", jpeg_bytes(3)))]))["saved"][0]["name"]
    wf = ok(world.api.post(f"{T}/workflows", json={"name": "WithPic", "steps": [{"type": "image", "file": name, "pause_after": 0}]}))
    r = world.api.delete(f"{T}/media/{name}")
    assert r.status_code == 409 and "WithPic" in r.json()["detail"]
    assert world.api.get(f"{T}/media/{name}").status_code == 200
    ok(world.api.delete(f"{T}/workflows/{wf['id']}"))
    ok(world.api.delete(f"{T}/media/{name}"))
    assert world.api.delete(f"{T}/media/{name}").status_code == 404


# --- media upload negatives -----------------------------------------------------------------------------------

def upload(api, *files):
    return api.post(f"{T}/media", files=[("files", f) for f in files])


def media_files(app):
    d = app.storage / "telegram" / "media"
    return sorted(p.name for p in d.iterdir()) if d.exists() else []


def test_upload_negatives(world):
    api = world.api
    before = media_files(world.app)
    assert api.post(f"{T}/media").status_code == 422                                      # no files at all
    assert api.post(f"{T}/media", data={"files": "text"}).status_code == 422             # a form field, not a file
    assert api.post(f"{T}/media", json={"files": []}).status_code == 422
    cases = {
        "empty.jpg": b"", "text.jpg": b"hello world, I am not an image", "noext": jpeg_bytes(1), "dot.": jpeg_bytes(1),
        "x.exe": b"MZ" + b"\0" * 100, "x.jpg.exe": jpeg_bytes(1), "png-as-jpg.jpg": jpeg_bytes(1, fmt="PNG"),
        "jpg-as-png.png": jpeg_bytes(1), "damaged.jpg": jpeg_bytes(1)[:200], "svg.jpg": b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
        "html.jpg": b"<html><script>alert(1)</script></html>", ".jpg": jpeg_bytes(1), "a" * 3000 + ".jpg": jpeg_bytes(1),
        "x.php": b"<?php echo 1;", "zero.ogg": b"\0" * 64, "gif.gif": b"GIF89a" + b"\0" * 100,
    }
    for name, data in cases.items():
        r = upload(api, (name, data))
        assert r.status_code in (413, 422, 200), f"{name[:20]!r}: {r.status_code} {r.text[:150]}"
        if name in ("noext", "dot.", "x.exe", "x.jpg.exe", "text.jpg", "empty.jpg", "png-as-jpg.jpg", "jpg-as-png.png", "damaged.jpg",
                    "svg.jpg", "html.jpg", "x.php", "zero.ogg", "gif.gif"):
            assert r.status_code == 422, f"{name!r} must be refused, got {r.status_code} {r.text[:150]}"
    assert media_files(world.app) == before, "a refused upload must leave no file behind"


def test_upload_too_large_is_413_and_leaves_nothing(world):
    before = media_files(world.app)
    r = upload(world.api, ("big.jpg", b"\xff\xd8\xff" + b"\0" * (10 * 1024 * 1024)))
    assert r.status_code == 413, f"{r.status_code} {r.text[:200]}"
    assert media_files(world.app) == before


def test_upload_mixed_batch_reports_each_file(world):
    r = ok(upload(world.api, ("good.jpg", jpeg_bytes(7)), ("bad.jpg", b"nope"), ("good2.png", jpeg_bytes(8, fmt="PNG"))))
    assert [s["kind"] for s in r["saved"]] == ["image", "image"]
    assert [x["filename"] for x in r["rejected"]] == ["bad.jpg"] and isinstance(r["rejected"][0]["error"], str)
    for s in r["saved"]:
        ok(world.api.delete(f"{T}/media/{s['name']}"))


@pytest.mark.parametrize("filename", ["../../evil.jpg", "..\\..\\evil.jpg", "/etc/passwd.jpg", "C:\\x\\y.jpg", "фото 🎉.jpg", "a b'c\"d;e.jpg",
                                      "x.jpg\u0000.png", "%2e%2e%2fx.jpg", "CON.jpg", "<script>.jpg", "x" * 200 + ".jpg", "UPPER.JPG", "a.jpeg"])
def test_upload_filenames_never_reach_the_disk(world, filename):
    before = set(media_files(world.app))
    r = upload(world.api, (filename, jpeg_bytes(2)))
    assert r.status_code in (200, 422), f"{r.status_code} {r.text[:150]}"
    after = set(media_files(world.app))
    if r.status_code == 200:
        name = r.json()["saved"][0]["name"]
        assert name.startswith("img-") and name.endswith(".jpg") and "/" not in name and "\\" not in name
        assert after - before == {name}
        assert world.api.get(f"{T}/media/{name}").headers["content-type"] == "image/jpeg"
        ok(world.api.delete(f"{T}/media/{name}"))
    else:
        assert after == before
    assert not (world.app.storage / "evil.jpg").exists() and not (world.app.storage / "telegram" / "evil.jpg").exists()


def test_media_download_headers(world):
    name = ok(upload(world.api, ("p.jpg", jpeg_bytes(4))))["saved"][0]["name"]
    r = world.api.get(f"{T}/media/{name}")
    assert r.headers["content-type"] == "image/jpeg" and r.headers["x-content-type-options"] == "nosniff"
    assert r.content[:3] == b"\xff\xd8\xff"
    ok(world.api.delete(f"{T}/media/{name}"))


def test_media_cleanup_and_unused_bounds(make_app):
    app = make_app(**ENV)
    api = app.client()
    name = ok(upload(api, ("p.jpg", jpeg_bytes(5))))["saved"][0]["name"]
    for bad in ("-1", "525601", "x", "", "1.5"):
        assert api.get(f"{T}/media/unused", params={"min_age_minutes": bad}).status_code == 422, bad
    assert ok(api.get(f"{T}/media/unused", params={"min_age_minutes": 60})) == {"items": [], "bytes": 0}      # too young
    young = ok(api.get(f"{T}/media/unused", params={"min_age_minutes": 0}))
    assert [i["name"] for i in young["items"]] == [name] and young["bytes"] == young["items"][0]["size"] > 0
    assert ok(api.post(f"{T}/media/cleanup", json={"min_age_minutes": 60})) == {"deleted": 0, "bytes": 0}
    assert ok(api.post(f"{T}/media/cleanup", json={})) == {"deleted": 0, "bytes": 0}                            # default 60 minutes
    assert ok(api.get(f"{T}/media"))[0]["name"] == name
    assert ok(api.post(f"{T}/media/cleanup", json={"min_age_minutes": 0}))["deleted"] == 1
    assert ok(api.get(f"{T}/media")) == []


def test_media_listing_ignores_foreign_files(make_app):
    app = make_app(**ENV)
    api = app.client()
    d = app.storage / "telegram" / "media"
    ok(api.get(f"{T}/media"))
    d.mkdir(parents=True, exist_ok=True)
    for junk in ("notes.txt", "img-short.jpg", "IMG-" + "A" * 32 + ".jpg", "img-" + "0" * 32 + ".exe", ".hidden"):
        (d / junk).write_bytes(b"x")
    assert ok(api.get(f"{T}/media")) == []
    assert ok(api.get(f"{T}/media/unused", params={"min_age_minutes": 0}))["items"] == []
    assert ok(api.post(f"{T}/media/cleanup", json={"min_age_minutes": 0}))["deleted"] == 0
    assert (d / "notes.txt").exists()


# --- SQL-looking input in filters ------------------------------------------------------------------------------

@pytest.mark.parametrize("q", ["'", "\"", "'; DROP TABLE tg_chat;--", "' OR '1'='1", "\\", "\\\\", "%", "%%", "_", "[a-z]", "(", ")", "*", "?", ".*",
                               "🎉", "Ünal", "ÜNAL", "ünal", "ß", pytest.param("x" * 20000, id="20k-x"), " ", "@", "@special5"])
def test_search_text_is_a_literal_not_a_pattern_or_sql(world, q):
    r = world.get("/chats", q=q, limit=1000)
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    items = r.json()["items"]
    assert r.json()["total"] == len(items)
    needle = q.strip().lstrip("@").casefold()
    for c in items:
        hay = " ".join([c["display_name"], c["username"]]).casefold()
        assert needle in hay or needle in (c["username"] or "").casefold() or not needle, (q, c["display_name"])
    assert world.get("/status").json()["chats"] == 260


def test_search_text_with_a_nul_character_is_harmless(world):
    r = world.get("/chats", q="a\u0000b", limit=1)
    assert r.status_code == 200 and world.get("/status").status_code == 200


def test_search_wildcards_match_only_themselves(world):
    names = lambda q: sorted(c["display_name"] for c in ok(world.get("/chats", q=q, account_id=world.a["id"], limit=1000))["items"])  # noqa: E731
    assert names("%") == ["100% Bob"]                    # not "everything"
    assert names("a_b") == ["a_b"]                       # _ is not "any one character"
    assert names("a%b") == []
    assert names("\\") == ["back\\slash"]
    assert names("ÜNAL") == ["Ünal Çelik"] and names("ünal") == ["Ünal Çelik"]
    assert names("'; drop table") == ["'; DROP TABLE tg_chat;--"]
    assert names("🎉") == ["🎉 Party 🎉"]
    assert names("привет") == ["Привет мир"]
    assert names("@special1") == ["100% Bob"] and names("SPECIAL1") == ["100% Bob"]


@pytest.mark.parametrize("status", ["bogus", "pending,bogus", "DONE", " done", "done ", "pending;", "'", "done,,bogus", "🎉", "x" * 5000])
def test_chat_status_filter_rejects_unknown_values(world, status):
    for path in ("/chats", "/chats/ids"):
        assert world.get(path, status=status).status_code == 422, (path, status)


def test_chat_status_filter_accepts_lists_and_empty_parts(world):
    total = ok(world.get("/chats", limit=1))["total"]
    assert ok(world.get("/chats", status="pending,,done,error,in_progress,paused", limit=1))["total"] == total
    assert ok(world.get("/chats", status=",", limit=1))["total"] == total
    assert ok(world.get("/chats", status="done,done", limit=1))["total"] == 0


@pytest.mark.parametrize("value", ["garbage", "2026-13-45", "2026-02-30", "", "'; --", "yesterday", "2026-03-01T25:00", "🎉", "x" * 1000, "NaN",
                                   "0000-00-00", "2026-03-01T10:00:00+99:00"])
def test_date_filters_reject_garbage(world, value):
    if value == "":       # an empty filter means "no filter"
        assert world.get("/chats", date_from=value).status_code == 200
        return
    for path in ("/chats", "/chats/ids", "/runs", "/runs/export.csv"):
        for key in ("date_from", "date_to"):
            assert world.get(path, **{key: value}).status_code == 422, (path, key, value)


@pytest.mark.parametrize("value", ["0001-01-01T00:00:00+14:00", "9999-12-31T23:59:59-05:00", "9999-12-31", "0001-01-01", "0001-01-01T00:00:00-12:00"])
def test_extreme_dates_do_not_crash(world, value):
    for path in ("/chats", "/chats/ids", "/runs", "/runs/export.csv"):
        for key in ("date_from", "date_to"):
            r = world.get(path, **{key: value})
            assert r.status_code in (200, 422), f"{path} {key}={value} -> {r.status_code} {r.text[:100]}"


def test_date_filter_semantics(world):
    cid = lambda r: r["total"]  # noqa: E731
    day = (BASE - timedelta(days=0)).date().isoformat()
    assert ok(world.get("/chats", date_from="2999-01-01"))["total"] == 0
    assert ok(world.get("/chats", date_to="1999-01-01"))["total"] == 0
    assert ok(world.get("/chats", date_from="2999-01-01", date_to="1999-01-01"))["total"] == 0           # reversed range: empty, not an error
    every = ok(world.get("/chats", limit=1))["total"]
    assert ok(world.get("/chats", date_from="1999-01-01", date_to="2999-01-01"))["total"] == every
    assert ok(world.get("/chats", date_to=day))["total"] >= 1                                              # a bare date as upper bound covers the day
    # +01:00 offsets are honoured
    assert ok(world.get("/chats", date_from="2026-03-01T13:00:00+01:00", date_to="2026-03-01T13:00:00+01:00"))["total"] == \
        ok(world.get("/chats", date_from="2026-03-01T12:00:00Z", date_to="2026-03-01T12:00:00Z"))["total"]
    assert cid(ok(world.get("/runs", date_from="2999-01-01"))) == 0


# --- 3. response shapes ------------------------------------------------------------------------------------------

def collect_responses(world):
    """JSON of every read route, after making sure there is something in each of them."""
    run = world.new_run(world.wf, ids=world.chats_a[:3])
    wait_until(lambda: ok(world.get(f"/runs/{run['id']}"))["status"] == "done", timeout=30, msg="run done")
    name = ok(upload(world.api, ("p.jpg", jpeg_bytes(6))))["saved"][0]["name"]
    docs = {}
    for path, params in [("/status", {}), ("/settings", {}), ("/accounts", {}), ("/chats", {"limit": 5}), (f"/chats/{world.chats_a[0]}", {}),
                         ("/chats/ids", {"account_id": world.a["id"]}), ("/chats/summary", {}), ("/workflows", {}),
                         (f"/workflows/{world.wf['id']}", {}), ("/runs", {}), (f"/runs/{run['id']}", {}), (f"/runs/{run['id']}/chats", {}),
                         ("/stats", {}), ("/stats", {"account_id": world.a["id"]}), ("/media", {}), ("/media/unused", {"min_age_minutes": 0})]:
        r = world.get(path, **params)
        assert r.status_code == 200, (path, r.text[:200])
        docs[path + json.dumps(params)] = r
    docs["media-delete"] = world.api.delete(f"{T}/media/{name}")
    return docs, run


def test_no_secrets_in_any_response(world):
    docs, run = collect_responses(world)
    docs["settings-put"] = world.api.put(f"{T}/settings", json=CREDS)
    docs["patch-account"] = world.api.patch(f"{T}/accounts/{world.a['id']}", json={"label": "Test 0001"})
    docs["connect"] = world.api.post(f"{T}/accounts/{world.a['id']}/connect")
    docs["patch-chat"] = world.api.patch(f"{T}/chats/{world.chats_a[0]}", json={"notes": ""})
    docs["bad-settings"] = world.api.put(f"{T}/settings", json={"api_id": 0, "api_hash": CREDS["api_hash"]})
    docs["bad-start"] = world.api.post(f"{T}/accounts/start", json={"phone": "x", **CREDS})
    docs["bad-code"] = world.api.post(f"{T}/accounts/{world.a['id']}/code", json={"code": "abcdef0123456789"})
    docs["run-csv"] = world.api.get(f"{T}/runs/{run['id']}/export.csv")
    docs["runs-csv"] = world.api.get(f"{T}/runs/export.csv")
    session = sqlite_value(world, "select session_string from tg_account where id = ?", world.a["id"])
    assert session and CREDS["api_hash"] not in ""
    for key, r in docs.items():
        assert CREDS["api_hash"] not in r.text, f"{key} leaks the api hash"
        assert session not in r.text and "fake:" not in r.text, f"{key} leaks the session string"
        if r.headers.get("content-type", "").startswith("application/json"):
            for path, k, v in walk(r.json()):
                assert k not in SECRET_KEYS, f"{key}: {path}/{k}"
    hint = ok(world.get("/settings"))
    assert hint["api_hash_hint"] == "…" + CREDS["api_hash"][-4:] and set(hint) == {"api_id", "api_hash_hint", "configured"}


def sqlite_value(world, sql, *args):
    import sqlite3
    con = sqlite3.connect(world.app.storage / "db.sqlite")
    try:
        row = con.execute(sql, args).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def test_the_api_hash_is_not_leaked_by_error_responses_either(world):
    for r in (world.api.post(f"{T}/accounts/start", json={"phone": PHONE, "api_id": 1, "api_hash": "SECRET-HASH-123"}),   # online -> 409
              world.api.post(f"{T}/accounts/start", json={"phone": "+4915100000009", "api_id": 1, "api_hash": "SECRET-HASH-123"}),
              world.api.post(f"{T}/accounts/start", json={"phone": "", "api_id": 1, "api_hash": "SECRET-HASH-123"}),
              world.api.put(f"{T}/settings", json={"api_id": "x", "api_hash": "SECRET-HASH-123"})):
        assert "SECRET-HASH-123" not in r.text, r.text
    assert ok(world.get("/settings"))["api_hash_hint"] == "…" + CREDS["api_hash"][-4:]       # a refused start did not store it
    assert "+4915100000009" not in accounts(world.api)


def test_every_timestamp_is_iso_utc_or_null(world):
    docs, _ = collect_responses(world)
    seen = 0
    for key, r in docs.items():
        for path, k, v in walk(r.json()):
            if k.endswith("_at"):
                if v is None:
                    continue
                assert isinstance(v, str) and v.endswith("Z"), f"{key} {path}/{k} = {v!r}"
                parsed = datetime.fromisoformat(v)
                assert parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0)
                seen += 1
            if k == "date":
                datetime.strptime(v, "%Y-%m-%d")
    assert seen > 20


def test_csv_exports_have_a_stable_shape(world):
    run = world.new_run(world.wf, ids=world.chats_a[:3])
    wait_until(lambda: ok(world.get(f"/runs/{run['id']}"))["status"] == "done", timeout=30, msg="run done")
    for url in (f"{T}/runs/export.csv", f"{T}/runs/{run['id']}/export.csv"):
        r = world.api.get(url)
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
        assert r.text.startswith("\ufeff") and 'filename="' in r.headers["content-disposition"]
        assert "\n" not in r.headers["content-disposition"] and "/" not in r.headers["content-disposition"].split("filename=")[1]
        assert len(r.text.strip().splitlines()) >= 2


def test_same_thing_has_the_same_fields_everywhere(world):
    api = world.api
    # accounts
    keys = lambda d: set(d)  # noqa: E731
    listed = ok(world.get("/accounts"))[0]
    for variant in (ok(api.patch(f"{T}/accounts/{world.a['id']}", json={"label": "Test 0001"})), ok(api.post(f"{T}/accounts/{world.a['id']}/connect")),
                    ok(api.post(f"{T}/accounts/{world.b['id']}/disconnect"))):
        assert keys(variant) == keys(listed)
    for a in ok(world.get("/accounts")):
        assert isinstance(a["id"], int) and isinstance(a["chats"], int) and a["status"] in ("offline", "connecting", "online", "error")
        assert isinstance(a["has_session"], bool) and isinstance(a["login_pending"], bool) and "sync" in a
    # chats
    one = ok(world.get(f"/chats/{world.chats_a[0]}"))
    assert keys(ok(world.get("/chats", limit=1))["items"][0]) == keys(one) == keys(ok(api.patch(f"{T}/chats/{one['id']}", json={})))
    assert one["chat_status"] in ("pending", "in_progress", "done", "error", "paused") and isinstance(one["messages_sent"], int)
    assert isinstance(one["id"], int) and isinstance(one["account_id"], int)
    # workflows
    w = ok(world.get(f"/workflows/{world.wf['id']}"))
    shapes = [ok(world.get("/workflows"))[0], w, ok(api.patch(f"{T}/workflows/{w['id']}", json={"name": "Plain"})),
              ok(api.put(f"{T}/workflows/{w['id']}", json={"name": "Plain", "steps": [STEP]}))]
    dup = ok(api.post(f"{T}/workflows/{w['id']}/duplicate"))
    shapes.append(dup)
    assert len({frozenset(s) for s in shapes}) == 1 and set(w) == {"id", "name", "steps", "media", "created_at", "updated_at"}
    ok(api.delete(f"{T}/workflows/{dup['id']}"))
    # runs
    run = world.new_run()
    shapes = [run, ok(world.get(f"/runs/{run['id']}")), ok(world.get("/runs"))["items"][0], ok(api.post(f"{T}/runs/{run['id']}/pause")),
              ok(api.post(f"{T}/runs/{run['id']}/resume")), ok(world.get("/stats"))["active_run"], ok(api.post(f"{T}/runs/{run['id']}/stop"))]
    assert len({frozenset(s) for s in shapes}) == 1, [set(s) ^ set(shapes[0]) for s in shapes]
    r = shapes[-1]
    assert 0 <= r["percent"] <= 100 and r["processed"] <= r["total"] and r["success"] + r["errors"] <= r["processed"] + 1
    assert all(isinstance(r[k], int) for k in ("id", "account_id", "total", "processed", "success", "errors", "skipped", "steps_total"))
    assert ok(world.get("/stats"))["last_run"].keys() == r.keys()


def test_deletes_and_cancels_answer_ok_true(world):
    w = ok(world.api.post(f"{T}/workflows", json={"name": "ToDelete", "steps": [STEP]}))
    assert ok(world.api.delete(f"{T}/workflows/{w['id']}")) == {"ok": True}
    run = world.new_run()
    ok(world.api.post(f"{T}/runs/{run['id']}/stop"))
    assert ok(world.api.delete(f"{T}/runs/{run['id']}")) == {"ok": True}
    assert ok(world.api.post(f"{T}/accounts/{world.a['id']}/cancel")) == {"ok": True}


def test_every_error_response_is_json_with_a_detail(world):
    responses = [world.api.get(f"{T}/chats/999999"), world.api.get(f"{T}/chats", params={"limit": 0}), world.api.post(f"{T}/workflows", json={}),
                 world.api.get(f"{T}/nope"), world.api.delete(f"{T}/workflows/999999"), world.api.put(f"{T}/chats"),
                 world.api.get(f"{T}/runs/export.csv", params={"status": "bogus"}), world.api.get(f"{T}/media/..")]
    for r in responses:
        assert r.status_code in (404, 405, 422), (r.request.url, r.status_code)
        assert r.headers["content-type"].startswith("application/json") and "detail" in r.json()
        assert "Traceback" not in r.text and "sqlalchemy" not in r.text.lower() and "\\modules\\" not in r.text


def test_manual_errors_have_a_plain_english_string_detail(world):
    cases = [world.api.get(f"{T}/chats/999999"), world.api.patch(f"{T}/chats/{world.chats_a[0]}", json={"chat_status": "bogus"}),
             world.api.post(f"{T}/workflows", json={"name": "", "steps": [STEP]}), world.api.post(f"{T}/workflows", json={"name": "Plain", "steps": [STEP]}),
             world.api.get(f"{T}/runs", params={"status": "bogus"}), world.api.post(f"{T}/accounts/start", json={"phone": "12"}),
             world.api.post(f"{T}/runs", json={"account_id": world.b["id"], "workflow_id": world.wf["id"], "chat_ids": world.chats_b[:1]})]
    for r in cases:
        d = r.json()["detail"]
        assert isinstance(d, str) and d and d.isascii() or "Straße" in d, d     # English, no German (the panel translates)
        assert d[0].isupper(), d


def test_status_matches_the_lists(world):
    s = ok(world.get("/status"))
    assert s["module"] == "telegram"
    assert s["accounts"] == len(ok(world.get("/accounts"))) and s["accounts_online"] == sum(a["status"] == "online" for a in ok(world.get("/accounts")))
    assert s["chats"] == ok(world.get("/chats", limit=1))["total"] == ok(world.get("/chats/summary"))["total"] == len(ok(world.get("/chats/ids"))["ids"])
    assert s["runs"] == ok(world.get("/runs", limit=1))["total"]
    assert ok(world.get("/stats"))["chats"]["total"] == s["chats"] and ok(world.get("/stats"))["runs"] == s["runs"]


def test_stats_shape(world):
    st = ok(world.get("/stats", days=14))
    assert set(st) == {"accounts", "accounts_online", "chats", "runs", "sends", "active_run", "last_run", "per_day"}
    assert set(st["chats"]) == {"total", "unprocessed", "processed", "errors", "in_progress", "paused"}
    assert st["chats"]["total"] == sum(v for k, v in st["chats"].items() if k != "total")
    assert set(st["sends"]) == {"successful", "failed", "messages"} and all(isinstance(v, int) and v >= 0 for v in st["sends"].values())
    assert len(st["per_day"]) == 14 and all(set(d) == {"date", "successful", "failed"} for d in st["per_day"])
    dates = [d["date"] for d in st["per_day"]]
    assert dates == sorted(dates) and len(set(dates)) == 14
    assert datetime.strptime(dates[-1], "%Y-%m-%d").date() == datetime.now(timezone.utc).date()
    one = ok(world.get("/stats", account_id=world.b["id"]))
    assert one["chats"]["total"] == 130 and one["runs"] == 0 and one["active_run"] is None and one["last_run"] is None
    assert one["sends"] == {"successful": 0, "failed": 0, "messages": 0}


def test_chat_summary_adds_up(world):
    for acc in (None, world.a["id"], world.b["id"], 999999):
        s = ok(world.get("/chats/summary", **({"account_id": acc} if acc else {})))
        assert set(s["by_status"]) == {"pending", "in_progress", "done", "error", "paused"}
        assert s["total"] == sum(s["by_status"].values())
    assert ok(world.get("/chats/summary", account_id=999999))["total"] == 0


# --- 4. pagination ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/chats", "/runs", "/runs/{run}/chats"])
@pytest.mark.parametrize("params,ok_", [({"limit": 1}, True), ({"limit": 0}, False), ({"limit": -1}, False), ({"limit": "x"}, False),
                                        ({"limit": ""}, False), ({"limit": 1.5}, False), ({"offset": -1}, False), ({"offset": "x"}, False),
                                        ({"offset": 0}, True), ({"offset": 10 ** 12}, True), ({"limit": 10 ** 9}, False), ({"limit": "1e3"}, False)])
def test_limit_and_offset_bounds(world, path, params, ok_):
    run = world.new_run(world.wf, ids=world.chats_a[:3])
    r = world.get(path.replace("{run}", str(run["id"])), **params)
    assert r.status_code == (200 if ok_ else 422), f"{path} {params}: {r.status_code} {r.text[:150]}"


@pytest.mark.parametrize("path,top", [("/chats", 1000), ("/runs", 500), ("/runs/{run}/chats", 1000)])
def test_the_largest_allowed_page_and_one_more(world, path, top):
    run = world.new_run(world.wf, ids=world.chats_a[:3])
    path = path.replace("{run}", str(run["id"]))
    assert world.get(path, limit=top).status_code == 200
    assert world.get(path, limit=top + 1).status_code == 422
    assert world.get(path, limit=1).status_code == 200


def test_offset_beyond_the_end_is_an_empty_page_with_the_real_total(world):
    total = ok(world.get("/chats", limit=1))["total"]
    assert total == 260
    for offset in (total, total + 1, 10 ** 9):
        page = ok(world.get("/chats", offset=offset))
        assert page == {"total": total, "items": []}
    last = ok(world.get("/chats", offset=total - 1, limit=50))
    assert len(last["items"]) == 1 and last["total"] == total
    assert ok(world.get("/runs", offset=10 ** 6)) == {"total": ok(world.get("/runs", limit=1))["total"], "items": []}


def test_defaults_are_100_chats_and_50_runs(world):
    assert len(ok(world.get("/chats"))["items"]) == 100
    for _ in range(3):
        world.new_run(world.wf, ids=world.chats_a[:1])
        wait_until(lambda: not ok(world.get("/runs", status="running"))["total"], timeout=20, msg="run done")


@pytest.mark.parametrize("sort", ["id", "last_contact_at", "first_contact_at", "display_name", "chat_status", "messages_sent"])
@pytest.mark.parametrize("order", ["asc", "desc"])
@pytest.mark.parametrize("size", [1, 7, 130])
def test_pages_are_disjoint_and_complete_for_every_sort(world, sort, order, size):
    acc = world.a["id"]
    total = ok(world.get("/chats", account_id=acc, limit=1))["total"]
    assert total == 130
    seen, offset, pages = [], 0, 0
    while True:
        page = ok(world.get("/chats", account_id=acc, sort=sort, order=order, limit=size, offset=offset))
        assert page["total"] == total
        assert len(page["items"]) <= size
        seen += [c["id"] for c in page["items"]]
        offset += size
        pages += 1
        if not page["items"] or pages > 200:
            break
    assert len(seen) == len(set(seen)) == total, f"{sort} {order} size {size}: duplicates or gaps across pages"
    assert set(seen) == set(world.chats_a)


def test_sort_directions_are_really_applied(world):
    acc = world.a["id"]
    ids = lambda **kw: [c["id"] for c in ok(world.get("/chats", account_id=acc, limit=1000, **kw))["items"]]  # noqa: E731
    assert ids(sort="id", order="asc") == sorted(world.chats_a)
    assert ids(sort="id", order="desc") == sorted(world.chats_a, reverse=True)
    dates = [c["last_contact_at"] for c in ok(world.get("/chats", account_id=acc, limit=1000, sort="last_contact_at", order="desc"))["items"]]
    assert dates == sorted(dates, reverse=True)
    dates = [c["last_contact_at"] for c in ok(world.get("/chats", account_id=acc, limit=1000, sort="last_contact_at", order="asc"))["items"]]
    assert dates == sorted(dates)
    assert ids() == ids(sort="last_contact_at", order="desc")                      # the documented default
    names = [c["display_name"] for c in ok(world.get("/chats", account_id=acc, limit=1000, sort="display_name", order="asc"))["items"]]
    assert names.index("Alice Müller") < names.index("Ünal Çelik") < names.index("Привет мир")


@pytest.mark.parametrize("params", [{"sort": "bogus"}, {"sort": ""}, {"sort": "id; DROP TABLE tg_chat"}, {"sort": "search_text"},
                                    {"sort": "access_hash"}, {"sort": "ID"}, {"order": "bogus"}, {"order": ""}, {"order": "ASC"},
                                    {"order": "asc; --"}, {"sort": "id,display_name"}])
def test_sort_and_order_accept_only_the_listed_values(world, params):
    assert world.get("/chats", **params).status_code == 422
    assert world.get("/status").status_code == 200


def test_filtering_and_paging_agree_with_the_id_list(world):
    acc = world.a["id"]
    ok(world.api.post(f"{T}/chats/bulk-status", json={"ids": world.chats_a[:17], "status": "done"}))
    try:
        ids = ok(world.get("/chats/ids", account_id=acc, status="done"))
        listed = ok(world.get("/chats", account_id=acc, status="done", limit=1000))
        assert ids["total"] == listed["total"] == 17 == len(ids["ids"]) == len(listed["items"])
        assert sorted(ids["ids"]) == sorted(c["id"] for c in listed["items"])
        assert ids["ids"] == sorted(ids["ids"])
        assert ok(world.get("/chats/summary", account_id=acc))["by_status"]["done"] == 17
        assert ok(world.get("/chats", account_id=acc, status="done", q="user", limit=1))["total"] <= 17
    finally:
        ok(world.api.post(f"{T}/chats/bulk-status", json={"ids": world.chats_a, "status": "pending"}))


def test_run_list_pagination_and_filters(world):
    api = world.api
    for _ in range(6):
        run = world.new_run(world.wf, ids=world.chats_a[:1])
        wait_until(lambda: ok(world.get(f"/runs/{run['id']}"))["status"] == "done", timeout=20, msg="run done")
    total = ok(world.get("/runs", limit=1))["total"]
    assert total >= 6
    seen = []
    for offset in range(0, total, 4):
        seen += [r["id"] for r in ok(world.get("/runs", limit=4, offset=offset))["items"]]
    assert len(seen) == len(set(seen)) == total and seen == sorted(seen, reverse=True)           # newest first, no gaps
    stopped = ok(world.get("/runs", status="stopped", limit=1))["total"]
    assert ok(world.get("/runs", status="done", limit=500))["total"] == total - stopped
    assert ok(world.get("/runs", status="running,paused", limit=500))["total"] == 0
    assert ok(world.get("/runs", status="stopped,error", limit=500))["total"] <= total
    assert ok(world.get("/runs", account_id=world.b["id"]))["total"] == 0
    assert ok(world.get("/runs", workflow_id=world.wf["id"], limit=500))["total"] >= 6
    assert ok(world.get("/runs", date_from="2999-01-01"))["total"] == 0
    assert ok(world.get("/runs", date_to="1999-01-01"))["total"] == 0
    rid = seen[0]
    listing = ok(world.get(f"/runs/{rid}/chats", limit=1000))
    assert listing["total"] == len(listing["items"]) == 1
    assert ok(world.get(f"/runs/{rid}/chats", status="done"))["total"] == 1
    assert ok(world.get(f"/runs/{rid}/chats", status="error"))["total"] == 0
    assert ok(world.get(f"/runs/{rid}/chats", status="bogus"))["total"] == 0                     # unknown names just match nothing
    assert ok(world.get(f"/runs/{rid}/chats", offset=1)) == {"total": 1, "items": []}
    assert api.get(f"{T}/runs", params={"status": "queued,bogus"}).status_code == 422


def test_run_chats_keep_their_order_across_pages(world):
    big = ok(world.api.post(f"{T}/workflows", json={"name": "Quick2", "steps": [STEP]}))
    order = list(reversed(world.chats_a[:40]))
    run = world.new_run(big, ids=order)
    wait_until(lambda: ok(world.get(f"/runs/{run['id']}"))["status"] == "done", timeout=60, msg="run done")
    got = []
    for offset in range(0, 40, 9):
        got += [i["chat_id"] for i in ok(world.get(f"/runs/{run['id']}/chats", limit=9, offset=offset))["items"]]
    assert got == order
    positions = [i["position"] for i in ok(world.get(f"/runs/{run['id']}/chats", limit=1000))["items"]]
    assert positions == list(range(40))


def test_stats_days_bounds(world):
    for days, expect in ((1, 200), (14, 200), (90, 200), (0, 422), (-1, 422), (91, 422), (10 ** 9, 422), ("x", 422), ("", 422), (1.5, 422)):
        r = world.get("/stats", days=days)
        assert r.status_code == expect, (days, r.status_code)
        if expect == 200:
            assert len(r.json()["per_day"]) == int(days)


def test_runs_cleanup_bounds_and_semantics(world):
    before = ok(world.get("/runs", limit=1))["total"]
    for days, expect in ((1, 200), (36500, 200), (0, 422), (-5, 422), (36501, 422)):
        assert world.api.post(f"{T}/runs/cleanup", json={"days": days}).status_code == expect, days
    assert ok(world.api.post(f"{T}/runs/cleanup", json={"days": 1})) == {"deleted": 0}          # nothing is a day old
    run = world.new_run()                                                                         # an active run is never swept
    assert ok(world.api.post(f"{T}/runs/cleanup", json={"days": 1}))["deleted"] == 0
    assert ok(world.get("/runs", limit=1))["total"] == before + 1


def test_chat_id_list_has_no_paging_but_is_complete(world):
    ids = ok(world.get("/chats/ids"))
    assert ids["total"] == len(ids["ids"]) == 260 and len(set(ids["ids"])) == 260
    assert world.get("/chats/ids", limit=5).status_code == 200          # unknown query parameters are ignored
    assert len(ok(world.get("/chats/ids", limit=5))["ids"]) == 260


def test_deleting_an_account_removes_everything_of_it_and_nothing_else(make_app):
    app = make_app(**ENV)
    api = app.client()
    a = link(api, PHONE)
    ok(api.post(f"{T}/accounts/{a['id']}/disconnect"))
    assert ok(api.delete(f"{T}/accounts/{a['id']}")) == {"ok": True}
    assert ok(api.get(f"{T}/accounts")) == [] and ok(api.get(f"{T}/status"))["chats"] == 0
    assert api.delete(f"{T}/accounts/{a['id']}").status_code == 404


def test_server_log_of_the_shared_server_has_no_tracebacks(world):
    """Runs last in this file (pytest keeps definition order): every refusal above must have been a handled error."""
    assert world.app.tracebacks() == 0, world.app.log.read_text(errors="replace")[-4000:]
