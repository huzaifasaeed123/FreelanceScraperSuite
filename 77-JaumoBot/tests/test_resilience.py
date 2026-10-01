"""Resilience: restarts, old databases, imports, photo library, validation, cleanup and guards."""

import io
import json
import os
import sqlite3
import time
import zipfile

import pytest

from conftest import ROOT, jpeg_bytes, ok, setup_ready, wait_runs_done, wait_until

SLOW = {k: [0.3, 0.4] for k in ("after_signup", "after_location", "after_refresh", "after_profile", "before_photo",
                                 "after_photo", "between_swipes", "between_batches", "before_message")}


def launch(api, cid, count=1):
    return ok(api.post("/api/runs", json={"config_id": cid, "count": count}))["run_ids"]


# --- restarts ---------------------------------------------------------------------------

@pytest.mark.parametrize("kill", [True, False], ids=["crash", "graceful"])
def test_restart_mid_run_marks_interrupted_and_recovers(make_app, tmp_path, jaumo, kill):
    storage = tmp_path / "st"
    app = make_app(storage=storage)
    api = app.client()
    cid = setup_ready(api, photos=4, max_swipes=0, delays=SLOW)
    ok(api.put("/api/settings", json={"bot": {"parallel_accounts": 1}}))
    ids = launch(api, cid, 3)
    wait_until(lambda: ok(api.get(f"/api/runs/{ids[0]}"))["account_id"], msg="account created")
    app.stop(kill=kill)

    app2 = make_app(storage=storage)
    api2 = app2.client()
    runs = [ok(api2.get(f"/api/runs/{i}")) for i in ids]
    assert [r["status"] for r in runs] == ["interrupted"] * 3
    acc = ok(api2.get(f"/api/accounts/{runs[0]['account_id']}"))
    assert acc["status"] in ("failed", "active") and not acc["working"]
    s = ok(api2.get("/api/stats"))
    assert s["running"] == 0 and s["queued"] == 0
    assert ok(api2.get("/api/settings"))["bot"]["parallel_accounts"] == 1, "settings survive restarts"
    # interrupted runs no longer hold names/photos; new work starts normally
    conf = ok(api2.get("/api/configs"))[0]
    ok(api2.put(f"/api/configs/{cid}", json={"name": conf["name"], "apk_profile_id": conf["apk_profile_id"],
                                              "settings": {**conf["settings"], "max_swipes": 2,
                                                           "delays": {k: [0, 0.01] for k in SLOW}}}))
    new = wait_runs_done(api2, launch(api2, cid, 2))
    assert all(r["status"] == "done" for r in new)


def test_old_database_is_migrated(make_app, tmp_path, jaumo):
    storage = tmp_path / "old"
    storage.mkdir()
    db = sqlite3.connect(storage / "db.sqlite")
    db.executescript("""
        CREATE TABLE apkprofile (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL UNIQUE, client_id VARCHAR NOT NULL,
            sign_secret VARCHAR NOT NULL, user_agent VARCHAR NOT NULL, package_id VARCHAR NOT NULL,
            os_version VARCHAR NOT NULL, accept_language VARCHAR NOT NULL, created_at DATETIME NOT NULL);
        INSERT INTO apkprofile VALUES (1, 'Old APK', 'good-client', 'good-secret', 'UA', 'com.jaumo', '14', 'en_US', '2026-09-01 10:00:00');
        CREATE TABLE account (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, status VARCHAR NOT NULL, location VARCHAR NOT NULL,
            created_at DATETIME NOT NULL, liked_count INTEGER NOT NULL, disliked_count INTEGER NOT NULL,
            matches_count INTEGER NOT NULL, messages_sent INTEGER NOT NULL);
        INSERT INTO account VALUES (1, 'Oldie', 'active', 'Berlin', '2026-09-01 10:00:00', 12, 4, 2, 1);
    """)
    db.commit()
    db.close()
    api = make_app(storage=storage).client()
    a = ok(api.get("/api/accounts"))["items"][0]
    assert (a["name"], a["liked_count"], a["worker"], a["jaumo_id"], a["messages_received"]) == ("Oldie", 12, None, None, None)
    assert a["actions"] == 17 and a["state"] == "active"
    apk = ok(api.get("/api/apk-profiles"))[0]
    assert apk["name"] == "Old APK" and apk["enabled"] is True and apk["fail_streak"] == 0
    assert ok(api.get("/api/accounts/summary"))["likes"] == 12


