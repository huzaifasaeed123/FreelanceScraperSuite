"""'Daten auf null setzen': the stored chats and all runs of one account (or of all) are deleted so the dashboard
starts from zero again; accounts, workflows and uploaded files stay; chats that still exist in Telegram come back
with the next sync."""

from conftest import ok
from test_telegram_accounts import accounts
from test_telegram_chats import chats, link_synced, wait_sync
from test_telegram_runs import (PHONE_B, T, chat_ids, control, linked, make_workflow, rig, run_chats,  # noqa: F401
                                scn, start, text_step, wait_status)


def stats(api, **params):
    return ok(api.get(f"{T}/stats", params=params))


def test_reset_everything_starts_the_numbers_from_zero(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("Hallo")])
    done = wait_status(api, start(api, acc, wf, chat_ids(api, acc, 1001, 1002))["id"], "done")
    st = stats(api)
    assert (st["chats"]["total"], st["chats"]["processed"], st["runs"], st["sends"]["successful"]) == (5, 2, 1, 2)

    assert ok(api.post(f"{T}/reset", json={})) == {"chats": 5, "runs": 1}

    st = stats(api)
    assert st["chats"] == {"total": 0, "unprocessed": 0, "processed": 0, "errors": 0, "in_progress": 0, "paused": 0}
    assert (st["runs"], st["sends"]["successful"], st["sends"]["failed"], st["sends"]["messages"]) == (0, 0, 0, 0)
    assert st["last_run"] is None and st["active_run"] is None
    assert chats(api)["total"] == 0 and ok(api.get(f"{T}/runs"))["total"] == 0
    assert api.get(f"{T}/runs/{done['id']}").status_code == 404
    # what is not data of the campaign stays
    assert len(ok(api.get(f"{T}/accounts"))) == 1 and accounts(api)["+4915100000001"]["status"] == "online"
    assert [w["name"] for w in ok(api.get(f"{T}/workflows"))] == ["Flow"]


def test_after_the_reset_chats_that_still_exist_are_tracked_again_untouched(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("Hallo")])
    wait_status(api, start(api, acc, wf, chat_ids(api, acc, 1001))["id"], "done")
    ok(api.post(f"{T}/reset", json={}))
    ok(api.post(f"{T}/accounts/{acc['id']}/sync-chats"))
    wait_sync(api)
    items = chats(api)["items"]
    assert len(items) == 5 and {c["chat_status"] for c in items} == {"pending"}      # nothing is marked as processed any more
    assert sum(c["messages_sent"] for c in items) == 0 and not any(c["blocked"] for c in items)
    # and a new run is counted from 1 again
    wait_status(api, start(api, acc, wf, chat_ids(api, acc, 1003))["id"], "done")
    assert (stats(api)["runs"], stats(api)["sends"]["successful"]) == (1, 1)


def test_reset_of_one_account_leaves_the_other_alone(linked):
    app, api, scn, acc = linked
    other = link_synced(api, PHONE_B)
    wf = make_workflow(api, [text_step("Hallo")])
    wait_status(api, start(api, acc, wf, chat_ids(api, acc, 1001))["id"], "done")
    wait_status(api, start(api, other, wf, chat_ids(api, other, 1002, 1003))["id"], "done")
    assert stats(api)["chats"]["total"] == 10 and stats(api)["runs"] == 2

    assert ok(api.post(f"{T}/reset", json={"account_id": acc["id"]})) == {"chats": 5, "runs": 1}
    assert chats(api, account_id=acc["id"])["total"] == 0 and chats(api, account_id=other["id"])["total"] == 5
    assert stats(api)["runs"] == 1 and stats(api, account_id=other["id"])["sends"]["successful"] == 2
    assert stats(api, account_id=acc["id"])["chats"]["total"] == 0


def test_reset_is_refused_while_a_run_is_active_and_works_after_it_was_stopped(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("Hallo", 30), text_step("Noch eins")])
    r = start(api, acc, wf, chat_ids(api, acc, 1001, 1002))
    wait_status(api, r["id"], "running")
    refused = api.post(f"{T}/reset", json={})
    assert refused.status_code == 409 and "still active" in refused.json()["detail"]
    assert chats(api)["total"] == 5                                   # nothing was deleted
    control(api, r["id"], "pause")                                    # a paused run holds data as well
    assert api.post(f"{T}/reset", json={}).status_code == 409
    control(api, r["id"], "stop")
    wait_status(api, r["id"], "stopped")
    assert ok(api.post(f"{T}/reset", json={}))["runs"] == 1


def test_reset_of_an_unknown_account_and_bad_bodies(linked):
    app, api, scn, acc = linked
    assert api.post(f"{T}/reset", json={"account_id": 9999}).status_code == 404
    assert api.post(f"{T}/reset", json={"account_id": "x"}).status_code == 422
    assert chats(api)["total"] == 5
