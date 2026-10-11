"""Bot-module system: registry, manifest, auth, table creation."""

import sqlite3

import httpx

from conftest import ok

TG_TABLES = {"tg_account", "tg_chat", "tg_workflow", "tg_run", "tg_run_chat"}


def test_manifest_lists_telegram(api):
    mods = ok(api.get("/api/modules"))
    assert [m["key"] for m in mods] == ["telegram"]
    assert mods[0]["title"] == "Telegram"
    assert mods[0]["panel"] == "/modules-static/telegram/panel.js" and mods[0]["color"] == "#229ED9"
    assert [n["tab"] for n in mods[0]["nav"]] == ["dashboard", "accounts", "chats", "workflows", "runs", "history"]
    assert all({"de", "en"} <= set(n["label"]) for n in mods[0]["nav"])


def test_panel_script_is_served_uncached(api):
    r = api.get("/modules-static/telegram/panel.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]
    assert r.headers["cache-control"] == "no-cache"
    assert "PanelModules.telegram" in r.text
    assert api.get("/modules-static/telegram/models.py").status_code == 404   # only the panel file is public


def test_module_routes_need_login(app):
    anon = httpx.Client(base_url=app.url)
    assert anon.get("/api/telegram/status").status_code in (401, 403)
    assert anon.get("/api/modules").status_code in (401, 403)


def test_telegram_status_empty(api):
    st = ok(api.get("/api/telegram/status"))
    assert st == {"module": "telegram", "accounts": 0, "accounts_online": 0, "chats": 0, "runs": 0}


def test_tables_created_and_module_storage_dir(app, api):
    ok(api.get("/api/telegram/status"))
    with sqlite3.connect(app.storage / "db.sqlite") as db:
        names = {r[0] for r in db.execute("select name from sqlite_master where type='table'")}
    assert TG_TABLES <= names
    assert "account" in names   # the Jaumo tables are untouched
    assert (app.storage / "telegram").is_dir()


def test_unknown_module_websocket_rejected(app):
    import pytest
    from websockets.sync.client import connect
    with pytest.raises(Exception):
        with connect(app.url.replace("http", "ws") + "/ws/modules/nope") as ws:
            ws.recv(timeout=2)
