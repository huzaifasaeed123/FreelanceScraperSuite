"""'Chat vor dem Ablauf öffnen': before the first message of a chat the contact's messages are marked as read (the two ticks),
once per chat, optional per run, and a failure of that call never fails the chat. The fake writes reads.jsonl."""

import json
from datetime import datetime

from conftest import ok, wait_until
from test_telegram_accounts import ENV  # noqa: F401
from test_telegram_runs import (T, chat_ids, control, linked, make_workflow, outbox, rig, run, scn, start,  # noqa: F401
                                text_step, wait_sent, wait_status)


def reads(scn):
    path = scn.dir / "reads.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
    for r in rows:
        r["t"] = datetime.fromisoformat(r["ts"]).timestamp()
    return rows


def test_every_chat_is_opened_once_before_its_first_message(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("a"), text_step("b"), text_step("c")])
    started = start(api, acc, wf, chat_ids(api, acc, 1002, 1001))
    assert started["mark_read"] is True                       # on by default
    wait_status(api, started["id"], "done")

    opened, sent = reads(scn), outbox(scn)
    assert [r["chat_id"] for r in opened] == [1002, 1001]     # one per chat, in the order of the run, not before every step
    for r in opened:
        first = min(m["t"] for m in sent if m["chat_id"] == r["chat_id"])
        assert r["t"] <= first, "the chat must be opened before its first message"
        assert r["peer"] == "InputPeerUser"                   # addressed by the stored (id, access_hash) like every send
    assert opened[0]["access_hash"] == 5002 and opened[1]["access_hash"] == 5001
    assert [m["content"] for m in sent] == ["a", "b", "c"] * 2       # nothing else changed in what is sent


def test_without_the_option_nothing_is_marked_as_read(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("a")])
    started = start(api, acc, wf, chat_ids(api, acc, 1001), mark_read=False)
    assert started["mark_read"] is False
    wait_status(api, started["id"], "done")
    assert reads(scn) == [] and [m["content"] for m in outbox(scn)] == ["a"]


def test_a_failing_read_does_not_fail_the_chat(linked):
    app, api, scn, acc = linked
    (scn.dir / "control.json").write_text(json.dumps({"read_fails": True}))
    wf = make_workflow(api, [text_step("a"), text_step("b")])
    final = wait_status(api, start(api, acc, wf, chat_ids(api, acc, 1001, 1002))["id"], "done")
    assert (final["processed"], final["success"], final["errors"]) == (2, 2, 0)
    assert len(outbox(scn)) == 4 and reads(scn) == []


def test_a_chat_that_is_resumed_in_the_middle_is_not_opened_again(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("a", 3), text_step("b")])
    r = start(api, acc, wf, chat_ids(api, acc, 1001))
    wait_sent(scn, 1)
    control(api, r["id"], "pause")
    control(api, r["id"], "resume")
    wait_status(api, r["id"], "done")
    assert len(reads(scn)) == 1 and [m["content"] for m in outbox(scn)] == ["a", "b"]


def test_restarting_a_run_keeps_its_option(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("a")])
    first = start(api, acc, wf, chat_ids(api, acc, 1001), mark_read=False)
    wait_status(api, first["id"], "done")
    again = control(api, first["id"], "restart")
    wait_status(api, again["id"], "done")
    assert again["mark_read"] is False and reads(scn) == []
    assert run(api, again["id"])["mark_read"] is False        # also what the run list and the live panel read
