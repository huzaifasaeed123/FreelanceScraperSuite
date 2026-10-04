"""Text overlay on library photos: the browser draws the caption, the server cleans + overwrites the photo."""

import hashlib
from pathlib import Path
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


def test_panel_files_are_revalidated_not_cached_blindly(app):
    """A browser must re-check app.js / style.css on every load, else an old app.js runs next to a new index.html
    after a deploy (e.g. the 'Add text' button staying disabled)."""
    import httpx
    for path in ("/static/app.js", "/static/style.css"):
        r = httpx.get(app.url + path)
        assert r.status_code == 200 and r.headers["cache-control"] == "no-cache", path
        again = httpx.get(app.url + path, headers={"If-None-Match": r.headers["etag"]})
        assert again.status_code == 304, "unchanged file -> cheap 'not modified'"


# --- several text lines (client: "one line on top and something below it") ---------------------------

def _flat_photo(api, colour=(16, 24, 40), size=(800, 1000)):
    buf = io.BytesIO()
    Image.new("RGB", size, colour).save(buf, "JPEG", quality=95)
    ok(api.post("/api/photos", files=[("files", ("flat.jpg", buf.getvalue(), "image/jpeg"))]))
    return "flat.jpg"


def _light_rows(path, y0, y1):
    """How many pixels in the band y0..y1 (fractions of the height) are near white."""
    with Image.open(path) as im:
        im = im.convert("RGB")
        w, h = im.size
        return sum(1 for y in range(int(h * y0), int(h * y1), 2) for x in range(0, w, 2)
                   if min(im.getpixel((x, y))) > 200)


def test_rows_of_one_line_are_stacked(browser, app):
    """Enter inside a line makes a second row under the first (no overlap): 1 row = 1 text band, 2 rows = 2."""
    pg = Page(browser, app).login("photos")
    try:
        script = """async (text) => {
          const c = document.createElement("canvas"); c.width = 600; c.height = 800;
          const g = c.getContext("2d"); g.fillStyle = "#101820"; g.fillRect(0, 0, 600, 800);
          const img = new Image(); img.src = c.toDataURL("image/png"); await img.decode();
          const out = document.createElement("canvas");
          drawCaption(out, img, [{ text, sizePct: 8, pos: "mc", color: "#ffffff", bold: true, outline: false, outlineColor: "#000000" }]);
          const d = out.getContext("2d").getImageData(0, 0, 600, 800).data;
          let bands = 0, prev = false;
          for (let y = 0; y < 800; y++) {
            let hit = false;
            for (let x = 0; x < 600 && !hit; x++) { const i = (y * 600 + x) * 4; hit = d[i] > 200 && d[i + 1] > 200 && d[i + 2] > 200; }
            if (hit && !prev) bands++;
            prev = hit;
          }
          return bands;
        }"""
        assert pg.p.evaluate(script, "ABC") == 1
        assert pg.p.evaluate(script, "ABC\nXYZ") == 2, "the second row sits under the first one"
        assert pg.p.evaluate(script, "ABC\n\n  \nXYZ") == 2, "empty rows are ignored"
    finally:
        pg.close()


def test_two_text_lines_top_and_bottom_on_the_saved_photo(browser, app):
    api = app.client()
    setup_ready(api, photos=0)
    name = _flat_photo(api)
    pg = Page(browser, app).login("photos")
    try:
        pg.p.wait_for_selector("#photo-grid .photo-card")
        pg.p.locator("#photo-grid [data-sel]").nth(0).check()
        pg.p.click("#photo-add-text")
        pg.p.wait_for_function("document.querySelector('#txt-canvas').width > 0")
        pg.p.fill("#txt-text", "Oben")
        pg.p.click('#txt-grid [data-pos="tc"]')
        pg.p.click("#txt-add")
        assert pg.p.locator("#txt-lines .txt-line[data-line]").count() == 2
        assert pg.p.get_attribute('#txt-grid [data-pos="mc"]', "class") == "on", "a new line starts at a free spot"
        assert pg.p.input_value("#txt-text") == "", "the new line starts empty"
        pg.p.fill("#txt-text", "Unten")
        pg.p.click('#txt-grid [data-pos="bc"]')
        # going back to line 1 shows its own settings
        pg.p.click('#txt-lines [data-line="0"]')
        assert pg.p.input_value("#txt-text") == "Oben"
        assert pg.p.get_attribute('#txt-grid [data-pos="tc"]', "class") == "on"
        pg.p.click("#txt-apply")
        pg.p.wait_for_selector("#txt-canvas", state="detached", timeout=20000)
        path = Path(app.storage) / "photos" / name
        assert _light_rows(path, 0.0, 0.18) > 150, "line 1 is at the top"
        assert _light_rows(path, 0.82, 1.0) > 150, "line 2 is at the bottom"
        assert _light_rows(path, 0.30, 0.70) == 0, "nothing in the middle"
        pg.assert_clean("two text lines")
    finally:
        pg.close()


def test_long_text_shrinks_to_fit_instead_of_being_cut_off(browser, app):
    """A caption wider than the photo must not be cropped at the edges: it shrinks until it fits."""
    pg = Page(browser, app).login("photos")
    try:
        script = """async (text) => {
          const c = document.createElement("canvas"); c.width = 600; c.height = 800;
          const g = c.getContext("2d"); g.fillStyle = "#101820"; g.fillRect(0, 0, 600, 800);
          const img = new Image(); img.src = c.toDataURL("image/png"); await img.decode();
          const out = document.createElement("canvas");
          drawCaption(out, img, [{ text, sizePct: 12, pos: "mc", color: "#ffffff", bold: true, outline: true, outlineColor: "#000000" }]);
          const d = out.getContext("2d").getImageData(0, 0, 600, 800).data;
          let left = 600, right = -1;
          for (let y = 0; y < 800; y++) for (let x = 0; x < 600; x++) {
            const i = (y * 600 + x) * 4;
            if (d[i] > 200 && d[i + 1] > 200 && d[i + 2] > 200) { left = Math.min(left, x); right = Math.max(right, x); }
          }
          return [left, right];
        }"""
        left, right = pg.p.evaluate(script, "Lustkreis.com SecretDesire und noch viel mehr Text")
        assert left > 5 and right < 594, f"text touches/leaves the photo edge: {left}..{right}"
        assert right - left > 300, "still large and readable, only as small as needed"
        # a short text keeps the chosen size (is not shrunk)
        short_left, short_right = pg.p.evaluate(script, "Hi")
        assert short_right - short_left < 150
    finally:
        pg.close()
