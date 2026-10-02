"""One Jaumo configuration: APK keys from env vars (fallback: stored profile), main-config choice, partial saves."""

import sqlite3

from conftest import jpeg_bytes, ok, setup_ready, wait_runs_done

UA = "Android 202609.1.4 (1001864) (GooglePlay;Free)"
ENV = {"JAUMO_CLIENT_ID": "other-client", "JAUMO_SIGN_SECRET": "other-secret", "JAUMO_USER_AGENT": UA}


def _photos(api, n):
    files = [("files", (f"p{i}.jpg", jpeg_bytes(i), "image/jpeg")) for i in range(n)]
    ok(api.post("/api/photos", files=files))


def _no_proxy(api):
    ok(api.put("/api/config", json={"settings": {"require_proxy": False, "max_swipes": 1}}))


def test_env_keys_sign_every_request(make_app, jaumo):
    api = make_app(**ENV).client()
    c = ok(api.get("/api/config"))
    assert c["apk_source"] == "env" and c["apk"]["client_id"] == "other-client"
    assert "sign_secret" not in c["apk"] and c["apk"]["sign_secret_hint"].endswith("cret")
    _photos(api, 1)
    _no_proxy(api)
    run = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]
    assert run["status"] == "done", run
    st = jaumo.state()
    assert st["bad_signatures"] == [] and {r["client"] for r in st["requests"] if r.get("client")} == {"other-client"}


def test_without_env_the_stored_profile_is_used(app, api, jaumo):
    assert ok(api.get("/api/config"))["apk_source"] == "none"
    setup_ready(api, photos=1, max_swipes=1)          # stores "Good APK" on the main configuration
    c = ok(api.get("/api/config"))
    assert c["apk_source"] == "stored" and c["apk"]["client_id"] == "good-client"
    run = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]
    assert run["status"] == "done", run


def test_upgrade_keeps_last_used_config_and_switches_to_env_keys(make_app, jaumo, tmp_path):
    storage = tmp_path / "server"
    old = make_app(storage=storage)
    api = old.client()
    setup_ready(api, photos=2, max_swipes=1)
    apk_id = ok(api.get("/api/configs"))[0]["apk_profile_id"]
    other = ok(api.post("/api/configs", json={"name": "Second", "apk_profile_id": apk_id,
                                              "settings": {**ok(api.get("/api/configs"))[0]["settings"], "max_swipes": 2}}))
    wait_runs_done(api, ok(api.post("/api/runs", json={"config_id": other["id"], "count": 1}))["run_ids"])
    old.stop()
    # the deployed (old) code never stored a main configuration — remove it to get the same database
    with sqlite3.connect(storage / "db.sqlite") as db:
        db.execute("DELETE FROM appsetting WHERE key = 'main_config_id'")

    api = make_app(storage=storage, **ENV).client()
    c = ok(api.get("/api/config"))
    assert c["id"] == other["id"], "the configuration used last stays the one"
    assert c["apk_source"] == "env" and c["apk"]["client_id"] == "other-client"
    run = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]
    assert run["status"] == "done" and run["config_id"] == other["id"]


def test_partial_save_keeps_other_fields(app, api):
    before = ok(api.get("/api/config"))["settings"]
    after = ok(api.put("/api/config", json={"settings": {"max_swipes": 3, "location_radius_km": 12}}))["settings"]
    assert after["max_swipes"] == 3 and after["location_radius_km"] == 12
    assert {k: v for k, v in after.items() if k not in ("max_swipes", "location_radius_km")} == \
        {k: v for k, v in before.items() if k not in ("max_swipes", "location_radius_km")}
    r = api.put("/api/config", json={"settings": {"like_ratio": 5}})
    assert r.status_code == 422 and "like_ratio" in r.json()["detail"]
    r = api.put("/api/config", json={"settings": {"relationship_search": "DATING"}})
    assert r.status_code == 422, "only the APK's relationship values"
    assert ok(api.get("/api/config"))["settings"]["like_ratio"] == before["like_ratio"]


def test_messaging_without_config_id_uses_the_main_config(app, api, jaumo):
    setup_ready(api, photos=1, max_swipes=0)
    r = api.post("/api/messages", json={"account_ids": []})
    assert r.status_code == 422 and "Messaging is turned off" in r.json()["detail"]
    ok(api.put("/api/config", json={"settings": {"messaging_enabled": True, "message_templates": ["Hi"]}}))
    assert ok(api.post("/api/messages", json={"account_ids": []}))["run_ids"] == [], "no accounts with matches yet"
