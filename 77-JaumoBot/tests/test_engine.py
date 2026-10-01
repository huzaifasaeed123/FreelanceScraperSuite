"""Engine (bot) tests: request layer fidelity and every signup / swipe / messaging path."""

import threading
import time
from urllib.parse import urlencode

import pytest

from bot.engine import SIGNUP_PHOTO_URLS, BotRunner, JaumoClient, MessageRunner, jaumo_urlencode
from conftest import FAST_DELAYS, jpeg_bytes
from fake_jaumo import _orig_urlencode, reference_signature

APK = {"client_id": "good-client", "sign_secret": "good-secret", "user_agent": "Android 202609.1.4 (1001864) (GooglePlay;Free)"}


@pytest.fixture
def photo(tmp_path):
    p = tmp_path / "girl.jpg"
    p.write_bytes(jpeg_bytes(3))
    return str(p)


class Recorder:
    def __init__(self):
        self.events = []

    def __call__(self, kind, data):
        self.events.append((kind, data))

    def kinds(self, kind):
        return [d for k, d in self.events if k == kind]

    def steps(self):
        return [d["step"] for d in self.kinds("step")]


def runner(photo, jaumo, emit, **settings):
    s = {"delays": FAST_DELAYS, "max_swipes": 8, **settings}
    r = BotRunner(s, APK, photo, emit=emit)
    r.client.base_url = jaumo.base
    return r


# --- request layer ----------------------------------------------------------------

@pytest.mark.parametrize("s", ["", "a b+c*~/?&=", "äöü€", "https://api.jaumo.com/v2/me?x=1&y=2"])
def test_urlencode_matches_original(s):
    assert jaumo_urlencode(s) == _orig_urlencode(s)


@pytest.mark.parametrize("method,path,token,body", [
    ("GET", "me", "tok-123", b""),
    ("POST", "auth/token", "", b"grant_type=client_credentials&client_id=x"),
    ("PUT", "https://api.jaumo.com/v2/zapping/like/77", "abc/=+", b""),
    ("POST", "signup/city/bycoordinates?longitude=13.4050&latitude=52.5200", "t", "äöü".encode()),
])
def test_signature_matches_original_algorithm(method, path, token, body):
    c = JaumoClient(APK, base_url="https://api.jaumo.com/v2")
    full = path if path.startswith("http") else "https://api.jaumo.com/v2/" + path
    assert c.compute_signature(method, path, token, body) == reference_signature("good-secret", method, full, token, body)


def test_headers_match_original_shape():
    c = JaumoClient(APK, device_info={"manufacturer": "samsung", "model": "SM-S911B", "brand": "samsung"})
    h = c.make_headers("GET", "https://api.jaumo.com/v2/me", access_token="tok")
    assert h["Jaumo-Package-Id"] == "com.jaumo"
    assert h["Jaumo-Client-Token"] == "good-client"
    assert h["User-Agent"] == APK["user_agent"]
    assert h["Jaumo-Device"] == "samsung;SM-S911B;samsung"
    assert h["Jaumo-Os"] == "14" and h["Accept-Language"] == "en_US"
    assert h["Authorization"] == "Bearer tok"
    assert "Authorization" not in c.make_headers("GET", "https://api.jaumo.com/v2/me")


def test_clients_are_isolated_per_instance():
    """Parallel bots must never share proxy, device or credentials (the old script used module globals)."""
    a = JaumoClient(APK, proxy_url="http://u:p@1.1.1.1:1")
    b = JaumoClient({**APK, "client_id": "other-client", "sign_secret": "other-secret"}, proxy_url="http://u:p@2.2.2.2:2")
    assert a.proxies != b.proxies and a.device_id != b.device_id and a.client_id != b.client_id


# --- full signup + swipe flow ------------------------------------------------------

