"""Telegram requirement gaps found by the critic: which message types exist, replacing a step's file, long pauses in a run,
and what the history says about a stopped run (aborted chats, duration, CSV). The browser side of the same gaps is in
test_telegram_workflows_ui.py (replace a file), test_telegram_runs_ui.py (retry option) and test_telegram_chats_ui.py
(first-contact date)."""

import csv
import io
import time

import pytest

from conftest import ok, wait_until
from test_telegram_chats import chats
from test_telegram_runs import (T, chat_ids, control, linked, make_workflow, outbox, rig, run, run_chats, scn, start, text_step,
                                upload, wait_sent, wait_status)
from test_telegram_workflows import ogg_opus


# --- §3 message types: text, image and voice are the supported ones, anything else is refused ---------------------------

@pytest.mark.parametrize("kind", ["video", "document", "file", "sticker", "audio", "gif", "poll"])
def test_other_message_types_are_refused_not_silently_stored(linked, kind):
    app, api, scn, acc = linked
    r = api.post(f"{T}/workflows", json={"name": kind, "steps": [{"type": kind, "file": "x.mp4", "pause_after": 0}]})
    assert r.status_code == 422 and "unknown step type" in r.json()["detail"]
    assert ok(api.get(f"{T}/workflows")) == []


# --- §3 a step can be replaced: the new file is used, the old one is released ----------------------------------------------

def test_replacing_a_steps_file_releases_the_old_one_and_the_run_sends_the_new_one(linked):
    app, api, scn, acc = linked
    old, new = upload(api, "old.ogg", ogg_opus(2)), upload(api, "new.ogg", ogg_opus(3))
    wf = make_workflow(api, [text_step("Hallo", 0), {"type": "voice", "file": old, "pause_after": 0}])
    assert api.delete(f"{T}/media/{old}").status_code == 409               # in use by the workflow
    used = {m["name"]: m["used_by"] for m in ok(api.get(f"{T}/media"))}
    assert used == {old: ["Flow"], new: []}

    steps = [wf["steps"][0], {"type": "voice", "file": new, "pause_after": 0}]
    saved = ok(api.put(f"{T}/workflows/{wf['id']}", json={"name": "Flow", "steps": steps}))
    assert [s.get("file") for s in saved["steps"]] == [None, new]
    used = {m["name"]: m["used_by"] for m in ok(api.get(f"{T}/media"))}
    assert used == {old: [], new: ["Flow"]}
    ok(api.delete(f"{T}/media/{old}"))                                     # released: it can go now
    assert api.delete(f"{T}/media/{new}").status_code == 409

    r = start(api, acc, saved, chat_ids(api, acc, 1001))
    wait_status(api, r["id"], "done")
    assert [m["type"] for m in outbox(scn)] == ["text", "voice"] and outbox(scn)[1]["file"].endswith(new)


# --- §4 pauses of minutes and hours are honoured as seconds -------------------------------------------------------------------

@pytest.mark.parametrize("seconds", [150, 7200, 86400])
def test_long_pauses_are_stored_in_seconds_and_counted_down_by_the_run(linked, seconds):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("a", seconds), text_step("b", 0)])
    assert wf["steps"][0]["pause_after"] == seconds
    r = start(api, acc, wf, chat_ids(api, acc, 1001))
    wait_sent(scn, 1)
    live = wait_until(lambda: (s := run(api, r["id"]))["wait_kind"] == "pause" and s, msg="the pause to start")
    assert seconds - 5 <= live["seconds_remaining"] <= seconds
    paused = control(api, r["id"], "pause")
    time.sleep(1.2)
    assert abs(run(api, r["id"])["seconds_remaining"] - paused["seconds_remaining"]) < 0.2      # frozen, not counting down
    assert len(outbox(scn)) == 1                                                             # the second step waits for the pause
    control(api, r["id"], "stop")


# --- §12 history of a run that did not finish ---------------------------------------------------------------------------------

def test_a_stopped_run_reports_aborted_chats_duration_and_the_audit_trail(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("a", 30), text_step("b", 0)])
    r = start(api, acc, wf, chat_ids(api, acc, 1001, 1002, 1003))
    wait_sent(scn, 1)
    wait_until(lambda: run(api, r["id"])["wait_kind"] == "pause", msg="the pause")
    time.sleep(1.1)
    stopped = control(api, r["id"], "stop")
    assert (stopped["status"], stopped["total"], stopped["processed"], stopped["skipped"]) == ("stopped", 3, 0, 3)
    assert stopped["finished_at"] and isinstance(stopped["duration_seconds"], int) and stopped["duration_seconds"] >= 1

    listed = ok(api.get(f"{T}/runs"))["items"][0]
    assert (listed["id"], listed["skipped"], listed["duration_seconds"]) == (r["id"], 3, stopped["duration_seconds"])
    rows = run_chats(api, r["id"])
    assert [(x["status"], x["steps_done"]) for x in rows] == [("skipped", 1), ("skipped", 0), ("skipped", 0)]
    assert all(x["processed_at"] for x in rows[:1])

    table = list(csv.DictReader(io.StringIO(api.get(f"{T}/runs/export.csv").text.lstrip("﻿"))))
    assert (table[0]["status"], table[0]["aborted"], table[0]["duration_seconds"]) == ("stopped", "3", str(stopped["duration_seconds"]))
    # the chat that got one of two messages is "paused", the two untouched ones are "pending" again
    by_tid = {c["telegram_id"]: c for c in chats(api)["items"]}
    assert [by_tid[t]["chat_status"] for t in ("1001", "1002", "1003")] == ["paused", "pending", "pending"]
    assert by_tid["1002"]["last_processed_at"] is None
