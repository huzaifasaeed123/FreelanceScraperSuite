"""Browser walk-through of the Telegram Abläufe tab (Edge via Playwright) against the real server: builds the brief's
workflow (voice, text, image, voice with pauses 60 / 30 / 10 s), reorders it by drag and by buttons, saves, reloads and
finds it unchanged, in German and English. Any JS error, console error or failed request fails the test."""

import pytest

from conftest import ADMIN_PASS, ok
from test_telegram_accounts import ENV
from test_telegram_workflows import M, W, jpg, ogg_opus

pw_sync = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.ui

T = "#tab-telegram-workflows"
VOICE_A, VOICE_B = ogg_opus(3.0), ogg_opus(5.0)


@pytest.fixture(scope="module")
def browser():
    with pw_sync.sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="msedge")
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"Edge is not available: {e}")
        yield b
        b.close()


@pytest.fixture
def ui(browser, make_app):
    app = make_app(**ENV)
    api = app.client()
    contexts, dialogs = [], []

    def open_page(lang="de", viewport=(1300, 2400)):
        ctx = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]}, locale="en-US")
        ctx.add_init_script(f"try{{localStorage.setItem('lang','{lang}')}}catch(e){{}}")
        page = ctx.new_page()
        problems = []
        page.on("pageerror", lambda e: problems.append(f"JS error: {e}"))
        page.on("console", lambda m: m.type == "error" and problems.append(f"console: {m.text}"))
        page.on("response", lambda r: r.status >= 400 and problems.append(f"HTTP {r.status} {r.url}"))
        page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
        page.goto(app.url + "/#telegram-workflows")
        page.fill("input[name=username]", "admin")
        page.fill("input[name=password]", ADMIN_PASS)
        page.click("#login-form button[type=submit]")
        page.wait_for_selector(f"{T} h1")
        contexts.append(ctx)
        return page, problems

    yield app, api, open_page, dialogs
    for ctx in contexts:
        ctx.close()


def file_arg(name, data, mime):
    return {"name": name, "mimeType": mime, "buffer": data}


def add_step(page, kind):
    page.click(f'{T} [data-act="add-toggle"]')
    page.click(f'{T} [data-add="{kind}"]')


def last_card(page):
    return page.locator(f"{T} .tg-step").last


def upload(page, card, name, data, mime):
    card.locator("[data-file]").set_input_files(file_arg(name, data, mime))
    card.locator("audio, img").first.wait_for()


def types(page):
    return page.eval_on_selector_all(f"{T} .tg-step", "els => els.map(e => e.querySelector('audio') ? 'voice:' + "
                                                       "e.querySelector('audio').getAttribute('src').slice(-37, -33) : "
                                                       "e.querySelector('img') ? 'image' : 'text')")


def drag_above(page, source, target):
    """Drag the grip of card `source` onto the upper half of card `target` with real mouse events."""
    grip = page.locator(f"{T} .tg-step").nth(source).locator("[data-grip]").bounding_box()
    card = page.locator(f"{T} .tg-step").nth(target).bounding_box()
    page.mouse.move(grip["x"] + 10, grip["y"] + 10)
    page.mouse.down()
    page.mouse.move(grip["x"] + 10, grip["y"] - 20, steps=5)           # the browser starts a drag only after some movement
    page.mouse.move(card["x"] + 80, card["y"] + 4, steps=10)
    page.mouse.up()


def shape(workflow):
    return [(s["type"], s["pause_after"]) for s in workflow["steps"]]


def build_brief_workflow(page):
    """Sprachmemo -60 s- Text -30 s- Bild -10 s- Sprachmemo."""
    page.click(f'{T} [data-act="new"]')
    page.fill(f"{T} [data-name]", "Workflow 1 – Neukontakt")
    add_step(page, "voice")
    upload(page, last_card(page), "a.ogg", VOICE_A, "audio/ogg")
    add_step(page, "text")
    last_card(page).locator("[data-content]").fill("Hallo <b>du</b>! Schön, dass du da bist.")
    add_step(page, "image")
    upload(page, last_card(page), "bild.jpg", jpg(), "image/jpeg")
    add_step(page, "voice")
    upload(page, last_card(page), "b.ogg", VOICE_B, "audio/ogg")
    for n, pause in enumerate(("60", "30", "10")):
        page.locator(f"{T} .tg-step").nth(n).locator("[data-pause]").select_option(pause)
    page.locator(f"{T} .tg-step").nth(3).locator("[data-pause]").select_option("0")


