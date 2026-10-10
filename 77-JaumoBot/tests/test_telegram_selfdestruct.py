"""Self-destructing media ("Anzeigedauer nach dem Öffnen"): an image can be shown once or for 3 / 10 / 30 seconds, a voice
message only played once. Validation, and what the run really hands to Telegram (the fake records the ttl)."""

import pytest

from conftest import jpeg_bytes, ok
from test_telegram_accounts import ENV  # noqa: F401
from test_telegram_runs import (chat_ids, linked, make_workflow, outbox, rig, scn, start, text_step,  # noqa: F401
                                upload, wait_status)
from test_telegram_workflows import W, ogg_opus, tg  # noqa: F401

VIEW_ONCE = 2147483647      # 0x7FFFFFFF, what Telegram's own apps send for "Einmalig zeigen"


def detail(r):
    return r.json()["detail"]


def image(api):
    return upload(api, "p.jpg", jpeg_bytes(1, (60, 40)))


def voice(api):
    return upload(api, "v.ogg", ogg_opus(2))


# --- validation ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("value", ["once", 3, 10, 30])
def test_an_image_accepts_every_display_time_of_telegram(tg, value):
    _, api = tg
    name = image(api)
    w = ok(api.post(W, json={"name": "x", "steps": [{"type": "image", "file": name, "self_destruct": value, "pause_after": 0}]}))
    assert w["steps"][0]["self_destruct"] == value
    assert ok(api.get(W))[0]["steps"][0]["self_destruct"] == value      # and it survives the round trip


def test_media_that_stays_has_no_self_destruct_key(tg):
    _, api = tg
    name = image(api)
    steps = ok(api.post(W, json={"name": "x", "steps": [{"type": "image", "file": name, "pause_after": 0}]}))["steps"]
    assert steps == [{"type": "image", "file": name, "pause_after": 0}]


@pytest.mark.parametrize("value", [5, 0, -1, 31, 3.5, "3", "never", "ONCE", True, False, [], {}, ""])
def test_an_image_refuses_other_display_times(tg, value):
    _, api = tg
    r = api.post(W, json={"name": "x", "steps": [{"type": "image", "file": image(api), "self_destruct": value, "pause_after": 0}]})
    assert r.status_code == 422 and "self_destruct must be one of" in detail(r), (value, r.text)


def test_a_voice_message_can_only_be_played_once(tg):
    _, api = tg
    name = voice(api)
    ok(api.post(W, json={"name": "once", "steps": [{"type": "voice", "file": name, "self_destruct": "once", "pause_after": 0}]}))
    for value in (3, 10, 30):
        r = api.post(W, json={"name": f"t{value}", "steps": [{"type": "voice", "file": name, "self_destruct": value, "pause_after": 0}]})
        assert r.status_code == 422 and "once" in detail(r), (value, r.text)


def test_a_text_step_has_no_display_time(tg):
    _, api = tg
    steps = ok(api.post(W, json={"name": "x", "steps": [{**text_step("Hallo"), "self_destruct": "once"}]}))["steps"]
    assert steps == [text_step("Hallo")]       # not a media step: the field is dropped


# --- what is sent ------------------------------------------------------------------------------------------

def test_the_run_sends_the_chosen_display_time_to_telegram(linked):
    app, api, scn, acc = linked
    img, vo = image(api), voice(api)
    wf = make_workflow(api, [
        {"type": "image", "file": img, "self_destruct": "once", "pause_after": 0},
        {"type": "image", "file": img, "self_destruct": 10, "pause_after": 0},
        {"type": "image", "file": img, "pause_after": 0},
        {"type": "voice", "file": vo, "self_destruct": "once", "pause_after": 0},
        {"type": "voice", "file": vo, "pause_after": 0}])
    wait_status(api, start(api, acc, wf, chat_ids(api, acc, 1001))["id"], "done")
    sent = outbox(scn)
    assert [(m["type"], m.get("ttl")) for m in sent] == [("image", VIEW_ONCE), ("image", 10), ("image", None),
                                                          ("voice", VIEW_ONCE), ("voice", None)]
    assert sent[3]["duration"] == 2 and sent[4]["duration"] == 2     # the voice length is still passed along