def test_legacy_accounts_import_once(make_app, tmp_path, jaumo):
    storage = tmp_path / "leg"
    storage.mkdir()
    rows = [{"created": "2026-09-20T10:00:00+00:00", "android_id": f"aid{i}", "device_id": f"dev{i}", "access_token": "a",
             "refresh_token": "r", "location": "Hamburg", "liked": ["1", "2"], "disliked": ["3"], "matches": ["2"],
             "messages_sent": 0, "name": f"Leg{i}", "gender": 2, "birthday": "1995-01-01", "looking_for_gender": 1,
             "photo_url": "x"} for i in range(3)]
    (storage / "accounts.txt").write_text("\n".join(json.dumps(r) for r in rows) + "\n\n{broken json\n", encoding="utf-8")
    app = make_app(storage=storage)
    api = app.client()
    items = ok(api.get("/api/accounts"))["items"]
    assert len(items) == 3 and {a["status"] for a in items} == {"legacy"} and {a["liked_count"] for a in items} == {2}
    assert not (storage / "accounts.txt").exists() and (storage / "accounts.txt.imported").exists()
    app.stop()
    api2 = make_app(storage=storage).client()
    assert ok(api2.get("/api/accounts"))["total"] == 3, "restart must not import twice"


# --- photo library ----------------------------------------------------------------------

def _img(fmt, size=(800, 1000), seed=1):
    return jpeg_bytes(seed, size, fmt)


def test_photo_upload_formats_zip_duplicates_and_errors(api):
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as z:
        z.writestr("set/a.png", _img("PNG", seed=10))
        z.writestr("set/b.webp", _img("WEBP", seed=11))
        z.writestr("set/dup.jpg", _img("JPEG", seed=10))   # same picture as a.png? different encoding -> new
        z.writestr("__MACOSX/set/._a.png", b"junk")
        z.writestr("set/readme.txt", b"hi")
    files = [("files", ("one.jpg", _img("JPEG", seed=1), "image/jpeg")),
             ("files", ("one-again.jpg", _img("JPEG", seed=1), "image/jpeg")),
             ("files", ("huge.png", _img("PNG", (3000, 2400), seed=2), "image/png")),
             ("files", ("tiny.jpg", _img("JPEG", (100, 100), seed=3), "image/jpeg")),
             ("files", ("notes.pdf", b"%PDF-1.4", "application/pdf")),
             ("files", ("broken.jpg", b"\xff\xd8garbage", "image/jpeg")),
             ("files", ("pack.zip", zbuf.getvalue(), "application/zip"))]
    res = ok(api.post("/api/photos", files=files))
    by = {r["name"]: r for r in res["results"]}
    assert by["one.jpg"]["status"] == "saved" and by["one-again.jpg"]["status"] == "duplicate"
    assert by["tiny.jpg"]["status"] == "error" and "too small" in by["tiny.jpg"]["detail"]
    assert by["notes.pdf"]["status"] == "error" and by["broken.jpg"]["status"] == "error"
    assert by["pack.zip › set/a.png"]["status"] == "saved" and by["pack.zip › set/b.webp"]["status"] == "saved"
    assert not any("readme" in n or "MACOSX" in n for n in by)
    photos = {p["name"]: p for p in ok(api.get("/api/photos"))}
    assert max(photos["huge.jpg"]["width"], photos["huge.jpg"]["height"]) == 1600
    assert all(p["status"] == "available" for p in photos.values())
    for name in photos:
        assert api.get(f"/api/photos/{name}/thumb").status_code == 200
        assert api.get(f"/api/photos/{name}/file").headers["content-type"] == "image/jpeg"
    # re-upload of an existing picture is detected across requests
    again = ok(api.post("/api/photos", files=[("files", ("x.jpg", _img("JPEG", seed=1), "image/jpeg"))]))
    assert again["duplicate"] == 1


def test_photo_path_traversal_and_delete_rules(app, api, jaumo):
    cid = setup_ready(api, photos=3, max_swipes=1)
    for bad in ("..%2Fdb.sqlite", "..%5C..%5Cdb.sqlite", "%2E%2E%2Fserver.log"):
        assert api.get(f"/api/photos/{bad}/file").status_code == 404
    run = wait_runs_done(api, launch(api, cid, 1))[0]
    assert api.delete(f"/api/photos/{run['photo']}").status_code == 409, "used photos are kept"
    free = [p["name"] for p in ok(api.get("/api/photos")) if p["status"] == "available"]
    res = ok(api.post("/api/photos/bulk-delete", json={"names": free + [run["photo"]]}))
    assert sorted(res["deleted"]) == sorted(free) and res["blocked"] == [run["photo"]]
    assert [p["name"] for p in ok(api.get("/api/photos"))] == [run["photo"]]
    assert not list((app.storage / "photos").glob(free[0]))


