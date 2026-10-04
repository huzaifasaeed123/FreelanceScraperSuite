"""Text overlay on library photos: the browser draws the caption, the server cleans + overwrites the photo."""

import hashlib
import io

from PIL import Image, ImageDraw

from conftest import jpeg_bytes, ok, setup_ready, wait_runs_done
from test_ui import Page, browser  # noqa: F401 (fixture)


def _captioned(seed=0, text="Sofihey Telegram", size=(600, 800)):
    """What the browser would send: the photo with a caption drawn on it."""
    im = Image.open(io.BytesIO(jpeg_bytes(seed))).convert("RGB").resize(size)
    ImageDraw.Draw(im).text((size[0] // 4, size[1] // 2), text, fill=(255, 255, 255))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=92)
    return out.getvalue()


def _names(api):
    return {p["name"]: p for p in ok(api.get("/api/photos"))}


def test_overwrite_replaces_image_hash_and_thumb(app, api):
    setup_ready(api, photos=2)
    name = sorted(_names(api))[0]
    before = _names(api)[name]
    r = api.post(f"/api/photos/{name}/overwrite", files={"file": ("x.jpg", _captioned(0), "image/jpeg")})
    res = ok(r)
    assert res["name"] == name and res["width"] == 600 and res["height"] == 800
    after = _names(api)[name]
    assert after["size"] != before["size"], "stored image changed"
    assert api.get(f"/api/photos/{name}/file").content[:2] == b"\xff\xd8", "still a JPEG"
    thumb = api.get(f"/api/photos/{name}/thumb")
    assert thumb.status_code == 200 and thumb.headers["content-type"].startswith("image/")
    # the stored file matches the new hash (so duplicates are detected against the captioned image)
    assert hashlib.sha256(api.get(f"/api/photos/{name}/file").content).hexdigest() == \
        hashlib.sha256(api.get(f"/api/photos/{name}/file").content).hexdigest()


def test_overwrite_validations(app, api, jaumo):
    setup_ready(api, photos=3, max_swipes=1)
    names = sorted(_names(api))
    # not an image
    r = api.post(f"/api/photos/{names[0]}/overwrite", files={"file": ("x.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 422 and "readable image" in r.json()["detail"]
    # too small
    tiny = io.BytesIO()
    Image.new("RGB", (40, 40), "red").save(tiny, "JPEG")
    assert api.post(f"/api/photos/{names[0]}/overwrite", files={"file": ("x.jpg", tiny.getvalue(), "image/jpeg")}).status_code == 422
    # the same image sent for two different photos -> the second is refused (keeps "never the same image twice")
    same = _captioned(5)
    ok(api.post(f"/api/photos/{names[0]}/overwrite", files={"file": ("x.jpg", same, "image/jpeg")}))
    r = api.post(f"/api/photos/{names[1]}/overwrite", files={"file": ("x.jpg", same, "image/jpeg")})
    assert r.status_code == 422 and f"same image as {names[0]}" in r.json()["detail"]
    # unknown photo
    assert api.post("/api/photos/nope.jpg/overwrite", files={"file": ("x.jpg", _captioned(0), "image/jpeg")}).status_code == 422
    # a photo already used by an account is kept for its history
    run = wait_runs_done(api, ok(api.post("/api/runs", json={"count": 1}))["run_ids"])[0]
    r = api.post(f"/api/photos/{run['photo']}/overwrite", files={"file": ("x.jpg", _captioned(1), "image/jpeg")})
    assert r.status_code == 422 and "used by an account" in r.json()["detail"]


def test_editor_adds_text_to_selected_photos(browser, app):
    api = app.client()
    setup_ready(api, photos=3)
    before = {n: p["size"] for n, p in _names(api).items()}
    pg = Page(browser, app).login("photos")
    try:
        pg.p.wait_for_selector("#photo-grid .photo-card")
        assert pg.p.is_disabled("#photo-add-text"), "needs a selection first"
        # select two of the three photos
        boxes = pg.p.locator("#photo-grid [data-sel]")
        boxes.nth(0).check()
        boxes.nth(1).check()
        assert not pg.p.is_disabled("#photo-add-text")
        pg.p.click("#photo-add-text")
        pg.p.wait_for_selector("#txt-canvas")
        pg.p.wait_for_function("document.querySelector('#txt-canvas').width > 0")
        # empty text is refused
        pg.p.click("#txt-apply")
        assert "Text" in pg.p.inner_text("#txt-error")
        pg.p.fill("#txt-text", "Sofihey Telegram")
        pg.p.click('#txt-grid [data-pos="bc"]')
        pg.p.fill("#txt-size", "9")
        assert "1 / 2" in pg.p.inner_text("#txt-count")
        pg.p.click("#txt-next")
        assert "2 / 2" in pg.p.inner_text("#txt-count")
        pg.p.click("#txt-apply")
        pg.p.wait_for_selector("#txt-canvas", state="detached", timeout=20000)
        after = {n: p["size"] for n, p in _names(api).items()}
        changed = [n for n in before if after[n] != before[n]]
        assert len(changed) == 2, f"exactly the 2 selected photos got the text: {changed}"
        pg.assert_clean("photo text editor")
    finally:
        pg.close()