def test_happy_path_signup_swipe(jaumo, photo):
    rec = Recorder()
    res = runner(photo, jaumo, rec).run()
    st = jaumo.state()
    assert res == {"status": "done", "reason": "max swipes reached (8)"}
    assert st["bad_signatures"] == [] and st["bad_headers"] == []
    assert rec.steps() == ["client_token", "signup", "location", "profile", "photo", "verify", "swiping", "finished"]
    acc = rec.kinds("account_created")[0]["account"]
    assert acc["gender"] == 2 and acc["looking_for_gender"] == 1 and acc["status"] == "signing_up"
    assert acc["photo"] == "girl.jpg" and acc["access_token"] and acc["refresh_token"]
    updates = rec.kinds("account_update")
    assert any(u.get("jaumo_id") for u in updates), "jaumo user id must be captured from /me"
    assert any(u.get("status") == "active" and u.get("photo_uploaded") for u in updates)
    swipes = rec.kinds("swipe")
    assert len(swipes) == 8
    likes = [s for s in swipes if s["action"] == "like"]
    assert len(likes) == len(st["likes"]) and len(swipes) - len(likes) == len(st["dislikes"])
    assert sum(s["matched"] for s in swipes) == sum(1 for i in range(1, len(likes) + 1) if i % 3 == 0)
    # one device identity for the whole account
    devices = {r["device"] for r in st["requests"] if r["path"] != "/ip"}
    assert len(devices) == 1
    assert rec.kinds("apk_check") == [{"ok": True}]
    assert st["uploads"][0]["valid_multipart"]


def test_signup_payload_identical_to_original_defaults(jaumo, photo):
    rec = Recorder()
    r = runner(photo, jaumo, rec, max_swipes=1)
    r.name = "Anna"
    r.run()
    reg = jaumo.state()["registrations"][0]
    f = reg["form"]
    original_order = ["gender", "birthday", "looking_for_gender", "photo_url", "name", "relationship_search",
                      "dating_relationship_search", "allow_in_all_brands", "location_permission", "notifications_services"]
    expected = urlencode({k: f[k] for k in original_order})
    assert reg["raw"] == expected, "signup body must keep the original field order/values"
    assert f["gender"] == "2" and f["looking_for_gender"] == "1" and f["name"] == "Anna"
    assert f["relationship_search"] == "FLIRT" == f["dating_relationship_search"], "default is FLIRT"
    assert f["allow_in_all_brands"] == "1" and f["location_permission"] == "" == f["notifications_services"]
    assert f["photo_url"] == "https://i.jaumo.com/gallery_orig/113550,0339ee18d142fbf39e.jpg" == SIGNUP_PHOTO_URLS[0]


@pytest.mark.parametrize("rel,dating", [("FLIRT", "FLIRT"), ("FRIENDSHIP", "FRIENDSHIP"), ("FLIRT", "FRIENDSHIP")])
def test_relationship_values_reach_jaumo_unchanged(jaumo, photo, rel, dating):
    rec = Recorder()
    res = runner(photo, jaumo, rec, max_swipes=1, relationship_search=rel, dating_relationship_search=dating).run()
    assert res["status"] == "done", res
    f = jaumo.state()["registrations"][0]["form"]
    assert (f["relationship_search"], f["dating_relationship_search"]) == (rel, dating)
    acc = rec.kinds("account_created")[0]["account"]
    assert (acc["relationship_search"], acc["dating_relationship_search"]) == (rel, dating)


def test_unknown_relationship_value_is_rejected_by_app(jaumo, photo):
    res = runner(photo, jaumo, Recorder(), max_swipes=1, relationship_search="DATING").run()
    assert res == {"status": "failed", "reason": "signup failed"}


def test_signup_defaults_are_reported(jaumo, photo):
    rec = Recorder()
    runner(photo, jaumo, rec, max_swipes=1).run()
    sd = rec.kinds("signup_defaults")
    assert len(sd) == 1 and sd[0]["data"]["relationship_search"]["items"][0]["value"] == "FLIRT"