def test_photos_copied_into_volume_are_registered(make_app, tmp_path, jaumo):
    storage = tmp_path / "vol"
    (storage / "photos").mkdir(parents=True)
    (storage / "photos" / "manual.jpg").write_bytes(jpeg_bytes(42))
    api = make_app(storage=storage).client()
    p = ok(api.get("/api/photos"))
    assert [x["name"] for x in p] == ["manual.jpg"] and p[0]["status"] == "available"
    assert api.get("/api/photos/manual.jpg/thumb").status_code == 200


# --- validation & guards ------------------------------------------------------------------

def test_input_validation(app, api, jaumo):
    cid = setup_ready(api, photos=1)
    conf = ok(api.get("/api/configs"))[0]
    base = {"name": conf["name"], "apk_profile_id": conf["apk_profile_id"]}
    bad_settings = [
        {"delays": {**conf["settings"]["delays"], "between_swipes": [5, 1]}},
        {"age_min": 40, "age_max": 30},
        {"age_min": 16},
        {"locations": []},
        {"like_ratio": 1.5},
        {"relationship_search": "friendship; drop"},
        {"looking_for_gender": 3},
        {"name_source": "custom", "name_pool": []},
    ]
    for override in bad_settings:
        r = api.put(f"/api/configs/{cid}", json={**base, "settings": {**conf["settings"], **override}})
        assert r.status_code == 422, override
    for body in ({"bot": {"parallel_accounts": 0}}, {"bot": {"parallel_accounts": 21}}):
        assert api.put("/api/settings", json=body).status_code == 422
    for count in (0, 501):
        assert api.post("/api/runs", json={"config_id": cid, "count": count}).status_code == 422
    assert api.post("/api/runs", json={"config_id": 9999, "count": 1}).status_code == 404
    assert api.post("/api/configs", json={"name": conf["name"]}).status_code == 409
    assert api.post("/api/proxies/bulk", json={"text": "not a proxy"}).status_code == 422
    assert api.post("/api/apk-profiles", json={"name": "x", "client_id": "a", "user_agent": "u"}).status_code == 422
    assert api.post("/api/login", json={"username": "admin", "password": "wrong"}).status_code == 401
    assert ok(api.get("/api/configs"))[0]["settings"] == conf["settings"], "rejected updates change nothing"


def test_config_without_apk_cannot_launch(app, api, jaumo):
    cid = ok(api.get("/api/configs"))[0]["id"]
    r = api.post("/api/runs", json={"config_id": cid, "count": 1})
    assert r.status_code == 422 and "APK" in r.json()["detail"]


def test_delete_guards_and_log_cleanup(app, api, jaumo):
    cid = setup_ready(api, photos=3, max_swipes=0, delays={**SLOW, "between_swipes": [1, 1]})
    rid = launch(api, cid, 1)[0]
    acc = wait_until(lambda: ok(api.get(f"/api/runs/{rid}"))["account_id"], msg="account")
    assert api.delete(f"/api/accounts/{acc}").status_code == 409, "account with active session"
    assert api.delete(f"/api/runs/{rid}").status_code == 409, "active run"
    ok(api.post(f"/api/runs/{rid}/stop"))
    wait_runs_done(api, [rid])
    assert ok(api.get(f"/api/runs/{rid}/logs"))
    ok(api.post("/api/runs/cleanup", json={"days": 0}))
    assert ok(api.get(f"/api/runs/{rid}/logs")) == [] and ok(api.get(f"/api/runs/{rid}"))["status"] == "stopped"
    ok(api.delete(f"/api/accounts/{acc}"))
    assert api.get(f"/api/accounts/{acc}").status_code == 404
    assert ok(api.get(f"/api/accounts/{acc}/events")) == []


def test_outdated_server_is_detected(app, api):
    assert ok(api.get("/api/version")) == {"outdated": False}
    src = ROOT / "api" / "schemas.py"
    st = src.stat()
    try:
        os.utime(src, (st.st_atime, time.time() + 5))
        assert ok(api.get("/api/version")) == {"outdated": True}
    finally:
        os.utime(src, (st.st_atime, st.st_mtime))
    assert ok(api.get("/api/version")) == {"outdated": False}
