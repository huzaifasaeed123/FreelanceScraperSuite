"""The "block user" workflow step: a final action that blocks the contact on Telegram after the messages went out.
Validation (only as the last step), the run (BlockRequest to the stored peer, not counted as a message, the chat is
flagged), a failing block and the API fields."""

import json

import pytest

from conftest import ok
from test_telegram_accounts import ENV  # noqa: F401
from test_telegram_runs import (T, chat_ids, chat_row, linked, make_workflow, outbox, rig, run_chats,  # noqa: F401
                                scn, script_errors, start, text_step, upload, wait_status)
from test_telegram_workflows import W, ogg_opus, tg  # noqa: F401

BLOCK = {"type": "block", "pause_after": 0}


def detail(r):
    return r.json()["detail"]


# --- validation ------------------------------------------------------------------------------------------

def test_block_is_accepted_as_the_last_step_and_stored_without_content_or_pause(tg):
    _, api = tg
    r = ok(api.post(W, json={"name": "Mit Blockade", "steps": [text_step("Hallo", 30), {"type": "block", "pause_after": 45,
                                                                                     "content": "ignored", "file": "x"}]}))
    assert r["steps"][1] == {"type": "block", "pause_after": 0}      # a block step has no pause and nothing to send
    assert ok(api.get(W))[0]["steps"] == r["steps"]
    assert ok(api.put(f"{W}/{r['id']}", json={"name": "Mit Blockade", "steps": r["steps"]}))["steps"] == r["steps"]


def test_block_is_refused_anywhere_but_last(tg):
    _, api = tg
    for steps in ([BLOCK, text_step("danach")],
                  [text_step("a"), BLOCK, text_step("b")],
                  [text_step("a"), BLOCK, BLOCK]):
        r = api.post(W, json={"name": "x", "steps": steps})
        assert r.status_code == 422 and "only allowed as the last step" in detail(r), (steps, r.text)
    assert ok(api.get(W)) == []


def test_a_workflow_may_consist_of_the_block_step_alone(tg):
    _, api = tg
    ok(api.post(W, json={"name": "Nur blockieren", "steps": [BLOCK]}))


def test_the_workflow_copy_keeps_the_block_step(tg):
    _, api = tg
    w = ok(api.post(W, json={"name": "Orig", "steps": [text_step("a"), BLOCK]}))
    copy = ok(api.post(f"{W}/{w['id']}/duplicate", json={}))
    assert copy["steps"] == w["steps"]


# --- running ---------------------------------------------------------------------------------------------

def test_a_run_sends_the_messages_and_then_blocks_each_contact(linked):
    app, api, scn, acc = linked
    voice = upload(api, "v.ogg", ogg_opus(2))
    wf = make_workflow(api, [text_step("Hallo"), {"type": "voice", "file": voice, "pause_after": 0}, BLOCK])
    ids = chat_ids(api, acc, 1002, 1001)
    r = start(api, acc, wf, ids)
    final = wait_status(api, r["id"], "done")
    assert (final["processed"], final["success"], final["errors"]) == (2, 2, 0)

    sent = outbox(scn)
    assert [(m["chat_id"], m["type"]) for m in sent] == [(1002, "text"), (1002, "voice"), (1002, "block"),
                                                          (1001, "text"), (1001, "voice"), (1001, "block")]
    block = sent[2]      # blocked through the stored (id, access_hash), like every other send
    assert (block["peer"], block["access_hash"]) == ("InputPeerUser", 5002)

    for cid in ids:
        c = chat_row(api, cid)
        assert (c["chat_status"], c["messages_sent"], c["blocked"], c["error_reason"]) == ("done", 2, True, "")
    rows = run_chats(api, r["id"])
    assert [(x["status"], x["steps_done"]) for x in rows] == [("done", 3), ("done", 3)]


def test_contacts_outside_the_run_and_runs_without_the_step_are_not_blocked(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("Hallo")])
    ids = chat_ids(api, acc, 1001, 1002)
    wait_status(api, start(api, acc, wf, ids[:1])["id"], "done")
    assert chat_row(api, ids[0])["blocked"] is False and chat_row(api, ids[1])["blocked"] is False
    assert all(m["type"] != "block" for m in outbox(scn))


def test_a_failing_block_marks_that_chat_as_an_error_and_the_run_goes_on(linked):
    app, api, scn, acc = linked
    script_errors(scn, c1001={"error": "UserPrivacyRestrictedError", "after": 1, "times": 1})   # the text goes, the block fails
    wf = make_workflow(api, [text_step("Hallo"), BLOCK])
    ids = chat_ids(api, acc, 1001, 1002)
    r = start(api, acc, wf, ids)
    final = wait_status(api, r["id"], "done")
    assert (final["processed"], final["success"], final["errors"]) == (2, 1, 1)
    first, second = chat_row(api, ids[0]), chat_row(api, ids[1])
    assert (first["chat_status"], first["messages_sent"], first["blocked"]) == ("error", 1, False)
    assert (second["chat_status"], second["messages_sent"], second["blocked"]) == ("done", 1, True)
    rows = run_chats(api, r["id"])
    assert [(x["status"], x["steps_done"]) for x in rows] == [("error", 1), ("done", 2)]
    assert [(m["chat_id"], m["type"]) for m in outbox(scn)] == [(1001, "text"), (1002, "text"), (1002, "block")]


def test_the_chat_list_reports_blocked_contacts(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("Hallo"), BLOCK])
    ids = chat_ids(api, acc, 1003)
    wait_status(api, start(api, acc, wf, ids)["id"], "done")
    items = {c["telegram_id"]: c for c in ok(api.get(f"{T}/chats", params={"account_id": acc["id"], "limit": 100}))["items"]}
    assert items["1003"]["blocked"] is True and items["1004"]["blocked"] is False
    assert "access_hash" not in json.dumps(items["1003"])