def test_signup_details_from_settings(jaumo, photo):
    runner(photo, jaumo, Recorder(), max_swipes=1, looking_for_gender=2, relationship_search="FRIENDSHIP",
           dating_relationship_search="FRIENDSHIP", allow_in_all_brands=False).run()
    f = jaumo.state()["registrations"][0]["form"]
    assert (f["looking_for_gender"], f["relationship_search"], f["dating_relationship_search"], f["allow_in_all_brands"]) == ("2", "FRIENDSHIP", "FRIENDSHIP", "0")


def test_age_range_respected(jaumo, photo):
    for _ in range(5):
        r = runner(photo, jaumo, Recorder(), age_min=25, age_max=26)
        year = int(r.make_profile()["birthday"][:4])
        assert time.gmtime().tm_year - 26 <= year <= time.gmtime().tm_year - 25


def test_blocked_after_consecutive_failures(jaumo, photo):
    jaumo.control(block_after_likes=2)
    rec = Recorder()
    res = runner(photo, jaumo, rec, max_swipes=0, like_ratio=1.0, block_threshold=3).run()
    assert res["status"] == "blocked" and "403" in res["reason"]
    assert len(rec.kinds("swipe")) == 2
    assert {"status": "blocked"} in rec.kinds("account_update")


def test_runs_until_cards_run_out(jaumo, photo):
    jaumo.control(batches=2, cards_per_batch=3)
    rec = Recorder()
    res = runner(photo, jaumo, rec, max_swipes=0, max_empty_batches=2).run()
    assert res == {"status": "done", "reason": "no more cards"}
    assert len(rec.kinds("swipe")) == 6


def test_zapping_errors_count_as_block(jaumo, photo):
    jaumo.control(zapping_status=403)
    res = runner(photo, jaumo, Recorder(), max_swipes=0, block_threshold=2).run()
    assert res["status"] == "blocked" and "zapping HTTP 403" in res["reason"]


@pytest.mark.parametrize("uses", [10, 15])  # expiry during swiping (handled by the original like/dislike retry)
def test_expired_token_is_refreshed_and_continues(jaumo, photo, uses):
    jaumo.control(access_token_uses=uses)
    rec = Recorder()
    res = runner(photo, jaumo, rec, max_swipes=12).run()
    assert res["status"] == "done", res
    assert len(rec.kinds("swipe")) == 12
    refreshed = [u for u in rec.kinds("account_update") if "access_token" in u]
    assert len(refreshed) >= 1, "refreshes must be reported so the DB keeps the newest token"


def test_photo_warning_stops_before_swiping(jaumo, photo):
    jaumo.control(photo_warning=True)
    rec = Recorder()
    res = runner(photo, jaumo, rec).run()
    assert res["status"] == "failed" and "photo" in res["reason"]
    assert rec.kinds("swipe") == [] and {"status": "photo_failed", "photo_uploaded": False} in rec.kinds("account_update")
    assert jaumo.state()["likes"] == []


def test_missing_compliance_link(jaumo, photo):
    jaumo.control(no_compliance_link=True)
    res = runner(photo, jaumo, Recorder()).run()
    assert res["status"] == "failed"


def test_missing_photo_file(jaumo, tmp_path):
    res = runner(str(tmp_path / "nope.jpg"), jaumo, Recorder()).run()
    assert res["status"] == "failed"


def test_banned_apk_reports_health(jaumo, photo):
    rec = Recorder()
    r = BotRunner({"delays": FAST_DELAYS}, {**APK, "client_id": "banned-client", "sign_secret": "banned-secret"}, photo, emit=rec)
    r.client.base_url = jaumo.base
    res = r.run()
    assert res["status"] == "failed" and "HTTP 401" in res["reason"]
    chk = rec.kinds("apk_check")
    assert len(chk) == 1 and chk[0]["ok"] is False and "401" in chk[0]["error"]
    assert rec.kinds("account_created") == []


