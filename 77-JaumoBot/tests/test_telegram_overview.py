"""The Telegram card of the main dashboard (GET /api/modules/summary) and the reply tracking behind its "Antworten" number.
A reply = the contact answered something we sent: live (a message that arrives after we wrote) or found by a later sync.
The reset button of the dashboard is gone for good (the client was afraid to delete the statistics by accident)."""

from datetime import datetime, timedelta, timezone

import httpx

from conftest import ok, wait_until
from test_telegram_chats import chats, dlg, wait_sync
from test_telegram_runs import (T, chat_ids, chat_row, linked, make_workflow, rig, scn, start,  # noqa: F401
                                text_step, wait_status)


def summary(api):
    return ok(api.get("/api/modules/summary"))


def values(api):
    return [m["value"] for m in summary(api)[0]["metrics"]]


def incoming(scn, i, text="Danke!", **kw):
    scn.incoming(id=1000 + i, access_hash=5000 + i, first_name=f"User{i}", username=f"user{i}", text=text, **kw)


def replied(api, tid):
    return next(c for c in chats(api)["items"] if c["telegram_id"] == str(tid))["replied_at"]


# --- the card -----------------------------------------------------------------------------------------------

def test_the_summary_needs_a_login(app):
    assert httpx.Client(base_url=app.url).get("/api/modules/summary").status_code in (401, 403)


def test_without_an_account_the_card_is_offline_and_zero(api):
    card, = summary(api)
    assert (card["key"], card["title"], card["status"], card["link"]) == ("telegram", "Telegram", "offline", "telegram-dashboard")
    assert card["color"] == "#229ED9" and card["icon"] == "send"
    assert [m["value"] for m in card["metrics"]] == [0, 0, 0]
    assert [m["label"]["en"] for m in card["metrics"]] == ["Open chats", "Sent", "Replies"]
    assert [m["label"]["de"] for m in card["metrics"]] == ["Offene Chats", "Gesendet", "Antworten"]


def test_the_card_counts_open_chats_sent_messages_and_replies(linked):
    app, api, scn, acc = linked
    assert summary(api)[0]["status"] == "active" and values(api) == [5, 0, 0]
    wf = make_workflow(api, [text_step("a"), text_step("b")])
    wait_status(api, start(api, acc, wf, chat_ids(api, acc, 1001, 1002))["id"], "done")
    assert values(api) == [3, 4, 0]                     # 5 chats - 2 processed, 2 chats x 2 messages
    ok(api.post(f"{T}/accounts/{acc['id']}/disconnect"))
    assert summary(api)[0]["status"] == "offline"       # no account online any more


# --- replies --------------------------------------------------------------------------------------------------

def test_a_contact_that_answers_after_our_message_counts_once(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("Hallo")])
    wait_status(api, start(api, acc, wf, chat_ids(api, acc, 1001))["id"], "done")
    assert replied(api, 1001) is None
    incoming(scn, 1)
    first = wait_until(lambda: replied(api, 1001), msg="the reply to be noticed")
    assert datetime.fromisoformat(first.replace("Z", "+00:00")).year >= 2026
    assert values(api) == [4, 1, 1] and ok(api.get(f"{T}/stats"))["chats"]["replied"] == 1
    incoming(scn, 1, text="noch eine", date=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat())
    wait_until(lambda: any(c["last_message"] == "noch eine" for c in chats(api)["items"]), msg="the second message to be stored")
    assert replied(api, 1001) == first and values(api)[2] == 1      # the first answer is kept, the chat counts once


def test_a_message_from_a_chat_we_never_wrote_to_is_not_a_reply(linked):
    app, api, scn, acc = linked
    incoming(scn, 2, text="Hallo, ich schreibe zuerst")
    wait_until(lambda: any(c["last_message"] == "Hallo, ich schreibe zuerst" for c in chats(api)["items"]), msg="live message")
    assert replied(api, 1002) is None and values(api)[2] == 0


def test_a_message_that_came_before_our_first_one_is_not_a_reply(linked):
    app, api, scn, acc = linked
    incoming(scn, 3, text="vorher")
    wait_until(lambda: any(c["last_message"] == "vorher" for c in chats(api)["items"]), msg="live message")
    wf = make_workflow(api, [text_step("Hallo")])
    wait_status(api, start(api, acc, wf, chat_ids(api, acc, 1003))["id"], "done")
    assert replied(api, 1003) is None and values(api)[2] == 0


def test_a_reply_that_arrived_while_the_server_was_away_is_found_by_the_next_sync(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("Hallo")])
    wait_status(api, start(api, acc, wf, chat_ids(api, acc, 1004, 1005))["id"], "done")
    later = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    # 1004 wrote after our run, 1005 has only the old message; 1003 was never messaged but has a newer message
    scn.dialogs([dlg(1), dlg(2), dlg(3, date=later), dlg(4, date=later), dlg(5)])
    ok(api.post(f"{T}/accounts/{acc['id']}/sync-chats"))
    wait_sync(api)
    assert replied(api, 1004) is not None
    assert replied(api, 1005) is None and replied(api, 1003) is None
    assert values(api)[2] == 1


def test_the_chat_list_tells_who_replied(linked):
    app, api, scn, acc = linked
    wf = make_workflow(api, [text_step("Hallo")])
    ids = chat_ids(api, acc, 1001)
    wait_status(api, start(api, acc, wf, ids)["id"], "done")
    incoming(scn, 1)
    wait_until(lambda: chat_row(api, ids[0])["replied_at"], msg="reply")
    assert all("replied_at" in c for c in chats(api)["items"])


# --- the reset is gone ---------------------------------------------------------------------------------------

def test_there_is_no_reset_any_more(api):
    for method in ("post", "put", "delete"):
        assert getattr(api, method)(f"{T}/reset").status_code in (404, 405)
    panel = httpx.get(str(api.base_url) + "/modules-static/telegram/panel.js").text
    assert "Daten auf null setzen" not in panel and "/reset`" not in panel