def test_german_walkthrough_builds_reorders_saves_and_reloads(ui):
    app, api, open_page, dialogs = ui
    page, problems = open_page("de")
    assert "Noch kein Ablauf gespeichert" in page.inner_text(T)

    build_brief_workflow(page)
    ids = types(page)
    assert [t.split(":")[0] for t in ids] == ["voice", "text", "image", "voice"]
    original = list(ids)
    assert "Pausen pro Chat: 1 Min 40 s" in page.inner_text(f"{T} [data-total]")
    assert "1 Min Pause" in page.inner_text(f"{T} .tg-arrow >> nth=0")
    assert page.locator(f"{T} .tg-arrow").count() == 3
    assert page.is_visible(f"{T} [data-dirty]")

    # drag the last card above the first one
    drag_above(page, 3, 0)
    assert types(page) == [original[3], original[0], original[1], original[2]]

    # and back with the buttons: down once, then twice more for the same card
    page.locator(f"{T} .tg-step").nth(0).locator('[data-act="down"]').click()
    assert types(page) == [original[0], original[3], original[1], original[2]]
    page.locator(f"{T} .tg-step").nth(1).locator('[data-act="down"]').click()
    page.locator(f"{T} .tg-step").nth(2).locator('[data-act="down"]').click()
    assert types(page) == original
    assert page.locator(f"{T} .tg-step").first.locator('[data-act="up"]').is_disabled()

    page.click(f'{T} [data-act="save"]')
    page.wait_for_selector("#toasts >> text=Ablauf gespeichert")
    assert not page.is_visible(f"{T} [data-dirty]")
    saved = ok(api.get(W))
    assert len(saved) == 1 and saved[0]["name"] == "Workflow 1 – Neukontakt"
    assert shape(saved[0]) == [("voice", 60), ("text", 30), ("image", 10), ("voice", 0)]
    assert saved[0]["steps"][1]["content"] == "Hallo <b>du</b>! Schön, dass du da bist."

    # reload the whole page: the list shows the card, the editor shows the same workflow
    page.reload()
    page.wait_for_selector(f"{T} .tg-wf-card")
    card = page.inner_text(f"{T} .tg-wf-card")
    assert "Workflow 1 – Neukontakt" in card and "4 Schritte" in card and "1 Min 40 s" in card
    page.click(f"{T} .tg-wf-card")
    page.wait_for_selector(f"{T} .tg-step")
    assert types(page) == original
    assert page.input_value(f"{T} [data-name]") == "Workflow 1 – Neukontakt"
    assert page.locator(f"{T} [data-pause]").evaluate_all("els => els.map(e => e.value)") == ["60", "30", "10", "0"]
    assert page.locator(f"{T} [data-content]").input_value() == "Hallo <b>du</b>! Schön, dass du da bist."
    assert page.locator(f"{T} .tg-step b").count() == 0                       # the text is not rendered as markup
    assert not page.is_visible(f"{T} [data-dirty]")
    assert not problems, problems


def test_english_walkthrough_and_phone_width(ui):
    app, api, open_page, _ = ui
    page, problems = open_page("en")
    assert "No workflow saved yet" in page.inner_text(T)
    build_brief_workflow(page)
    assert "pauses per chat: 1 min 40 s" in page.inner_text(f"{T} [data-total]")
    assert "Pause after" in page.inner_text(T) and "Add message" in page.inner_text(T)
    page.click(f'{T} [data-act="save"]')
    page.wait_for_selector("#toasts >> text=Workflow saved")
    assert shape(ok(api.get(W))[0]) == [("voice", 60), ("text", 30), ("image", 10), ("voice", 0)]

    page.click(f'{T} [data-act="back"]')
    page.wait_for_selector(f"{T} .tg-wf-card")
    assert "4 steps" in page.inner_text(T)
    page.click(f'{T} [data-act="duplicate"]')
    page.wait_for_selector(f"{T} .tg-wf-card >> nth=1")
    assert [w["name"] for w in ok(api.get(W))] == ["Workflow 1 – Neukontakt", "Workflow 1 – Neukontakt (copy)"]

    page.set_viewport_size({"width": 390, "height": 800})
    page.click(f"{T} .tg-wf-card >> nth=0")
    page.wait_for_selector(f"{T} .tg-step")
    page.wait_for_timeout(300)
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    assert not problems, problems


