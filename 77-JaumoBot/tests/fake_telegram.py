"""In-process stand-in for Telethon's TelegramClient. The server under test loads it through
TELEGRAM_CLIENT_FACTORY=fake_telegram:FakeClient, so no request ever reaches Telegram.

Scripted behaviour:
  login code                 12345
  +4915100000002             has two-step verification, password "secret"
  +4915100000009             rejected as an invalid phone number
  api_hash "bad"             rejected as an invalid API ID / Hash
  session "fake:revoked"     Telegram has ended it (is_user_authorized() is False)
  session "fake:unreachable" connect() fails with a network error

Scenario seam (chats and sending). Point the server at a folder with FAKE_TG_DIR=<dir>; the files are read when
needed, so a test may create and change them while the server runs:
  dialogs.json   [{"id", "access_hash", "first_name", "last_name", "username", "bot", "deleted", "last_message",
                   "date" (ISO), "kind" ("user", default; anything else is a group/channel dialog)}, ...]
                 returned by iter_dialogs() for every account. An entry whose id is the account's own id is its
                 "Saved Messages".
  inbox.jsonl    one JSON object per line, appended while a client is connected: the user fields above plus
                 "text", optional "date", "out" (true = sent by us) and "to" (phone; default: every client). The
                 fake client tails the file and calls the handlers registered with add_event_handler.
  outbox.jsonl   written by the fake: every send_message / send_file as
                 {ts, account, chat_id, access_hash, peer (class name of the recipient), type, content|file}
                 (type: text | image | voice | block; block = the contact was blocked).
  send_errors.json  {"<chat_id>": {"error": "UserPrivacyRestrictedError", "times": 2, "seconds": 3}}: sends to that
                 chat fail with that Telethon error (or "ConnectionError"); "times" limits how often (default:
                 always, counted down in the file); "after" lets that many sends succeed first; "seconds" is the
                 wait of a FloodWaitError.
  flood_once.txt seconds; the next iter_dialogs() raises FloodWaitError(seconds) once and deletes the file.
  control.json   {"drop": [...], "down": [...], "revoke": [...], "ban": [...], "probe_error": [...]}, each a list of phones
                 ("*" = every account); read every 0.1 s and whenever a request is made, so a test can change it while the
                 server runs:
                 drop   one-shot: a connected client of that account loses its connection (is_connected() turns False,
                        as when Telethon gave up reconnecting); the entry is removed once it has been applied
                 down   the network is down while listed: connected clients drop, connect() fails with a ConnectionError
                 revoke Telegram ended the session: get_me() returns None, is_user_authorized() is False, sends fail with
                        AuthKeyUnregisteredError
                 ban    the account was banned: get_me() returns None, sends fail with UserDeactivatedBanError
                 probe_error  get_me() fails with an unexpected error
                 drop_on_send one-shot: the next send drops the connection and fails with a ConnectionError
                 send_delay   number of seconds every send takes (so a test can act while a send is in flight)
                 dump_tasks   true: every connected client writes tasks.json = {"ts", "tasks": [coroutine names of all
                              unfinished asyncio tasks of the server]} about every 0.1 s, to look for leaked tasks
  reads.jsonl    written by the fake: every chat marked as read {ts, account, chat_id, access_hash, peer};
                 control.json "read_fails": true makes that call fail
  connections.jsonl  written by the fake: {"client": <object id>, "event": "connect" | "connect_failed" | "disconnect"}, so a
                 test can count connection attempts and prove that every connection the server opened was closed again.
  FAKE_TG_DIALOG_DELAY (env)  seconds iter_dialogs() sleeps per dialog, to keep a sync running for a while.
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from telethon import errors

CODE = "12345"
PASSWORD = "secret"
TWO_STEP_PHONES = {"+4915100000002"}
INVALID_PHONES = {"+4915100000009"}


def _dir():
    d = os.environ.get("FAKE_TG_DIR")
    return Path(d) if d else None


def _when(value):
    if not value:
        return datetime.now(timezone.utc)
    d = datetime.fromisoformat(value)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _control():
    d = _dir()
    path = d and d / "control.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path and path.exists() else {}
    except ValueError:      # the test is writing the file right now
        return {}


def _user(d):
    return SimpleNamespace(id=d["id"], access_hash=d.get("access_hash"), first_name=d.get("first_name", ""),
                           last_name=d.get("last_name", ""), username=d.get("username"),
                           bot=d.get("bot", False), deleted=d.get("deleted", False))


class _Session:
    def __init__(self, value):
        self.value = value

    def save(self):
        return self.value


class FakeClient:
    def __init__(self, session, api_id, api_hash):
        self.session = _Session(session or "")
        self.api_hash = api_hash
        self.connected = False
        self.phone = None
        self.handlers = []
        self._tail = None
        self._logged = False

    def _listed(self, key):
        """Is this client's account named under `key` in control.json?"""
        phones = _control().get(key, [])
        return "*" in phones or (self._phone() or "") in phones

    def _phone(self):
        return self.phone or self.session.value.removeprefix("fake:")

    def _log_connection(self, event):
        d = _dir()
        if d:
            with open(d / "connections.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"client": id(self), "event": event}) + "\n")

    async def connect(self):
        if self.session.value == "fake:unreachable" or self._listed("down"):
            self._log_connection("connect_failed")
            raise ConnectionError("network down")
        self.connected = True
        self._logged = True
        self._log_connection("connect")
        inbox = _dir() and _dir() / "inbox.jsonl"
        offset = inbox.stat().st_size if inbox and inbox.exists() else 0   # only messages that arrive from now on
        self._tail = asyncio.create_task(self._tail_inbox(offset))

    async def disconnect(self):
        if self._logged:
            self._logged = False
            self._log_connection("disconnect")
        self.connected = False
        tail, self._tail = self._tail, None
        if tail:
            tail.cancel()
            await asyncio.gather(tail, return_exceptions=True)    # a cancelled task is only finished once it has been awaited

    # --- chats ---

    def add_event_handler(self, callback, event=None):
        self.handlers.append((callback, event))

    async def iter_dialogs(self):
        d = _dir()
        if not d:
            return
        flood = d / "flood_once.txt"
        if flood.exists():
            seconds = int(flood.read_text())
            flood.unlink()
            raise errors.FloodWaitError(None, capture=seconds)
        delay = float(os.environ.get("FAKE_TG_DIALOG_DELAY", "0"))
        path = d / "dialogs.json"
        for item in json.loads(path.read_text(encoding="utf-8")) if path.exists() else []:
            if delay:
                await asyncio.sleep(delay)
            date = _when(item.get("date"))
            yield SimpleNamespace(is_user=item.get("kind", "user") == "user", entity=_user(item), date=date,
                                  message=SimpleNamespace(message=item.get("last_message", ""), date=date, media=None))

    def _apply_control(self):
        """Carry out a scripted connection drop; True when this client lost its connection."""
        ctl = _control()
        phones = ctl.get("drop", [])
        if self.connected and ("*" in phones or self._phone() in phones):
            ctl["drop"] = [p for p in phones if p not in ("*", self._phone())]
            (_dir() / "control.json").write_text(json.dumps(ctl), encoding="utf-8")
            self.connected = False
        elif self.connected and self._listed("down"):
            self.connected = False
        return not self.connected

    async def _tail_inbox(self, offset):
        while True:
            await asyncio.sleep(0.1)
            if _dir() and self._apply_control():
                return
            if _dir() and _control().get("dump_tasks"):
                self._dump_tasks()
            d = _dir()
            inbox = d and d / "inbox.jsonl"
            if not inbox or not inbox.exists():
                continue
            with open(inbox, "rb") as f:
                f.seek(offset)
                data = f.read()
            end = data.rfind(b"\n") + 1           # a half-written last line waits for the next round
            offset += end
            for line in data[:end].decode("utf-8").splitlines():
                if line.strip():
                    await self._dispatch(json.loads(line))

    def _dump_tasks(self):
        names = sorted(getattr(t.get_coro(), "__qualname__", repr(t)) for t in asyncio.all_tasks() if not t.done())
        tmp = _dir() / "tasks.json.tmp"
        tmp.write_text(json.dumps({"ts": time.time(), "tasks": names}), encoding="utf-8")
        os.replace(tmp, _dir() / "tasks.json")

    async def _dispatch(self, item):
        if item.get("to") and item["to"] != self.session.value.removeprefix("fake:"):
            return
        user = _user(item)

        async def get_sender():
            if item.get("sender_error"):
                raise RuntimeError("sender lookup failed")
            return user

        event = SimpleNamespace(is_private=item.get("kind", "user") == "user", out=bool(item.get("out")),
                                get_sender=get_sender,
                                message=SimpleNamespace(message=item.get("text", ""), date=_when(item.get("date")),
                                                        media=None))
        for callback, _ in self.handlers:
            try:
                await callback(event)
            except Exception as e:  # noqa: BLE001 — Telethon logs a failing handler and carries on with the next update
                print(f"[fake telegram] handler failed: {type(e).__name__}: {e}")

    # --- sending (recorded for the tests) ---

    def _fail_if_scripted(self, entity):
        if not self.connected:
            raise ConnectionError("not connected")
        if self._listed("drop_on_send"):
            ctl = _control()
            ctl["drop_on_send"] = [p for p in ctl["drop_on_send"] if p not in ("*", self._phone())]
            (_dir() / "control.json").write_text(json.dumps(ctl), encoding="utf-8")
            self.connected = False
            raise ConnectionError("connection lost while sending")
        if self._listed("revoke"):
            raise errors.AuthKeyUnregisteredError(None)
        if self._listed("ban"):
            raise errors.UserDeactivatedBanError(None)
        d = _dir()
        path = d and d / "send_errors.json"
        if not path or not path.exists():
            return
        scripts = json.loads(path.read_text(encoding="utf-8"))
        script = scripts.get(str(getattr(entity, "user_id", entity)))
        if not script or script.get("times") == 0:
            return
        if script.get("after"):
            script["after"] -= 1
            path.write_text(json.dumps(scripts), encoding="utf-8")
            return
        if "times" in script:
            script["times"] -= 1
            path.write_text(json.dumps(scripts), encoding="utf-8")
        name = script["error"]
        if name == "ConnectionError":
            raise ConnectionError("network down")
        if name == "FloodWaitError":
            raise errors.FloodWaitError(None, capture=script.get("seconds", 1))
        raise getattr(errors, name)(None)

    def _record(self, entity, kind, **fields):
        self._fail_if_scripted(entity)
        d = _dir()
        if d:
            line = {"ts": datetime.now(timezone.utc).isoformat(), "account": self.session.value.removeprefix("fake:"),
                    "chat_id": getattr(entity, "user_id", entity), "access_hash": getattr(entity, "access_hash", None),
                    "peer": type(entity).__name__, "type": kind, **fields}
            with open(d / "outbox.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(line) + "\n")

    async def _send_delay(self):
        # a real send waits for the network, so the event loop serves other requests meanwhile (sleep(0) yields too)
        await asyncio.sleep(_control().get("send_delay", 0))

    async def send_message(self, entity, message, **kwargs):
        await self._send_delay()
        self._record(entity, "text", content=message)

    async def send_file(self, entity, file, voice_note=False, **kwargs):
        await self._send_delay()
        extra = {}
        for attr in kwargs.get("attributes") or []:            # what a voice message says about itself
            if getattr(attr, "duration", None) is not None:
                extra["duration"] = attr.duration
        if kwargs.get("ttl"):                                   # self-destructing media ("view once" = 2147483647)
            extra["ttl"] = kwargs["ttl"]
        self._record(entity, "voice" if voice_note else "image", file=str(file), **extra)

    async def send_read_acknowledge(self, entity, message=None, **kwargs):
        """The chat was opened: the contact's messages are marked as read. Written to reads.jsonl (not to the outbox, so the
        assertions on sends stay as they are); control.json {"read_fails": true} makes it fail."""
        if _control().get("read_fails"):
            raise ConnectionError("could not mark as read")
        d = _dir()
        if d:
            line = {"ts": datetime.now(timezone.utc).isoformat(), "account": self.session.value.removeprefix("fake:"),
                    "chat_id": getattr(entity, "user_id", entity), "access_hash": getattr(entity, "access_hash", None),
                    "peer": type(entity).__name__}
            with open(d / "reads.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(line) + "\n")
        return True

    async def __call__(self, request):
        """Raw Telegram requests: only BlockRequest is used. It is recorded as a "block" in the outbox and can be
        made to fail with send_errors.json like any send."""
        if type(request).__name__ != "BlockRequest":
            raise NotImplementedError(type(request).__name__)
        await self._send_delay()
        self._record(request.id, "block")
        return True

    def is_connected(self):
        return self.connected

    async def is_user_authorized(self):
        return bool(self.session.value) and not self.session.value.startswith("fake:revoked") and not self._listed("revoke")

    async def send_code_request(self, phone):
        if self.api_hash == "bad":
            raise errors.ApiIdInvalidError(None)
        if phone in INVALID_PHONES:
            raise errors.PhoneNumberInvalidError(None)
        self.phone = phone
        return SimpleNamespace(phone_code_hash="hash-" + phone)

    async def sign_in(self, phone=None, code=None, *, password=None, bot_token=None, phone_code_hash=None):
        if password is not None:
            if password != PASSWORD:
                raise errors.PasswordHashInvalidError(None)
        else:
            self.phone = phone or self.phone
            if str(code) != CODE:
                raise errors.PhoneCodeInvalidError(None)
            if self.phone in TWO_STEP_PHONES:
                raise errors.SessionPasswordNeededError(None)
        self.session = _Session(f"fake:{self.phone}")
        return await self.get_me()

    async def get_me(self):
        if self._listed("probe_error"):
            raise RuntimeError("probe failed")
        if self._listed("revoke") or self._listed("ban"):
            return None          # what Telethon returns when the server answers "unauthorized"
        phone = self._phone()
        return SimpleNamespace(id=int(phone[1:]), username="user" + phone[-4:], first_name="Test", last_name=phone[-4:])