def test_signup_rejected(jaumo, photo):
    jaumo.control(signup_fail=True)
    rec = Recorder()
    res = runner(photo, jaumo, rec).run()
    assert res == {"status": "failed", "reason": "signup failed"} and rec.kinds("account_created") == []


def test_network_error_is_reported_not_raised(photo):
    r = BotRunner({"delays": FAST_DELAYS, "request_timeout": 5}, APK, photo, emit=Recorder())
    r.client.base_url = "http://127.0.0.1:9/v2"
    res = r.run()
    assert res["status"] == "failed" and "network error" in res["reason"]


def test_stop_interrupts_long_delay(jaumo, photo):
    ev = threading.Event()
    rec = Recorder()
    r = BotRunner({"delays": {**FAST_DELAYS, "between_swipes": [30, 30]}, "max_swipes": 0}, APK, photo, emit=rec, stop_event=ev)
    r.client.base_url = jaumo.base
    out = {}
    t = threading.Thread(target=lambda: out.update(r.run()))
    t.start()
    while not rec.kinds("swipe"):
        time.sleep(0.05)
    t0 = time.time()
    ev.set()
    t.join(5)
    assert not t.is_alive() and time.time() - t0 < 2
    assert out["status"] == "stopped"
    assert {"status": "active"} in rec.kinds("account_update"), "an account that finished setup stays active after stop"


# --- messaging runner ---------------------------------------------------------------

def _account_from_signup(jaumo, photo):
    rec = Recorder()
    runner(photo, jaumo, rec, max_swipes=9, like_ratio=1.0).run()
    a = rec.kinds("account_created")[0]["account"]
    matches = [s["user_id"] for s in rec.kinds("swipe") if s["matched"]]
    assert matches, "fake server matches every 3rd like"
    return {**a, "id": 1, "matches": matches, "messaged": []}


def test_message_runner_sends_to_unmessaged_matches(jaumo, photo):
    acc = _account_from_signup(jaumo, photo)
    acc["messaged"] = acc["matches"][:1]
    rec = Recorder()
    res = MessageRunner({"delays": FAST_DELAYS, "message_templates": ["Hallo!"]}, APK, acc, emit=rec)
    res.client.base_url = jaumo.base
    out = res.run()
    sent = rec.kinds("message")
    assert out["status"] == "done" and [m["user_id"] for m in sent] == acc["matches"][1:]
    assert all(m["ok"] and m["text"] == "Hallo!" for m in sent)
    assert [m["to"] for m in jaumo.state()["messages"]] == acc["matches"][1:]
    assert jaumo.state()["bad_signatures"] == []


def test_message_runner_falls_back_to_messages_endpoint(jaumo, photo):
    acc = _account_from_signup(jaumo, photo)
    jaumo.control(header_message_fail=True)
    m = MessageRunner({"delays": FAST_DELAYS}, APK, acc, emit=Recorder())
    m.client.base_url = jaumo.base
    assert m.run()["status"] == "done"
    assert {x["via"] for x in jaumo.state()["messages"]} == {"messages"}


def test_message_runner_reuses_device_and_handles_legacy(jaumo, photo):
    acc = _account_from_signup(jaumo, photo)
    legacy = {**acc, "device_info": None}
    rec = Recorder()
    m = MessageRunner({"delays": FAST_DELAYS}, APK, legacy, emit=rec)
    m.client.base_url = jaumo.base
    m.run()
    assert m.client.device_id == acc["device_id"], "same Jaumo-Device-Id as at signup"
    assert any("device_info" in u for u in rec.kinds("account_update")), "legacy account gets a stored device model"


def test_message_runner_without_pending_matches(jaumo, photo):
    acc = _account_from_signup(jaumo, photo)
    acc["messaged"] = list(acc["matches"])
    m = MessageRunner({"delays": FAST_DELAYS}, APK, acc, emit=Recorder())
    m.client.base_url = jaumo.base
    assert m.run() == {"status": "done", "reason": "no unmessaged matches"}