def test_validation_messages_unsaved_warning_and_list_actions(ui):
    app, api, open_page, dialogs = ui
    page, problems = open_page("de")

    page.click(f'{T} [data-act="new"]')
    page.click(f'{T} [data-act="save"]')                    # nothing filled in
    assert "Bitte einen Namen eingeben." in page.inner_text(f'{T} [data-err="name"]')
    assert "mindestens einen Schritt" in page.inner_text(f'{T} [data-err="top"]')

    add_step(page, "text")
    add_step(page, "image")
    page.click(f'{T} [data-act="save"]')
    assert "Der Text darf nicht leer sein." in page.inner_text(f"{T} .tg-step >> nth=0")
    assert "Bitte eine Datei hochladen." in page.inner_text(f"{T} .tg-step >> nth=1")
    assert ok(api.get(W)) == []

    page.fill(f"{T} [data-name]", "<i>Test</i>")
    page.locator(f"{T} [data-content]").fill("x" * 4097)
    assert "zu lang" in page.inner_text(f"{T} .tg-step >> nth=0")
    page.locator(f"{T} [data-content]").fill("Hallo")
    page.locator(f"{T} .tg-step").first.locator("[data-pause]").select_option("custom")
    page.locator(f"{T} .tg-step").first.locator("[data-pause-n]").fill("1.5")
    assert "ganze Zahl" in page.inner_text(f"{T} .tg-step >> nth=0")
    page.locator(f"{T} .tg-step").first.locator("[data-pause-n]").fill("2")
    page.locator(f"{T} .tg-step").first.locator("[data-pause-unit]").select_option("min")
    assert "2 Min Pause" in page.inner_text(f"{T} .tg-arrow")
    page.locator(f"{T} .tg-step").nth(1).locator('[data-act="remove"]').click()   # empty step: no confirmation
    assert page.locator(f"{T} .tg-step").count() == 1

    page.click(f'{T} [data-act="save"]')
    page.wait_for_selector("#toasts >> text=Ablauf gespeichert")
    assert shape(ok(api.get(W))[0]) == [("text", 120)]

    # leaving with unsaved changes asks first
    page.locator(f"{T} [data-content]").fill("Anders")
    assert page.is_visible(f"{T} [data-dirty]")
    dialogs.clear()
    page.click(f'{T} [data-act="back"]')
    assert any("Ungespeicherte" in d for d in dialogs)
    page.wait_for_selector(f"{T} .tg-wf-card")
    assert ok(api.get(W))[0]["steps"][0]["content"] == "Hallo"

    # names are shown escaped; rename, duplicate, delete from the list
    assert page.locator(f"{T} .tg-wf-card i").count() == 0 and "<i>Test</i>" in page.inner_text(f"{T} .tg-wf-card")
    page.click(f'{T} [data-act="rename"]')
    page.fill("#modal input[name=name]", "Umbenannt")
    page.click("#modal [type=submit]")
    page.wait_for_selector(f"{T} .tg-wf-card:has-text('Umbenannt')")
    page.click(f'{T} [data-act="duplicate"]')
    page.wait_for_selector(f"{T} .tg-wf-card:has-text('Umbenannt (Kopie)')")
    page.click(f'{T} .tg-wf-card >> nth=1 >> [data-act="delete"]')
    page.wait_for_function("document.querySelectorAll('#tab-telegram-workflows .tg-wf-card').length === 1")
    assert [w["name"] for w in ok(api.get(W))] == ["Umbenannt"]
    assert not problems, problems


def test_server_errors_are_shown_in_german(ui):
    app, api, open_page, _ = ui
    ok(api.post(W, json={"name": "Doppelt", "steps": [{"type": "text", "content": "a", "pause_after": 0}]}), 200)
    page, problems = open_page("de")
    page.click(f'{T} [data-act="new"]')
    page.fill(f"{T} [data-name]", "doppelt")
    add_step(page, "text")
    page.locator(f"{T} [data-content]").fill("b")
    page.click(f'{T} [data-act="save"]')
    page.wait_for_function("document.querySelector('#tab-telegram-workflows [data-err=name]').textContent.length > 0")
    assert page.inner_text(f'{T} [data-err="name"]') == "Ein Ablauf mit diesem Namen existiert bereits"

    add_step(page, "voice")
    page.locator(f"{T} .tg-step").last.locator("[data-file]").set_input_files(file_arg("x.ogg", b"not audio", "audio/ogg"))
    page.wait_for_selector("#toasts >> text=Dateityp nicht unterstützt")
    assert not [p for p in problems if "HTTP 422" not in p and "HTTP 409" not in p and "Failed to load" not in p]


def test_a_voice_step_can_be_replaced_and_the_old_file_is_released(ui):
    app, api, open_page, _ = ui
    old = ok(api.post(M, files=[("files", ("old.ogg", VOICE_A))]))["saved"][0]["name"]
    ok(api.post(W, json={"name": "Mit Sprachmemo", "steps": [{"type": "voice", "file": old, "pause_after": 0}]}))
    page, problems = open_page("de")
    page.click(f"{T} .tg-wf-card")
    page.wait_for_selector(f"{T} .tg-step audio")
    assert "Sprachmemo ersetzen" in page.inner_text(f"{T} .tg-step")
    upload(page, last_card(page), "new.ogg", VOICE_B, "audio/ogg")
    page.wait_for_function("(old) => !document.querySelector('#tab-telegram-workflows audio').src.includes(old)", arg=old)
    page.click(f'{T} [data-act="save"]')
    page.wait_for_selector("#toasts >> text=Ablauf gespeichert")
    new = ok(api.get(W))[0]["steps"][0]["file"]
    assert new != old
    assert {m["name"]: m["used_by"] for m in ok(api.get(M))} == {old: [], new: ["Mit Sprachmemo"]}
    ok(api.delete(f"{M}/{old}"))
    assert not problems, problems
