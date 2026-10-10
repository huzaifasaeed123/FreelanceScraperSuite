"""Telegram workflows and media (backend): CRUD, the validation matrix, step order, upload rules, serving,
deleting, malicious file names and the ogg/opus conversion (a stand-in ffmpeg always, the real one when installed)."""

import json
import os
import shutil
import sqlite3
import stat
import struct
import sys
import wave
from pathlib import Path

import httpx
import pytest

from conftest import jpeg_bytes, ok
from test_telegram_accounts import ENV

W = "/api/telegram/workflows"
M = "/api/telegram/media"
HAS_FFMPEG = shutil.which("ffmpeg") is not None


# --- sample files ---------------------------------------------------------------

def _ogg_crc(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte << 24
        for _ in range(8):
            crc = ((crc << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if crc & 0x80000000 else (crc << 1) & 0xFFFFFFFF
    return crc


def _ogg_page(payload: bytes, granule: int, seq: int, flags: int) -> bytes:
    head = b"OggS" + struct.pack("<BBqIIIB", 0, flags, granule, 1, seq, 0, 1) + bytes([len(payload)])
    page = head + payload
    return page[:22] + struct.pack("<I", _ogg_crc(page)) + page[26:]


def ogg_opus(seconds: float = 3.0, pre_skip: int = 312) -> bytes:
    """A structurally valid OGG/Opus stream whose last page says it lasts `seconds`."""
    opus_head = b"OpusHead" + struct.pack("<BBHIhB", 1, 1, pre_skip, 48000, 0, 0)
    return (_ogg_page(opus_head, 0, 0, 2) + _ogg_page(b"OpusTags" + b"\0" * 8, 0, 1, 0)
            + _ogg_page(b"\xf8" + b"\0" * 40, int(seconds * 48000) + pre_skip, 2, 4))


def ogg_vorbis() -> bytes:
    return _ogg_page(b"\x01vorbis" + b"\0" * 20, 0, 0, 2)


MP3 = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x00" * 200
M4A = b"\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00M4A mp42" + b"\0" * 100
AAC = b"\xff\xf1\x50\x80" + b"\0" * 100


def wav_bytes(seconds=1.0) -> bytes:
    import io
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x10\x20" * int(8000 * seconds))
    return buf.getvalue()


def png():
    return jpeg_bytes(1, (60, 40), "PNG")


def webp():
    return jpeg_bytes(2, (60, 40), "WEBP")


def jpg():
    return jpeg_bytes(3, (60, 40))


# --- helpers --------------------------------------------------------------------

@pytest.fixture
def tg(make_app):
    app = make_app(**ENV)
    return app, app.client()


def upload(api, *files):
    """files: (filename, bytes) pairs"""
    return api.post(M, files=[("files", (n, d, "application/octet-stream")) for n, d in files])


def up(api, filename, data):
    r = upload(api, (filename, data))
    return ok(r, 200)["saved"][0]


def media_files(app):
    d = app.storage / "telegram" / "media"
    return sorted(p.name for p in d.iterdir()) if d.exists() else []


def text(content="Hallo", pause=0):
    return {"type": "text", "content": content, "pause_after": pause}


def create(api, name="Ablauf", steps=None, status=None):
    r = api.post(W, json={"name": name, "steps": steps if steps is not None else [text()]})
    return ok(r, status)


def detail(r):
    return r.json()["detail"]


def db_exec(app, sql, args=()):
    with sqlite3.connect(app.storage / "db.sqlite") as c:
        return c.execute(sql, args).lastrowid


def add_run(app, workflow_id, status, steps=(), name="Lauf"):
    return db_exec(app, "INSERT INTO tg_run (account_id, workflow_id, workflow_name, workflow_snapshot, status, total_chats,"
                        " processed, success, errors, current_step_index, on_error, created_at)"
                        " VALUES (1, ?, ?, ?, ?, 1, 0, 0, 0, 0, 'next', '2026-01-01 00:00:00')",
                   (workflow_id, name, json.dumps({"name": name, "steps": list(steps)}), status))


# --- access ---------------------------------------------------------------------

def test_every_workflow_and_media_route_needs_login(tg):
    app, _ = tg
    anon = httpx.Client(base_url=app.url)
    name = "img-" + "0" * 32 + ".jpg"
    calls = [("GET", W), ("POST", W), ("GET", W + "/1"), ("PUT", W + "/1"), ("PATCH", W + "/1"),
             ("POST", W + "/1/duplicate"), ("DELETE", W + "/1"),
             ("GET", M), ("POST", M), ("GET", f"{M}/{name}"), ("DELETE", f"{M}/{name}")]
    for method, url in calls:
        r = anon.request(method, url, json={})
        assert r.status_code in (401, 403), (method, url, r.status_code)


# --- workflow CRUD --------------------------------------------------------------

def test_the_three_example_workflows_of_the_brief(tg):
    app, api = tg
    voice, image = up(api, "memo.ogg", ogg_opus(4))["name"], up(api, "bild.png", png())["name"]
    v = lambda p=0: {"type": "voice", "file": voice, "pause_after": p}   # noqa: E731
    i = lambda p=0: {"type": "image", "file": image, "pause_after": p}   # noqa: E731
    flows = {
        "Workflow 1 - Neukontakt": [v(60), text("Hi, schön dich kennenzulernen", 30), i(0)],
        "Workflow 2 - Follow-up": [text("Na, wie geht's?", 10), i(20), v(0)],
        "Workflow 3 - Ohne Pause": [v(), text("Kurz noch etwas"), i(), v()],
    }
    for name, steps in flows.items():
        made = create(api, name, steps)
        assert made["steps"] == steps and made["name"] == name
    listed = ok(api.get(W))
    assert [w["name"] for w in listed] == list(flows)
    for w, steps in zip(listed, flows.values()):
        assert w["steps"] == steps                                  # order and every field exactly as saved
        assert ok(api.get(f"{W}/{w['id']}"))["steps"] == steps
    assert listed[0]["media"][voice]["duration"] == 4.0 and listed[0]["media"][image]["kind"] == "image"


def test_crud_roundtrip(tg):
    _, api = tg
    w = create(api, "Erster", [text("a", 5), text("b", 6)])
    assert w["id"] and w["created_at"] and w["updated_at"]
    assert ok(api.get(f"{W}/{w['id']}")) == w
    steps = [text("b", 6), text("c", 7), text("a", 5)]
    saved = ok(api.put(f"{W}/{w['id']}", json={"name": "Zweiter", "steps": steps}))
    assert saved["name"] == "Zweiter" and saved["steps"] == steps and saved["updated_at"] >= w["updated_at"]
    assert [x["name"] for x in ok(api.get(W))] == ["Zweiter"]
    renamed = ok(api.patch(f"{W}/{w['id']}", json={"name": "  Dritter  "}))
    assert renamed["name"] == "Dritter" and renamed["steps"] == steps
    ok(api.delete(f"{W}/{w['id']}"))
    assert ok(api.get(W)) == []
    assert api.get(f"{W}/{w['id']}").status_code == 404
    assert api.put(f"{W}/{w['id']}", json={"name": "x", "steps": [text()]}).status_code == 404
    assert api.patch(f"{W}/{w['id']}", json={"name": "x"}).status_code == 404
    assert api.delete(f"{W}/{w['id']}").status_code == 404
    assert api.post(f"{W}/{w['id']}/duplicate").status_code == 404


def test_step_order_survives_every_permutation_and_a_restart(make_app, tmp_path):
    app = make_app(tmp_path / "s", **ENV)
    api = app.client()
    steps = [text(f"Schritt {n}", n * 7) for n in range(12)]
    wid = create(api, "Lang", steps)["id"]
    shuffled = steps[6:] + steps[:6][::-1]
    ok(api.put(f"{W}/{wid}", json={"name": "Lang", "steps": shuffled}))
    app.stop()
    again = make_app(tmp_path / "s", **ENV).client()
    assert ok(again.get(f"{W}/{wid}"))["steps"] == shuffled


def test_unknown_fields_are_dropped_and_a_missing_pause_is_zero(tg):
    _, api = tg
    made = create(api, "Lose", [{"type": "text", "content": "x", "evil": "<b>", "id": 7}])
    assert made["steps"] == [{"type": "text", "content": "x", "pause_after": 0}]


def test_names_with_markup_and_unicode_are_kept_verbatim(tg):
    _, api = tg
    name = '<img src=x onerror="alert(1)"> Ablauf für Jürgen 🎤'
    assert create(api, name, [text("<script>1</script>")])["steps"][0]["content"] == "<script>1</script>"
    assert ok(api.get(W))[0]["name"] == name


def test_duplicate(tg):
    _, api = tg
    src = create(api, "Original", [text("a", 3), text("b", 4)])
    copy = ok(api.post(f"{W}/{src['id']}/duplicate"))
    assert copy["id"] != src["id"] and copy["name"] == "Original (copy)" and copy["steps"] == src["steps"]
    assert ok(api.post(f"{W}/{src['id']}/duplicate"))["name"] == "Original (copy 2)"
    named = ok(api.post(f"{W}/{src['id']}/duplicate", json={"name": "Meine Kopie"}))
    assert named["name"] == "Meine Kopie"
    assert api.post(f"{W}/{src['id']}/duplicate", json={"name": "meine kopie"}).status_code == 409
    assert api.post(f"{W}/{src['id']}/duplicate", json={"name": " "}).status_code == 422
    # the copy is independent
    ok(api.put(f"{W}/{copy['id']}", json={"name": copy["name"], "steps": [text("neu")]}))
    assert ok(api.get(f"{W}/{src['id']}"))["steps"] == src["steps"]
    # a long name is cut so that the copy still fits 80 characters
    long = create(api, "L" * 80, [text()])
    assert len(ok(api.post(f"{W}/{long['id']}/duplicate"))["name"]) == 80


def test_a_workflow_that_uses_a_deleted_file_is_reported_not_crashing(tg):
    app, api = tg
    name = up(api, "bild.png", png())["name"]
    wid = create(api, "Mit Bild", [{"type": "image", "file": name, "pause_after": 0}])["id"]
    (app.storage / "telegram" / "media" / name).unlink()           # lost from disk behind the panel's back
    assert ok(api.get(f"{W}/{wid}"))["media"][name] == {"missing": True}
    assert ok(api.get(W))[0]["media"][name] == {"missing": True}
    r = api.put(f"{W}/{wid}", json={"name": "Mit Bild", "steps": [{"type": "image", "file": name}]})
    assert r.status_code == 422 and "does not exist" in detail(r)


# --- validation matrix ----------------------------------------------------------

@pytest.mark.parametrize("name,status", [("", 422), ("   ", 422), ("x" * 81, 422), ("x" * 80, 200), ("x", 200)])
def test_name_length(tg, name, status):
    _, api = tg
    r = api.post(W, json={"name": name, "steps": [text()]})
    assert r.status_code == status, r.text
    if status == 422:
        assert "1 to 80" in detail(r)


def test_saving_the_same_new_name_twice_at_once_gives_one_workflow_and_a_409_not_a_500(tg):
    """A double click on Save sends two POSTs together; the name check and the insert are not atomic."""
    from concurrent.futures import ThreadPoolExecutor
    app, api = tg
    for round_ in range(5):
        name = f"Doppelklick {round_}"
        with ThreadPoolExecutor(8) as pool:
            codes = sorted(pool.map(lambda _: api.post(W, json={"name": name, "steps": [text()]}).status_code, range(8)))
        assert codes.count(200) == 1 and set(codes) <= {200, 409}, codes
    assert len(ok(api.get(W))) == 5


def test_name_must_be_unique_ignoring_case_but_a_workflow_may_keep_its_own(tg):
    _, api = tg
    a = create(api, "Alpha")
    r = api.post(W, json={"name": "ALPHA", "steps": [text()]})
    assert r.status_code == 409 and "already exists" in detail(r)
    b = create(api, "Beta")
    assert api.put(f"{W}/{b['id']}", json={"name": " alpha ", "steps": [text()]}).status_code == 409
    assert api.patch(f"{W}/{b['id']}", json={"name": "Alpha"}).status_code == 409
    ok(api.put(f"{W}/{a['id']}", json={"name": "alpha", "steps": [text("neu")]}))     # only the case changes
    ok(api.patch(f"{W}/{a['id']}", json={"name": "alpha"}))                          # same name again


def test_name_that_is_not_text_is_refused(tg):
    _, api = tg
    for bad in (None, 5, ["a"], {"a": 1}):
        assert api.post(W, json={"name": bad, "steps": [text()]}).status_code == 422
    assert api.post(W, json={"steps": [text()]}).status_code == 422


@pytest.mark.parametrize("steps,fragment", [
    ([], "at least one step"),
    ([["text"]], "Step 1: invalid step"),
    (["text"], "Step 1: invalid step"),
    ([None], "Step 1: invalid step"),
    ([{"content": "x"}], "unknown step type"),
    ([{"type": "video", "file": "x"}], "unknown step type"),
    ([{"type": ["text"], "content": "x"}], "unknown step type"),
    ([{"type": "TEXT", "content": "x"}], "unknown step type"),
    ([text(), {"type": "text"}], "Step 2: text is required"),
    ([{"type": "text", "content": ""}], "text is required"),
    ([{"type": "text", "content": "  \n\t "}], "text is required"),
    ([{"type": "text", "content": None}], "text is required"),
    ([{"type": "text", "content": 5}], "text is required"),
    ([{"type": "text", "content": "x" * 4097}], "too long"),
    ([{"type": "image"}], "image file is required"),
    ([{"type": "voice", "file": ""}], "voice file is required"),
    ([{"type": "voice", "file": 7}], "voice file is required"),
    ([{"type": "image", "file": "../../etc/passwd"}], "not a image file"),
    ([{"type": "image", "file": "img-" + "0" * 32 + ".jpg/../x"}], "not a image file"),
    ([{"type": "image", "file": "img-" + "0" * 32 + ".exe"}], "not a image file"),
    ([{"type": "image", "file": "img-" + "a" * 32 + ".jpg"}], "does not exist"),
    ([{"type": "voice", "file": "voice-" + "a" * 32 + ".ogg"}], "does not exist"),
    ([text(pause=-1)], "pause must be a whole number"),
    ([text(pause=86401)], "pause must be a whole number"),
    ([text(pause=1.5)], "pause must be a whole number"),
    ([text(pause=30.0)], "pause must be a whole number"),
    ([text(pause="10")], "pause must be a whole number"),
    ([text(pause=True)], "pause must be a whole number"),
    ([text(pause=None)], "pause must be a whole number"),
    ([text(), text(), text(pause=10 ** 9)], "Step 3: the pause"),
])
def test_step_validation_matrix(tg, steps, fragment):
    app, api = tg
    r = api.post(W, json={"name": "V", "steps": steps})
    assert r.status_code == 422, r.text
    assert fragment in detail(r), detail(r)
    assert ok(api.get(W)) == []                                   # nothing was stored
    wid = create(api, "Gut")["id"]                                # the same rules apply on save
    r = api.put(f"{W}/{wid}", json={"name": "Gut", "steps": steps})
    assert r.status_code == 422 and fragment in detail(r)
    assert ok(api.get(f"{W}/{wid}"))["steps"] == [text()]         # and the stored workflow is untouched


def test_steps_that_are_not_a_list_are_refused(tg):
    _, api = tg
    for bad in (None, "text", {"type": "text"}, 5):
        assert api.post(W, json={"name": "x", "steps": bad}).status_code == 422
    assert api.post(W, json={"name": "x"}).status_code == 422
    assert api.post(W, content=b"not json", headers={"content-type": "application/json"}).status_code == 422


def test_boundaries_that_are_allowed(tg):
    _, api = tg
    voice = up(api, "v.ogg", ogg_opus(1))["name"]
    steps = [text("x" * 4096, 86400), text("ä", 0), {"type": "voice", "file": voice, "pause_after": 1}]
    assert create(api, "Grenzen", steps)["steps"] == steps


def test_a_file_must_match_the_step_type(tg):
    _, api = tg
    img, voice = up(api, "a.png", png())["name"], up(api, "v.ogg", ogg_opus())["name"]
    r = api.post(W, json={"name": "x", "steps": [{"type": "voice", "file": img}]})
    assert r.status_code == 422 and "not a voice file" in detail(r)
    r = api.post(W, json={"name": "x", "steps": [{"type": "image", "file": voice}]})
    assert r.status_code == 422 and "not a image file" in detail(r)


def test_step_types_are_registered_in_one_place():
    import modules.telegram.api as tg_api
    assert set(tg_api.STEP_TYPES) == {"text", "image", "voice"}
    tg_api.STEP_TYPES["probe"] = lambda step: {"content": "ok"}
    try:
        assert tg_api._clean_steps([{"type": "probe", "pause_after": 2}]) == [{"type": "probe", "content": "ok", "pause_after": 2}]
    finally:
        del tg_api.STEP_TYPES["probe"]


# --- deleting workflows and runs ------------------------------------------------

def test_deleting_a_workflow_with_an_active_run_is_refused_and_finished_runs_keep_their_snapshot(tg):
    app, api = tg
    w = create(api, "Mit Lauf", [text("a"), text("b")])
    run = add_run(app, w["id"], "running", w["steps"], "Mit Lauf")
    for status in ("queued", "paused"):
        db_exec(app, "UPDATE tg_run SET status=? WHERE id=?", (status, run))
        r = api.delete(f"{W}/{w['id']}")
        assert r.status_code == 409 and "active run" in detail(r)
    assert len(ok(api.get(W))) == 1
    db_exec(app, "UPDATE tg_run SET status='done' WHERE id=?", (run,))
    ok(api.delete(f"{W}/{w['id']}"))
    with sqlite3.connect(app.storage / "db.sqlite") as c:
        wid, name, snap = c.execute("SELECT workflow_id, workflow_name, workflow_snapshot FROM tg_run").fetchone()
    assert wid is None and name == "Mit Lauf" and json.loads(snap)["steps"] == w["steps"]


def test_editing_a_workflow_does_not_touch_a_running_snapshot(tg):
    app, api = tg
    w = create(api, "Edit", [text("alt")])
    add_run(app, w["id"], "running", w["steps"])
    ok(api.put(f"{W}/{w['id']}", json={"name": "Edit", "steps": [text("neu")]}))
    with sqlite3.connect(app.storage / "db.sqlite") as c:
        snap = json.loads(c.execute("SELECT workflow_snapshot FROM tg_run").fetchone()[0])
    assert snap["steps"][0]["content"] == "alt"


# --- media: upload, serve, delete -----------------------------------------------

@pytest.mark.parametrize("filename,data,content_type,kind,ext", [
    ("foto.jpg", jpg(), "image/jpeg", "image", "jpg"),
    ("FOTO.JPEG", jpg(), "image/jpeg", "image", "jpg"),
    ("bild.png", png(), "image/png", "image", "png"),
    ("bild.webp", webp(), "image/webp", "image", "webp"),
    ("memo.ogg", ogg_opus(), "audio/ogg", "voice", "ogg"),
    ("memo.opus", ogg_opus(), "audio/ogg", "voice", "ogg"),
], ids=lambda v: v if isinstance(v, str) and len(v) < 12 else "")
def test_upload_and_serve(tg, filename, data, content_type, kind, ext):
    app, api = tg
    info = up(api, filename, data)
    assert info["kind"] == kind and info["size"] == len(data)
    assert info["name"].endswith("." + ext) and info["name"] != filename and len(info["name"]) > 30
    r = api.get(f"{M}/{info['name']}")
    assert r.status_code == 200 and r.content == data                  # opus and images are stored as they came
    assert r.headers["content-type"] == content_type and r.headers["x-content-type-options"] == "nosniff"
    assert media_files(app) == [info["name"]]


def test_two_uploads_of_the_same_file_get_different_names(tg):
    _, api = tg
    assert up(api, "a.png", png())["name"] != up(api, "a.png", png())["name"]


def test_many_files_in_one_request_with_a_partial_rejection(tg):
    app, api = tg
    res = ok(upload(api, ("a.jpg", jpg()), ("b.png", png()), ("kaputt.jpg", b"not an image"), ("c.ogg", ogg_opus())), 200)
    assert [s["kind"] for s in res["saved"]] == ["image", "image", "voice"]
    assert [r["filename"] for r in res["rejected"]] == ["kaputt.jpg"] and res["rejected"][0]["error"]
    assert len(media_files(app)) == 3
    assert len(ok(api.get(M))) == 3


def test_when_nothing_is_accepted_the_call_fails_with_the_reason(tg):
    app, api = tg
    r = upload(api, ("a.txt", b"hello"), ("b.jpg", b"x"))
    assert r.status_code == 422 and "Unsupported file type" in detail(r)
    assert media_files(app) == []
    assert api.post(M).status_code == 422                               # no files at all


@pytest.mark.parametrize("filename,data,fragment,status", [
    ("leer.jpg", b"", "file is empty", 422),
    ("leer.ogg", b"", "file is empty", 422),
    ("text.jpg", b"just some text, not an image at all", "Unsupported file type", 422),
    ("script.exe", b"MZ\x90\x00" + b"\0" * 100, "Unsupported file type", 422),
    ("page.html", b"<html><script>alert(1)</script></html>", "Unsupported file type", 422),
    ("fake.jpg", b"<?php system($_GET['c']); ?>", "Unsupported file type", 422),
    ("pic.jpg", png(), "does not match its extension", 422),            # a PNG under a .jpg name
    ("pic.png", jpg(), "does not match its extension", 422),
    ("pic.mp3", jpg(), "does not match its extension", 422),
    ("sound.jpg", ogg_opus(), "does not match its extension", 422),
    ("dead.jpg", b"\xff\xd8\xff\xe0" + b"garbage" * 50, "damaged", 422),    # JPEG header, no image behind it
    ("dead.png", b"\x89PNG\r\n\x1a\n" + b"garbage" * 50, "damaged", 422),
    ("shell.php.jpg", jpg(), "Double file extensions", 422),
    ("a.b.c.png", png(), "Double file extensions", 422),
    ("evil.jpg.exe", jpg(), "Double file extensions", 422),
    ("../../evil.jpg", jpg(), "Invalid file name", 422),
    ("..\\..\\evil.jpg", jpg(), "Invalid file name", 422),
    ("/etc/passwd.jpg", jpg(), "Invalid file name", 422),
    ("..jpg", jpg(), "Invalid file name", 422),
    ("keinedung", jpg(), "no extension", 422),
    (".jpg", jpg(), "no extension", 422),
    ("x" * 300 + ".jpg", jpg(), "Invalid file name", 422),
], ids=lambda v: v[:20] if isinstance(v, str) else "")
def test_rejected_uploads(tg, filename, data, fragment, status):
    app, api = tg
    r = upload(api, (filename, data))
    assert r.status_code == status and fragment in detail(r), r.text
    assert media_files(app) == []                                        # nothing written, not even a temp file


def test_upload_size_limits(tg):
    app, api = tg
    at_limit = b"\xff\xd8\xff" + b"\0" * (10 * 1024 * 1024 - 3)
    r = upload(api, ("gross.jpg", at_limit + b"\0"))
    assert r.status_code == 413 and "10 MB" in detail(r)                  # oversize is refused before it is looked at
    assert media_files(app) == []
    r = upload(api, ("gross.ogg", ogg_opus() + b"\0" * (50 * 1024 * 1024)))
    assert r.status_code == 413 and "50 MB" in detail(r)
    assert media_files(app) == []
    # exactly 10 MB of a real image is still fine: pad a PNG with trailing bytes (readers ignore them)
    big = png() + b"\0" * (10 * 1024 * 1024 - len(png()))
    assert ok(upload(api, ("genau.png", big)), 200)["saved"][0]["size"] == 10 * 1024 * 1024


def test_serving_rules(tg):
    app, api = tg
    name = up(api, "a.png", png())["name"]
    anon = httpx.Client(base_url=app.url)
    assert anon.get(f"{M}/{name}").status_code in (401, 403)
    assert api.get(f"{M}/img-{'0' * 32}.png").status_code == 404
    for bad in ("..", "../db.sqlite", "..%2Fdb.sqlite", "%2e%2e%2f%2e%2e%2fdb.sqlite", "..%5Cdb.sqlite", "db.sqlite",
                name.upper(), name + "/", name + ".exe", "img-xyz.png", "%00", name + "%00.png"):
        r = api.get(f"{M}/{bad}")
        assert r.status_code in (307, 404, 405) and b"SQLite" not in r.content, (bad, r.status_code)
    # a file of the right shape put into the folder by hand is the only thing that can be served
    (app.storage / "telegram" / "secret.txt").write_text("nope")
    assert api.get(f"{M}/..%2Fsecret.txt").status_code == 404


def test_delete_rules(tg):
    app, api = tg
    name = up(api, "a.png", png())["name"]
    w = create(api, "Nutzer", [{"type": "image", "file": name, "pause_after": 0}])
    r = api.delete(f"{M}/{name}")
    assert r.status_code == 409 and "Nutzer" in detail(r)
    assert api.get(f"{M}/{name}").status_code == 200
    assert ok(api.get(M))[0]["used_by"] == ["Nutzer"]
    # replacing the step's file frees the old one
    other = up(api, "b.png", png())["name"]
    ok(api.put(f"{W}/{w['id']}", json={"name": "Nutzer", "steps": [{"type": "image", "file": other}]}))
    ok(api.delete(f"{M}/{name}"))
    assert api.get(f"{M}/{name}").status_code == 404
    assert api.delete(f"{M}/{name}").status_code == 404                     # already gone
    assert api.delete(f"{M}/..%2Fdb.sqlite").status_code == 404
    assert api.delete(f"{M}/{other}").status_code == 409
    ok(api.delete(f"{W}/{w['id']}"))
    ok(api.delete(f"{M}/{other}"))
    assert media_files(app) == []


def test_a_file_used_by_a_running_run_cannot_be_deleted(tg):
    app, api = tg
    name = up(api, "a.png", png())["name"]
    step = {"type": "image", "file": name, "pause_after": 0}
    run = add_run(app, None, "paused", [step], "Alt")
    r = api.delete(f"{M}/{name}")
    assert r.status_code == 409 and "Alt" in detail(r)
    db_exec(app, "UPDATE tg_run SET status='stopped' WHERE id=?", (run,))
    ok(api.delete(f"{M}/{name}"))


def test_media_list_reports_duration_kind_and_usage(tg):
    _, api = tg
    voice = up(api, "v.ogg", ogg_opus(2.5))
    assert voice["duration"] == 2.5
    img = up(api, "i.jpg", jpg())
    assert img["duration"] is None
    rows = {m["name"]: m for m in ok(api.get(M))}
    assert rows[voice["name"]]["duration"] == 2.5 and rows[img["name"]]["used_by"] == []


def test_voice_duration_is_measured_from_the_stream(tg):
    _, api = tg
    for seconds in (0.5, 12.3, 61):
        assert up(api, "v.ogg", ogg_opus(seconds))["duration"] == pytest.approx(seconds, abs=0.1)


# --- voice conversion -----------------------------------------------------------

def fake_ffmpeg(tmp_path: Path) -> Path:
    """A stand-in for ffmpeg: answers with a fixed OGG/Opus file, fails on input that contains BAD."""
    (tmp_path / "converted.ogg").write_bytes(ogg_opus(7.0))
    (tmp_path / "args.json").write_text("[]")
    script = tmp_path / "fake_ffmpeg.py"
    script.write_text(
        "import json, shutil, sys\n"
        f"json.dump(sys.argv[1:], open({str(tmp_path / 'args.json')!r}, 'w'))\n"
        "src = sys.argv[sys.argv.index('-i') + 1]\n"
        "if b'BAD' in open(src, 'rb').read():\n"
        "    sys.exit(1)\n"
        f"shutil.copy({str(tmp_path / 'converted.ogg')!r}, sys.argv[-1])\n")
    if os.name == "nt":
        launcher = tmp_path / "ffmpeg.cmd"
        launcher.write_text(f'@"{sys.executable}" "{script}" %*\r\n')
    else:
        launcher = tmp_path / "ffmpeg"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
        launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC)
    return launcher


@pytest.mark.parametrize("filename,data", [
    ("lied.mp3", MP3), ("lied.m4a", M4A), ("lied.aac", AAC), ("lied.wav", wav_bytes()), ("lied.ogg", ogg_vorbis())],
    ids=lambda v: v if isinstance(v, str) else "")
def test_other_audio_formats_are_converted_to_opus(make_app, tmp_path, filename, data):
    app = make_app(**ENV, FFMPEG_BIN=str(fake_ffmpeg(tmp_path)))
    api = app.client()
    info = up(api, filename, data)
    assert info["name"].startswith("voice-") and info["name"].endswith(".ogg") and info["duration"] == 7.0
    stored = api.get(f"{M}/{info['name']}").content
    assert stored == ogg_opus(7.0)                                          # the converted file, not the upload
    args = json.loads((tmp_path / "args.json").read_text())
    assert "libopus" in args and "-vn" in args and args[-1].endswith("out.ogg")
    assert media_files(app) == [info["name"]]


def test_a_failing_conversion_is_reported_and_leaves_nothing_behind(make_app, tmp_path):
    app = make_app(**ENV, FFMPEG_BIN=str(fake_ffmpeg(tmp_path)))
    r = upload(app.client(), ("kaputt.mp3", MP3 + b"BAD"))
    assert r.status_code == 422 and "could not be converted" in detail(r)
    assert media_files(app) == []


def test_opus_is_never_sent_through_ffmpeg(make_app, tmp_path):
    app = make_app(**ENV, FFMPEG_BIN=str(fake_ffmpeg(tmp_path)))
    up(app.client(), "memo.ogg", ogg_opus(3))
    assert json.loads((tmp_path / "args.json").read_text()) == []            # the stand-in was not called


def test_missing_ffmpeg_gives_a_clear_error_but_opus_still_works(make_app, tmp_path):
    app = make_app(**ENV, FFMPEG_BIN=str(tmp_path / "no-such-ffmpeg"))
    api = app.client()
    for filename, data in (("a.mp3", MP3), ("a.wav", wav_bytes()), ("a.ogg", ogg_vorbis())):
        r = upload(api, (filename, data))
        assert r.status_code == 503 and "ffmpeg" in detail(r) and "OGG/Opus" in detail(r)
    assert media_files(app) == []
    up(api, "ok.ogg", ogg_opus())
    up(api, "ok.png", png())


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg is not installed")
def test_real_ffmpeg_converts_wav_to_a_real_voice_file(tg):
    _, api = tg
    info = up(api, "ton.wav", wav_bytes(1.0))
    stored = api.get(f"{M}/{info['name']}").content
    assert stored[:4] == b"OggS" and b"OpusHead" in stored[:64]
    assert info["duration"] == pytest.approx(1.0, abs=0.2)


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg is not installed")
def test_real_ffmpeg_rejects_garbage_with_a_wav_header(tg):
    _, api = tg
    r = upload(api, ("kaputt.wav", b"RIFF\x00\x00\x00\x00WAVEgarbage" * 20))
    assert r.status_code == 422 and "could not be converted" in detail(r)
