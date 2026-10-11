"""Telegram engine: Telethon sessions of the linked accounts (login with code / two-step password,
connect, disconnect, reconnect at startup), chat capture (live incoming messages + import of existing
dialogs) and the run engine (a workflow sent chat by chat). Runs inside the panel's event loop; api.py calls it.

Tests plug in a fake client with TELEGRAM_CLIENT_FACTORY=module:callable (called as f(session, api_id, api_hash)).

Keeping accounts honest (hardening): a watcher task per connected account notices a lost connection (the account
becomes "connecting", its runs pause, a reconnect loop with growing waits brings it back) and a session Telegram has
ended (the account becomes "error", the login is dropped, its runs pause); a janitor task sweeps abandoned logins.

Telethon surface the chat capture relies on (the fake client in tests/fake_telegram.py mimics exactly this):
  client.add_event_handler(callback, events.NewMessage(incoming=True))
  event:   .is_private, .out, .message (.message text, .date, .media), await event.get_sender()
  client.is_connected(), await client.get_me() (None = Telegram says the session is unauthorized)
  client.iter_dialogs() -> async iterator of dialogs: .is_user, .entity, .message (.message, .date, .media)
  user:    .id, .access_hash, .first_name, .last_name, .username, .bot, .deleted
The run engine sends with
  await client.send_message(InputPeerUser, text)
  await client.send_file(InputPeerUser, path, voice_note=False|True)"""

import asyncio
import importlib
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Optional

from sqlalchemy import or_
from sqlalchemy import update as sa_update
from sqlmodel import Session, select
from telethon import errors, events
from telethon.tl.functions.contacts import BlockRequest
from telethon.tl.types import DocumentAttributeAudio, InputPeerUser

from api.models import engine as db_engine, iso, utcnow

from .api import TgAccount, TgChat, TgRun, TgRunChat  # api.py defines the tables first, then imports this module

LOGIN_WINDOW = float(os.environ.get("TELEGRAM_LOGIN_WINDOW", "300"))     # seconds the operator has to enter the code after it was sent
CONNECT_TIMEOUT = 30
EVENTS = "telegram:events"
SERVICE_CHAT_ID = 777000   # Telegram's own service chat (login codes), never a contact
SYNC_BATCH = 100           # dialogs written per commit
SYNC_FLOOD_RETRIES = 5
ACTIVE_RUN = ("queued", "running", "paused")
RETRY_WAIT = float(os.environ.get("TELEGRAM_RETRY_WAIT", "5"))   # seconds between two attempts (run option on_error = retry)
FLOOD_RETRIES = 10         # FloodWaits waited out for one step before the chat is given up
SLICE = 0.1                # longest sleep between two looks at the pause gate
REASON_OFFLINE = "Account offline"
REASON_RESTART = "Server restarted"
REASON_DROPPED = "Connection to Telegram lost"
# Telegram's "view once" marker for a photo or voice message (what the official apps send as the self-destruct
# time; Telethon's own docs only mention 1-60 seconds). Only works in private chats, which every chat here is.
VIEW_ONCE = 0x7FFFFFFF


def _ttl(step: dict) -> dict:
    """send_file arguments of a step's "show for ..." setting ("once" or seconds); nothing when the media stays."""
    shown = step.get("self_destruct")
    return {} if shown is None else {"ttl": VIEW_ONCE if shown == "once" else int(shown)}
PEER_FLOOD = "Telegram limited this account for writing to new people (PeerFlood)"
# seconds: between two looks at an account's connection / between two checks that Telegram still accepts its session /
# first and longest wait of the reconnect loop (it doubles in between)
WATCH_INTERVAL = float(os.environ.get("TELEGRAM_WATCH_INTERVAL", "5"))
AUTH_PROBE = float(os.environ.get("TELEGRAM_AUTH_PROBE", "300"))
RECONNECT_BASE = float(os.environ.get("TELEGRAM_RECONNECT_BASE", "2"))
RECONNECT_MAX = 60.0
NETWORK_ERRORS = (ConnectionError, OSError, asyncio.TimeoutError)


class TgError(Exception):
    """An error with a message that is safe to show the operator (the panel translates known ones)."""

    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


def default_factory(session: str, api_id: int, api_hash: str):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    return TelegramClient(StringSession(session or None), api_id, api_hash)


def _factory():
    spec = os.environ.get("TELEGRAM_CLIENT_FACTORY")
    if not spec:
        return default_factory
    mod, attr = spec.split(":")
    return getattr(importlib.import_module(mod), attr)


@dataclass
class Pending:
    """A login waiting for the code (and maybe the two-step password)."""
    client: object
    phone: str
    code_hash: str
    expires: float
    needs_password: bool = False


# Telethon error -> message for the operator
_FRIENDLY = [
    (errors.PhoneNumberInvalidError, "Invalid phone number"),
    (errors.ApiIdInvalidError, "API ID / API Hash are not valid (check my.telegram.org)"),
    (errors.PhoneNumberBannedError, "This phone number is banned by Telegram"),
    (errors.PhoneNumberFloodError, "Too many code requests for this number, try again later"),
    (errors.PhoneCodeInvalidError, "The code is wrong"),
    (errors.PhoneCodeEmptyError, "Enter the code"),
    (errors.PhoneCodeExpiredError, "The code has expired, request a new one"),
    (errors.PasswordHashInvalidError, "Wrong two-step verification password"),
    (errors.PhonePasswordFloodError, "Too many password attempts, try again later"),
    (errors.AuthKeyUnregisteredError, "Telegram ended this session, log in again"),
    (errors.SessionRevokedError, "Telegram ended this session, log in again"),
    (errors.SessionExpiredError, "Telegram ended this session, log in again"),
    (errors.UserDeactivatedError, "This Telegram account was deactivated"),
    (errors.UserDeactivatedBanError, "This Telegram account was banned"),
]
SESSION_ENDED = "Telegram ended this session, log in again"
# Telegram will not accept this login any more (revoked, deactivated, banned): only a new login helps
SESSION_ENDED_ERRORS = (errors.AuthKeyUnregisteredError, errors.SessionRevokedError, errors.SessionExpiredError,
                        errors.UserDeactivatedError, errors.UserDeactivatedBanError)


def friendly(e: Exception) -> TgError:
    if isinstance(e, TgError):
        return e
    for cls, msg in _FRIENDLY:
        if isinstance(e, cls):
            return TgError(msg)
    if isinstance(e, errors.FloodWaitError):
        return TgError(f"Telegram asks to wait {e.seconds} s before trying again")
    if isinstance(e, NETWORK_ERRORS):
        return TgError("Could not reach Telegram (network problem)", 502)
    print(f"[telegram] unexpected {type(e).__name__}: {e}")
    return TgError(f"Telegram error: {type(e).__name__}", 502)


async def _quiet_disconnect(client):
    try:
        await client.disconnect()
    except Exception:  # noqa: BLE001 — closing a broken connection must never raise
        pass


# --- chat capture helpers ---------------------------------------------------------------

def _utc(d: Optional[datetime]) -> Optional[datetime]:
    """The database only accepts timezone-aware datetimes; a naive one is taken as UTC."""
    if d is None:
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)


def _is_contact(user, own_id: Optional[str]) -> bool:
    """A real person we can write to: not a bot, a deleted account, ourselves (Saved Messages) or Telegram itself."""
    if user is None or getattr(user, "id", None) is None:
        return False
    if getattr(user, "bot", False) or getattr(user, "deleted", False) or getattr(user, "is_self", False):
        return False
    return user.id != SERVICE_CHAT_ID and str(user.id) != own_id


def _chat_row(user, message, live: bool = False) -> dict:
    """What we store about a chat, from a Telethon user and its latest message."""
    username = getattr(user, "username", None) or ""
    name = " ".join(x for x in (getattr(user, "first_name", None), getattr(user, "last_name", None)) if x)
    text = getattr(message, "message", "") or ("[media]" if getattr(message, "media", None) else "")
    return {"telegram_id": str(user.id), "access_hash": str(getattr(user, "access_hash", None) or ""),
            "display_name": name or username or str(user.id), "username": username,
            "last_message": text[:300], "date": _utc(getattr(message, "date", None)),
            "incoming": not getattr(message, "out", False),      # the latest message is from the contact
            "live": live}                                        # it just arrived (not read from the dialog list)


def upsert_chats(s: Session, acc_id: int, rows: list[dict]) -> list[tuple[TgChat, bool]]:
    """Create or refresh chats by (account, telegram_id); returns (chat, created) pairs. Not committed.
    Only what Telegram tells us is refreshed: the operator's work (chat_status, notes, messages_sent) is never touched."""
    wanted = [r["telegram_id"] for r in rows]
    known = {c.telegram_id: c for c in s.exec(select(TgChat).where(TgChat.account_id == acc_id,
                                                                    TgChat.telegram_id.in_(wanted)))}
    now, result = utcnow(), []
    for r in rows:
        chat, date = known.get(r["telegram_id"]), r["date"]
        created = chat is None
        if created:
            chat = known[r["telegram_id"]] = TgChat(account_id=acc_id, telegram_id=r["telegram_id"])
            # one API call per dialog is far too slow: the earliest message date we know for free is the latest one
            # (or, for a live message, its own date); with no date at all it is the moment we first saw the chat
            chat.first_contact_at = date or now
            chat.last_contact_at, chat.last_message = date or now, r["last_message"]
        else:
            if date and (chat.first_contact_at is None or date < chat.first_contact_at):
                chat.first_contact_at = date
            if date and (chat.last_contact_at is None or date >= chat.last_contact_at):
                chat.last_contact_at, chat.last_message = date, r["last_message"]
        # "Replies": the contact answered something we sent. A live message is an answer as soon as we have sent
        # anything; a dialog read later only counts when the contact's last message is newer than our last run on it.
        if (not created and r.get("incoming") and date and chat.replied_at is None and chat.messages_sent > 0
                and (r.get("live") or (chat.last_processed_at and date > _utc(chat.last_processed_at)))):
            chat.replied_at = date
        chat.display_name, chat.username = r["display_name"], r["username"]
        if r["access_hash"]:
            chat.access_hash = r["access_hash"]
        chat.search_text = _search_text(chat)
        s.add(chat)
        result.append((chat, created))
    return result


def _search_text(chat: TgChat) -> str:
    return f"{chat.display_name} {chat.username} {chat.telegram_id}".casefold()


def backfill_search_text():
    """Chats stored before the search column existed come out of the migration with it empty: fill it, so they are
    found by the search and sort by name without waiting for the next chat sync."""
    with Session(db_engine) as s:
        for chat in s.exec(select(TgChat).where(or_(TgChat.search_text == "", TgChat.search_text.is_(None)))):
            chat.search_text = _search_text(chat)
            s.add(chat)
        s.commit()


def purge_unlinked_accounts(keep: frozenset = frozenset(), older_than: float = 0) -> int:
    """Delete accounts whose login was never completed (the dialog was abandoned, the server stopped in between):
    no session, no chats, no runs, offline. `keep` are logins still waiting for their code, `older_than` spares rows
    created less than that many seconds ago (a login being started right now)."""
    cutoff = utcnow() - timedelta(seconds=older_than)
    with Session(db_engine) as s:
        used = set(s.exec(select(TgChat.account_id)).all()) | set(s.exec(select(TgRun.account_id)).all())
        stale = [a for a in s.exec(select(TgAccount).where(TgAccount.session_string == "", TgAccount.status == "offline"))
                 if a.id not in used | keep and _utc(a.created_at) < cutoff]
        for a in stale:
            s.delete(a)
        s.commit()
    return len(stale)


class TelegramEngine:
    def __init__(self):
        self.factory = _factory()
        self.clients: dict[int, object] = {}      # account id -> connected client
        self.pending: dict[int, Pending] = {}     # account id -> login waiting for the code
        self._locks: dict[int, asyncio.Lock] = {}
        self._tasks: set[asyncio.Task] = set()
        self.syncing: dict[int, dict] = {}        # account id -> progress of its running chat sync
        self.sync_tasks: dict[int, asyncio.Task] = {}
        self.watchers: dict[int, asyncio.Task] = {}      # account id -> task watching its connection
        self.recoveries: dict[int, asyncio.Task] = {}    # account id -> reconnect loop of a dropped account
        self.runs = RunEngine(self)
        self.hub = None

    # --- lifecycle (called by the module hooks) ------------------------------------------

    async def startup(self, ctx):
        self.hub = ctx.hub
        purge_unlinked_accounts()       # logins the last server never finished
        backfill_search_text()
        self.runs.recover()
        with Session(db_engine) as s:
            accounts = s.exec(select(TgAccount)).all()
            for a in accounts:    # nothing is connected yet, whatever the last run left behind
                if a.status in ("online", "connecting"):
                    a.status, a.status_msg = "offline", ""
                    s.add(a)
            s.commit()
            todo = [a.id for a in accounts if a.session_string and a.auto_connect]
        for acc_id in todo:       # in the background: an unreachable account must not delay the panel
            self._start_recovery(acc_id, wait_first=False)
        self._spawn(self._janitor())

    async def shutdown(self, ctx):
        """Stop every task (an active run stays "running" in the database, recover() pauses it at the next start), then
        close every connection. The tasks are awaited: a cancelled task nobody awaits is reported as destroyed while pending."""
        tasks = list(self._tasks)
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for acc_id in list(self.pending):
            await self.forget_pending(acc_id)
        for client in list(self.clients.values()):
            await _quiet_disconnect(client)
        self.clients.clear()

    def _spawn(self, coro):
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    # --- watchdog ---------------------------------------------------------------------------

    def _find(self, acc_id: int) -> Optional[TgAccount]:
        with Session(db_engine) as s:
            return s.get(TgAccount, acc_id)

    def _start_watch(self, acc_id: int, client):
        self._stop_watch(acc_id)
        self.watchers[acc_id] = self._spawn(self._watch(acc_id, client))

    def _stop_watch(self, acc_id: int):
        task = self.watchers.pop(acc_id, None)
        if task:
            task.cancel()

    def _start_recovery(self, acc_id: int, wait_first: bool):
        task = self.recoveries.get(acc_id)
        if not task or task.done():
            self.recoveries[acc_id] = self._spawn(self._recover(acc_id, wait_first))

    def _stop_recovery(self, acc_id: int):
        task = self.recoveries.pop(acc_id, None)
        if task:
            task.cancel()

    async def _watch(self, acc_id: int, client):
        """While this client lives: a lost connection (Telethon gave up reconnecting) is handled at once, and every
        AUTH_PROBE seconds Telegram is asked whether it still accepts the session. An error in here is logged, the watch goes on."""
        probe_at = time.monotonic() + AUTH_PROBE
        while self.clients.get(acc_id) is client:
            await asyncio.sleep(WATCH_INTERVAL)
            if self.clients.get(acc_id) is not client:
                return
            try:
                if not client.is_connected():
                    return await self._dropped(acc_id, client)
                if time.monotonic() >= probe_at:
                    probe_at = time.monotonic() + AUTH_PROBE
                    await self._probe(acc_id, client)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 — a failing check must not end the watch
                print(f"[telegram] watching account {acc_id}: {type(e).__name__}: {e}")

    async def _probe(self, acc_id: int, client):
        try:
            me = await asyncio.wait_for(client.get_me(), CONNECT_TIMEOUT)
        except NETWORK_ERRORS:
            return          # a dead connection is noticed by the next look at is_connected()
        except SESSION_ENDED_ERRORS as e:
            return await self.session_lost(acc_id, friendly(e).args[0])
        if me is None:      # Telethon's answer to "unauthorized"
            await self.session_lost(acc_id, SESSION_ENDED)

    async def _dropped(self, acc_id: int, client):
        """The connection is gone: the account is "connecting" again, its runs pause and the reconnect loop starts."""
        if self.clients.get(acc_id) is client:
            del self.clients[acc_id]
        self._stop_sync(acc_id)
        await _quiet_disconnect(client)
        if not self._find(acc_id):
            return
        self._update(acc_id, status="connecting", status_msg=REASON_DROPPED)
        self.runs.account_lost(acc_id, REASON_DROPPED)
        self._start_recovery(acc_id, wait_first=True)

    async def session_lost(self, acc_id: int, message: str):
        """Telegram ended the session (revoked, account deactivated or banned): drop the login, show the message, pause
        the account's runs. The operator has to log in again."""
        self._stop_sync(acc_id)
        client = self.clients.pop(acc_id, None)
        if client:
            await _quiet_disconnect(client)
        self._update(acc_id, status="error", status_msg=message, session_string="")
        self.runs.account_lost(acc_id, message)

    async def _recover(self, acc_id: int, wait_first: bool):
        """Connect an account, and while Telegram cannot be reached try again with doubling waits (RECONNECT_BASE up to
        RECONNECT_MAX). Ends when it is online, switched off by the operator, deleted, or its session has ended."""
        delay = RECONNECT_BASE if wait_first else 0
        while True:
            if delay:
                await asyncio.sleep(delay)
            acc = self._find(acc_id)
            if not acc or not acc.auto_connect or not acc.session_string:
                return
            try:
                return await self.connect(acc_id, retrying=True)
            except TgError as e:
                print(f"[telegram] account {acc_id} not reconnected: {e}")
            delay = min(RECONNECT_MAX, delay * 2 or RECONNECT_BASE)

    async def _janitor(self):
        """Logins nobody completed: close the half-open connection and remove the account row that only exists for it."""
        while True:
            await asyncio.sleep(max(WATCH_INTERVAL, 1.0))
            try:
                for acc_id in [k for k, p in self.pending.items() if p.expires < time.time()]:
                    await self.forget_pending(acc_id)
                purge_unlinked_accounts(keep=frozenset(self.pending), older_than=LOGIN_WINDOW)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 — housekeeping must never end
                print(f"[telegram] housekeeping failed: {type(e).__name__}: {e}")

    # --- helpers ------------------------------------------------------------------------

    def _lock(self, acc_id: int) -> asyncio.Lock:
        return self._locks.setdefault(acc_id, asyncio.Lock())

    def _account(self, acc_id: int) -> TgAccount:
        with Session(db_engine) as s:
            acc = s.get(TgAccount, acc_id)
        if not acc:
            raise TgError("Account not found", 404)
        return acc

    def _update(self, acc_id: int, **fields):
        """Write fields to the account row and tell the panel (status changes are pushed live)."""
        with Session(db_engine) as s:
            acc = s.get(TgAccount, acc_id)
            if not acc:
                return
            for k, v in fields.items():
                setattr(acc, k, v)
            s.add(acc)
            s.commit()
            event = {"type": "account", "account_id": acc_id, "status": acc.status, "status_msg": acc.status_msg}
        if self.hub:
            self.hub.publish(EVENTS, event)

    async def forget_pending(self, acc_id: int):
        p = self.pending.pop(acc_id, None)
        if p:
            await _quiet_disconnect(p.client)

    # --- login ----------------------------------------------------------------------------

    async def start_login(self, acc_id: int):
        """Send the login code to the account's phone (Telegram delivers it to the Telegram app first)."""
        for other in [k for k, p in self.pending.items() if p.expires < time.time()]:
            await self.forget_pending(other)   # abandoned dialogs
        await self.forget_pending(acc_id)
        await self.disconnect(acc_id, manual=False)   # logging in again replaces a live session
        acc = self._account(acc_id)
        client = self.factory("", acc.api_id, acc.api_hash)
        try:
            await asyncio.wait_for(client.connect(), CONNECT_TIMEOUT)
            sent = await client.send_code_request(acc.phone)
        except asyncio.CancelledError:
            await _quiet_disconnect(client)
            raise
        except Exception as e:  # noqa: BLE001
            await _quiet_disconnect(client)
            raise friendly(e)
        self.pending[acc_id] = Pending(client, acc.phone, sent.phone_code_hash, time.time() + LOGIN_WINDOW)

    async def submit_code(self, acc_id: int, code: str) -> str:
        """Returns "done" or "password" (the account has two-step verification)."""
        p = self._pending(acc_id)
        code = "".join(ch for ch in code if ch.isdigit())
        try:
            await p.client.sign_in(p.phone, code, phone_code_hash=p.code_hash)
        except errors.SessionPasswordNeededError:
            p.needs_password = True
            return "password"
        except Exception as e:  # noqa: BLE001
            err = friendly(e)
            if isinstance(e, errors.PhoneCodeExpiredError):
                await self.forget_pending(acc_id)
            raise err
        return await self._complete(acc_id, p)

    async def submit_password(self, acc_id: int, password: str) -> str:
        p = self._pending(acc_id)
        if not p.needs_password:
            raise TgError("Enter the code first")
        try:
            await p.client.sign_in(password=password)
        except Exception as e:  # noqa: BLE001
            raise friendly(e)
        return await self._complete(acc_id, p)

    def _pending(self, acc_id: int) -> Pending:
        p = self.pending.get(acc_id)
        if not p or p.expires < time.time():
            self.pending.pop(acc_id, None)
            raise TgError("The login has expired, start again", 410)
        return p

    async def _complete(self, acc_id: int, p: Pending) -> str:
        try:
            me = await p.client.get_me()
            session = p.client.session.save()
        except Exception as e:  # noqa: BLE001
            await self.forget_pending(acc_id)
            raise friendly(e)
        self.pending.pop(acc_id, None)
        self.clients[acc_id] = p.client
        acc = self._account(acc_id)
        name = " ".join(x for x in (getattr(me, "first_name", ""), getattr(me, "last_name", "")) if x)
        self._update(acc_id, session_string=session, tg_user_id=str(me.id), tg_username=me.username or "",
                     label=acc.label or name or acc.phone, status="online", status_msg="", auto_connect=True,
                     last_connected_at=utcnow())
        self._attach(acc_id, p.client)
        return "done"

    # --- connection ---------------------------------------------------------------------

    async def connect(self, acc_id: int, retrying: bool = False):
        """retrying: called by the reconnect loop, so a network failure leaves the account "connecting" (it is not given
        up) instead of "error"."""
        async with self._lock(acc_id):
            acc = self._account(acc_id)
            client = self.clients.get(acc_id)
            if client and client.is_connected():
                self._update(acc_id, status="online", status_msg="", auto_connect=True)
                return
            if client:         # a dead client the watcher has not collected yet
                del self.clients[acc_id]
                await _quiet_disconnect(client)
            if not acc.session_string:
                raise TgError("This account is not logged in yet, log in first")
            if not retrying:
                self._update(acc_id, status="connecting", status_msg="")
            client = self.factory(acc.session_string, acc.api_id, acc.api_hash)
            try:
                await asyncio.wait_for(client.connect(), CONNECT_TIMEOUT)
                if not await client.is_user_authorized():
                    raise errors.SessionRevokedError(None)
            except asyncio.CancelledError:
                await _quiet_disconnect(client)     # the reconnect loop was stopped half-way: leave no socket behind
                raise
            except Exception as e:  # noqa: BLE001
                await _quiet_disconnect(client)
                err = friendly(e)
                if isinstance(e, SESSION_ENDED_ERRORS):     # a dead session cannot be reused
                    self._update(acc_id, status="error", status_msg=err.args[0], session_string="")
                    self.runs.account_lost(acc_id, err.args[0])
                else:
                    self._update(acc_id, status="connecting" if retrying else "error", status_msg=err.args[0])
                raise err
            self.clients[acc_id] = client
            self._update(acc_id, status="online", status_msg="", auto_connect=True, last_connected_at=utcnow())
            self._attach(acc_id, client)

    async def disconnect(self, acc_id: int, manual: bool = True):
        """manual=True: the operator wants it off, so it stays off after a server restart."""
        self._stop_recovery(acc_id)       # before the lock: a reconnect in progress holds it
        async with self._lock(acc_id):
            self._stop_watch(acc_id)
            self._stop_sync(acc_id)
            client = self.clients.pop(acc_id, None)
            if client:
                await _quiet_disconnect(client)
            self._update(acc_id, status="offline", status_msg="", **({"auto_connect": False} if manual else {}))

    async def forget(self, acc_id: int):
        """Drop every live object of an account that is about to be deleted."""
        await self.forget_pending(acc_id)
        self._stop_recovery(acc_id)
        self._stop_watch(acc_id)
        self._stop_sync(acc_id)
        client = self.clients.pop(acc_id, None)
        if client:
            await _quiet_disconnect(client)

    # --- chat capture -----------------------------------------------------------------------

    def _publish(self, event: dict):
        if self.hub:
            self.hub.publish(EVENTS, event)

    def _attach(self, acc_id: int, client):
        """A freshly connected client: capture incoming messages from now on, import the existing chats, watch the
        connection and let the runs that were waiting for this account go on."""
        client.add_event_handler(partial(self._on_message, acc_id, self._account(acc_id).tg_user_id),
                                 events.NewMessage(incoming=True))
        self.start_sync(acc_id)
        self._start_watch(acc_id, client)
        self.runs.account_back(acc_id)

    async def _on_message(self, acc_id: int, own_id: Optional[str], event):
        """A message arrived in a private chat: create the chat or refresh its last contact."""
        try:
            if not event.is_private or event.out:
                return
            user = await event.get_sender()
            if not _is_contact(user, own_id):
                return
            with Session(db_engine) as s:
                (chat, created), = upsert_chats(s, acc_id, [_chat_row(user, event.message, live=True)])
                s.commit()
                chat_id = chat.id
            self._publish({"type": "chat", "account_id": acc_id, "chat_id": chat_id, "new": created})
        except Exception as e:  # noqa: BLE001 — one bad message must not break the handler for the next ones
            print(f"[telegram] incoming message of account {acc_id} not stored: {type(e).__name__}: {e}")

    def start_sync(self, acc_id: int) -> bool:
        """Import the account's private dialogs in the background. False: a sync is already running."""
        client = self.clients.get(acc_id)
        if not client or not client.is_connected():
            raise TgError("This account is not online", 409)
        if acc_id in self.syncing:
            return False
        self.syncing[acc_id] = {"scanned": 0, "imported": 0}   # set right away: it is the guard against a second sync
        self.sync_tasks[acc_id] = self._spawn(self._run_sync(acc_id, client))
        return True

    def _stop_sync(self, acc_id: int):
        task = self.sync_tasks.pop(acc_id, None)
        if task:
            task.cancel()
        self.syncing.pop(acc_id, None)

    async def _run_sync(self, acc_id: int, client):
        prog = self.syncing[acc_id]
        own_id = self._account(acc_id).tg_user_id
        saved: set[str] = set()      # telegram ids already written (a FloodWait restart skips them)
        batch: list[dict] = []

        def release():     # idempotent; a newer sync of the same account must stay registered
            if self.syncing.get(acc_id) is prog:
                del self.syncing[acc_id]
                self.sync_tasks.pop(acc_id, None)

        def progress(state: str, **extra):
            self._publish({"type": "sync", "account_id": acc_id, "state": state, **prog, **extra})

        async def flush():
            if not batch:
                return
            with Session(db_engine) as s:
                upsert_chats(s, acc_id, batch)
                s.commit()
            saved.update(r["telegram_id"] for r in batch)
            batch.clear()
            prog["imported"] = len(saved)
            progress("running")
            await asyncio.sleep(0)   # let requests and incoming messages through between batches

        try:
            progress("running")
            for attempt in range(SYNC_FLOOD_RETRIES + 1):
                prog["scanned"] = 0
                try:
                    async for dialog in client.iter_dialogs():
                        prog["scanned"] += 1
                        if dialog.is_user and _is_contact(dialog.entity, own_id):
                            row = _chat_row(dialog.entity, dialog.message)
                            if row["telegram_id"] not in saved:
                                batch.append(row)
                        if len(batch) >= SYNC_BATCH:
                            await flush()
                    break
                except errors.FloodWaitError as e:
                    await flush()
                    if attempt == SYNC_FLOOD_RETRIES:
                        raise
                    progress("waiting", wait=e.seconds)
                    await asyncio.sleep(e.seconds + 1)
            await flush()
            release()
            progress("done")
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            release()
            progress("error", message=friendly(e).args[0])
        finally:
            release()


# --- run engine ---------------------------------------------------------------------------
# A run sends a frozen workflow to its chats, one chat after the other, one asyncio task per run.
# Pause is a gate (asyncio.Event) the task looks at between actions and while it waits, so the countdown
# freezes and Resume continues at the same chat and step with the remaining time. The task persists its
# position after every step: tg_run.current_run_chat_id / current_step_index name the step that is sent next
# (or is being sent), and next_action_at + wait_kind say the task is waiting before it ("pause" = the pause after
# the previous step; "flood" / "retry" = a send that failed and is tried again). That is all a restart needs.

# Telethon error -> reason stored on the chat (the first match wins)
_SEND_ERRORS = [
    (errors.UserPrivacyRestrictedError, "The user's privacy settings do not allow this message"),
    (errors.PeerFloodError, PEER_FLOOD),
    (errors.InputUserDeactivatedError, "The user's account was deleted"),
    (errors.UserIsBlockedError, "The user has blocked this account"),
    (errors.YouBlockedUserError, "This account has blocked the user"),
    (errors.UserNotMutualContactError, "The user only accepts messages from contacts"),
    (errors.PeerIdInvalidError, "Invalid recipient (the chat could not be found)"),
    (errors.UserIdInvalidError, "Invalid recipient (the chat could not be found)"),
    (errors.ChatWriteForbiddenError, "Writing to this chat is not allowed"),
    (errors.VoiceMessagesForbiddenError, "The user does not accept voice messages"),
    (errors.UserDeactivatedBanError, "This Telegram account was banned"),
    (errors.UserDeactivatedError, "This Telegram account was deactivated"),
    (errors.AuthKeyUnregisteredError, SESSION_ENDED),
    (errors.SessionRevokedError, SESSION_ENDED),
    (errors.MediaEmptyError, "Telegram rejected the media file"),
    (errors.ImageProcessFailedError, "Telegram rejected the media file"),
    (errors.PhotoInvalidDimensionsError, "Telegram rejected the media file"),
    (errors.FilePartsInvalidError, "Telegram rejected the media file"),
    (FileNotFoundError, "The media file is missing on the server"),
    (NETWORK_ERRORS, "Could not reach Telegram (network problem)"),
]


def send_error(e: Exception) -> str:
    """A short readable reason for a failed send."""
    if isinstance(e, TgError):
        return str(e)
    for cls, reason in _SEND_ERRORS:
        if isinstance(e, cls):
            return reason
    return f"Telegram error: {type(e).__name__}"


def run_state(s: Session, run: TgRun) -> dict:
    """Everything the panel shows about a run; the REST routes and the WebSocket events share this shape."""
    steps = (run.workflow_snapshot or {}).get("steps", [])
    rc = s.get(TgRunChat, run.current_run_chat_id) if run.status in ACTIVE_RUN and run.current_run_chat_id else None
    chat = s.get(TgChat, rc.chat_id) if rc else None
    due, left = _utc(run.next_action_at), None
    idx, step, next_type = run.current_step_index, None, None
    if due and run.wait_kind == "pause" and rc and rc.status == "running":
        idx -= 1       # the stored index is already the step after this pause; the one just sent is "current"
    if rc and 0 <= idx < len(steps):
        step = {"index": idx, "type": steps[idx]["type"]}
        chats_after = run.total_chats - run.processed - (1 if rc.status == "running" else 0)
        next_type = steps[idx + 1]["type"] if idx + 1 < len(steps) else (steps[0]["type"] if chats_after > 0 else None)
    if due and run.status == "running":
        left = max(0.0, (due - utcnow()).total_seconds())
    elif due and run.status == "paused":    # frozen: what was left when the run was paused
        left = max(0.0, (due - _utc(run.paused_at)).total_seconds())
    started = _utc(run.started_at)
    return {
        "id": run.id, "account_id": run.account_id, "workflow_id": run.workflow_id, "workflow_name": run.workflow_name,
        "status": run.status, "status_msg": run.status_msg, "on_error": run.on_error, "retries": run.retries,
        "auto_resume": run.auto_resume, "mark_read": run.mark_read, "peer_floods": run.peer_floods,
        "chat": {"id": chat.id, "name": chat.display_name, "username": chat.username} if chat else None,
        "step": step, "steps_total": len(steps), "next_step_type": next_type,
        "wait_kind": run.wait_kind if due else "",
        "next_action_at": iso(due) if run.status == "running" else None,
        "seconds_remaining": round(left, 1) if left is not None else None,
        "total": run.total_chats, "processed": run.processed, "success": run.success, "errors": run.errors,
        "skipped": run.total_chats - run.processed if run.status in ("stopped", "error") else 0,
        "percent": int(run.processed * 100 / run.total_chats) if run.total_chats else 0,
        "created_at": iso(run.created_at), "started_at": iso(run.started_at), "paused_at": iso(run.paused_at),
        "finished_at": iso(run.finished_at),
        "duration_seconds": int(((_utc(run.finished_at) or utcnow()) - started).total_seconds()) if started else None,
    }


class _Stopped(Exception):
    """Raised inside a run task when the operator stopped the run."""


@dataclass
class RunHandle:
    """The live side of a run that is running or paused (a run restored after a restart has none until it is resumed)."""
    run_id: int
    account_id: int
    steps: list
    on_error: str
    retries: int
    gate: asyncio.Event = field(default_factory=asyncio.Event)    # set = may work, clear = paused
    stopping: bool = False
    deadline: Optional[float] = None       # time.monotonic() at which the current wait ends
    frozen_left: Optional[float] = None    # seconds the current wait still needs, kept while paused
    task: Optional[asyncio.Task] = None


class RunEngine:
    def __init__(self, tg: "TelegramEngine"):
        self.tg = tg
        self.handles: dict[int, RunHandle] = {}

    # --- control (called by the routes) --------------------------------------------------

    def recover(self):
        """Server start: runs the last server left running or queued become paused, position intact."""
        now = utcnow()
        with Session(db_engine) as s:
            for run in s.exec(select(TgRun).where(TgRun.status.in_(("queued", "running")))).all():
                run.status, run.status_msg, run.paused_at = "paused", REASON_RESTART, now
                due = _utc(run.next_action_at)
                if due and due < now:      # the downtime used up the pause: it is over as soon as the run resumes
                    run.next_action_at = now
                s.add(run)
                self._mark_chat(s, run.id, "paused")
            s.commit()

    def start(self, account_id: int, workflow_id: Optional[int], name: str, snapshot: dict, chat_ids: list[int],
              on_error: str, retries: int, auto_resume: bool = False, mark_read: bool = True) -> int:
        """Create a run over chat_ids (in this order) and start working. There is no await in here: the check for
        another active run and the insert cannot be interleaved with a second start."""
        if not self._online(account_id):
            raise TgError("This account is not online", 409)
        with Session(db_engine) as s:
            if s.exec(select(TgRun.id).where(TgRun.account_id == account_id, TgRun.status.in_(ACTIVE_RUN))).first():
                raise TgError("This account already has an active run", 409)
            run = TgRun(account_id=account_id, workflow_id=workflow_id, workflow_name=name, workflow_snapshot=snapshot,
                        status="running", total_chats=len(chat_ids), on_error=on_error, retries=retries,
                        auto_resume=auto_resume, mark_read=mark_read, started_at=utcnow())
            s.add(run)
            s.flush()
            s.add_all(TgRunChat(run_id=run.id, chat_id=cid, position=n) for n, cid in enumerate(chat_ids))
            s.commit()
            run_id = run.id
        self._spawn(run_id, account_id, snapshot["steps"], on_error, retries)
        self._emit(run_id)
        return run_id

    def _spawn(self, run_id, account_id, steps, on_error, retries):
        h = RunHandle(run_id, account_id, steps, on_error, retries)
        h.gate.set()
        self.handles[run_id] = h
        h.task = self.tg._spawn(self._drive(h))

    def _get(self, run_id: int, allowed: tuple, action: str) -> TgRun:
        with Session(db_engine) as s:
            run = s.get(TgRun, run_id)
        if not run:
            raise TgError("Run not found", 404)
        if run.status not in allowed:
            raise TgError(f"The run cannot be {action}, it is {run.status}", 409)
        return run

    def pause(self, run_id: int):
        self._get(run_id, ("queued", "running"), "paused")
        self._pause(self.handles[run_id], "")

    def resume(self, run_id: int):
        run = self._get(run_id, ("paused",), "resumed")
        if not self._online(run.account_id):
            raise TgError("This account is not online, connect it first", 409)
        h, now = self.handles.get(run_id), utcnow()
        fields = {"status": "running", "status_msg": "", "paused_at": None}
        if h:
            if h.frozen_left is not None:
                h.deadline = time.monotonic() + h.frozen_left
                fields["next_action_at"] = now + timedelta(seconds=h.frozen_left)
                h.frozen_left = None
        elif run.next_action_at:      # restored after a restart: what was left when it was paused
            fields["next_action_at"] = now + max(_utc(run.next_action_at) - _utc(run.paused_at), timedelta(0))
        self._save(run_id, **fields)
        with Session(db_engine) as s:
            self._mark_chat(s, run_id, "in_progress")
            s.commit()
        if h:
            h.gate.set()
        else:
            self._spawn(run_id, run.account_id, run.workflow_snapshot["steps"], run.on_error, run.retries)
        self._emit(run_id)

    def account_lost(self, account_id: int, reason: str):
        """The account's connection or login is gone: its running runs pause with the reason (the countdown freezes), and
        runs that were already paused by the system, not by the operator, show the new reason."""
        for h in [h for h in self.handles.values() if h.account_id == account_id and h.gate.is_set()]:
            self._pause(h, reason)
        with Session(db_engine) as s:
            changed = [r for r in s.exec(select(TgRun).where(TgRun.account_id == account_id, TgRun.status == "paused",
                                                              TgRun.status_msg != "")) if r.status_msg != reason]
            for r in changed:
                r.status_msg = reason
                s.add(r)
            s.commit()
            ids = [r.id for r in changed]
        for run_id in ids:
            self._emit(run_id)

    def account_back(self, account_id: int):
        """The account is online again: runs that were paused by the system and opted into auto_resume go on."""
        with Session(db_engine) as s:
            ids = s.exec(select(TgRun.id).where(TgRun.account_id == account_id, TgRun.status == "paused",
                                                TgRun.status_msg != "", TgRun.auto_resume == True)).all()  # noqa: E712
        for run_id in ids:
            try:
                self.resume(run_id)
            except TgError as e:
                print(f"[telegram] run {run_id} not resumed: {e}")

    async def stop(self, run_id: int):
        self._get(run_id, ACTIVE_RUN, "stopped")
        h = self.handles.get(run_id)
        if h:
            h.stopping = True
            h.gate.set()
            await h.task       # the step being sent is finished first
        else:
            self._finish(run_id, "stopped")

    # --- the run task --------------------------------------------------------------------

    async def _drive(self, h: RunHandle):
        try:
            await self._work(h)
            self._finish(h.run_id, "done")
        except _Stopped:
            self._finish(h.run_id, "stopped")
        except asyncio.CancelledError:
            raise              # server shutdown: the run stays "running" and recover() pauses it at the next start
        except Exception as e:  # noqa: BLE001 — a bug must end this run, not leave it hanging
            print(f"[telegram] run {h.run_id} failed: {type(e).__name__}: {e}")
            self._finish(h.run_id, "error", f"Unexpected error: {type(e).__name__}")
        finally:
            self.handles.pop(h.run_id, None)

    async def _work(self, h: RunHandle):
        with Session(db_engine) as s:
            run = s.get(TgRun, h.run_id)
            rc = s.get(TgRunChat, run.current_run_chat_id) if run.current_run_chat_id else None
            rc_id = rc.id if rc and rc.status == "running" else None      # the chat a restored run was in
            idx, due, kind = run.current_step_index, _utc(run.next_action_at), run.wait_kind
        if due:      # restored in the middle of a wait: finish it first
            await self._wait(h, max(0.0, (due - utcnow()).total_seconds()), kind)
        while True:
            if rc_id is None:
                rc_id, idx = self._next_chat(h.run_id), 0
                if rc_id is None:
                    return
                await self._checkpoint(h)      # a paused run holds the next chat untouched, it is not "in progress" yet
                if not self._begin_chat(h.run_id, rc_id):
                    rc_id = None
                    continue
            await self._do_chat(h, rc_id, idx)
            rc_id = None

    async def _do_chat(self, h: RunHandle, rc_id: int, first: int):
        with Session(db_engine) as s:
            chat = s.get(TgChat, s.get(TgRunChat, rc_id).chat_id)
            tid, access_hash = chat.telegram_id, chat.access_hash
            mark_read = s.get(TgRun, h.run_id).mark_read
        try:       # Telethon's entity cache is gone after a restart: the stored access_hash is the only address
            peer = InputPeerUser(int(tid), int(access_hash))
        except (TypeError, ValueError):
            return self._fail_chat(h.run_id, rc_id, "The chat has no access key, sync the chats again")
        if first == 0 and mark_read:      # a chat that is already under way was opened before
            await self._open_chat(h, peer)
        for i in range(first, len(h.steps)):
            reason = await self._send_step(h, rc_id, peer, i)
            if reason:
                return self._fail_chat(h.run_id, rc_id, reason)
            last = i == len(h.steps) - 1
            self._sent(h.run_id, rc_id, next_step=None if last else i + 1, kind=h.steps[i]["type"])
            pause = h.steps[i]["pause_after"]
            if pause and (not last or self._next_chat(h.run_id)):    # after the very last step nobody is left to wait for
                await self._wait(h, pause, "pause")

    async def _open_chat(self, h: RunHandle, peer):
        """Open the chat like a person would: the contact's messages get the "read" ticks before our first message goes
        out. Cosmetic, so a failure here (or a slow answer) must never fail the chat."""
        client = self.tg.clients.get(h.account_id)
        if client is None:
            return
        try:
            await asyncio.wait_for(client.send_read_acknowledge(peer), 20)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            print(f"[telegram] run {h.run_id}: could not mark the chat as read ({type(e).__name__})")

    async def _send_step(self, h: RunHandle, rc_id: int, peer, i: int) -> Optional[str]:
        """Send step i with the run's error policy; returns None, or the reason it finally failed."""
        failures = floods = 0
        while True:
            await self._checkpoint(h)
            self._save(h.run_id, current_run_chat_id=rc_id, current_step_index=i, next_action_at=None, wait_kind="")
            self._emit(h.run_id)
            try:
                await self._send(h, peer, h.steps[i])
                return None
            except errors.FloodWaitError as e:
                floods += 1
                if floods > FLOOD_RETRIES:
                    return f"Telegram keeps asking to wait (FloodWait {e.seconds} s)"
                self.tg._publish({"type": "flood", "run_id": h.run_id, "account_id": h.account_id, "seconds": e.seconds})
                await self._wait(h, e.seconds + 1, "flood")
            except Exception as e:  # noqa: BLE001 — every Telegram failure becomes the chat's error reason
                if isinstance(e, SESSION_ENDED_ERRORS):      # not this chat's fault: log the account out, the run waits for a new login
                    await self.tg.session_lost(h.account_id, send_error(e))
                    continue
                if isinstance(e, NETWORK_ERRORS) and not self._online(h.account_id):
                    self._pause(h, REASON_DROPPED)           # the connection dropped under this send: try the step again later
                    continue
                failures += 1
                if h.on_error != "retry" or failures > h.retries:
                    return send_error(e)
                await self._wait(h, RETRY_WAIT, "retry")

    async def _send(self, h: RunHandle, peer, step: dict):
        client = self.tg.clients[h.account_id]
        if step["type"] == "text":
            await client.send_message(peer, step["content"])
            return
        if step["type"] == "block":
            # A plain block, as the client wants it: NO spam report (messages.ReportSpam) and the chat is NOT deleted
            # (messages.DeleteHistory); those are the two boxes of the Telegram app's block dialog, left unticked.
            # The contact stays in the chat list but can no longer write to this account.
            await client(BlockRequest(id=peer))
            return
        from .api import _voice_seconds, media_dir     # api.py imports this module, so the import cannot sit at the top
        path = media_dir() / step["file"]
        if not path.is_file():
            raise FileNotFoundError(path.name)
        once = _ttl(step)
        if step["type"] != "voice":
            await client.send_file(peer, path, **once)
            return
        # Telethon reads a voice file's length with the optional hachoir package; without it the message would
        # arrive as 0:00. The length is known here already (OGG header), so say it explicitly.
        seconds = int(round(_voice_seconds(path) or 0))
        await client.send_file(peer, path, voice_note=True,
                               attributes=[DocumentAttributeAudio(duration=seconds, voice=True)], **once)

    # --- waiting -------------------------------------------------------------------------

    def _online(self, account_id: int) -> bool:
        client = self.tg.clients.get(account_id)
        return bool(client and client.is_connected())

    async def _checkpoint(self, h: RunHandle):
        """Before every send: wait while paused, obey Stop, and pause (not fail) when the account went offline."""
        while True:
            await h.gate.wait()
            if h.stopping:
                raise _Stopped
            if self._online(h.account_id):
                return
            self._pause(h, REASON_OFFLINE)

    async def _wait(self, h: RunHandle, seconds: float, kind: str):
        """A countdown the operator can pause: next_action_at shows it, Pause freezes it, Resume continues it."""
        now = utcnow()
        h.deadline = time.monotonic() + seconds
        fields = {"next_action_at": now + timedelta(seconds=seconds), "wait_kind": kind}
        if not h.gate.is_set():      # paused while the step was being sent: the countdown starts frozen
            h.frozen_left, fields["paused_at"] = seconds, now
        self._save(h.run_id, **fields)
        self._emit(h.run_id)
        while True:
            await h.gate.wait()
            if h.stopping:
                raise _Stopped
            left = h.deadline - time.monotonic()
            if left <= 0:
                break
            await asyncio.sleep(min(SLICE, left))
        h.deadline = None
        self._save(h.run_id, next_action_at=None, wait_kind="")
        self._emit(h.run_id)

    def _pause(self, h: RunHandle, reason: str):
        if not h.gate.is_set():       # already paused: the first reason stays
            return
        h.gate.clear()
        if h.deadline is not None:
            h.frozen_left = max(0.0, h.deadline - time.monotonic())
        self._save(h.run_id, status="paused", status_msg=reason, paused_at=utcnow())
        with Session(db_engine) as s:
            self._mark_chat(s, h.run_id, "paused")
            s.commit()
        self._emit(h.run_id)

    # --- bookkeeping ---------------------------------------------------------------------

    def _save(self, run_id: int, **fields):
        with Session(db_engine) as s:
            run = s.get(TgRun, run_id)
            for k, v in fields.items():
                setattr(run, k, v)
            s.add(run)
            s.commit()

    def _emit(self, run_id: int):
        with Session(db_engine) as s:
            state = run_state(s, s.get(TgRun, run_id))
        self.tg._publish({"type": "run", **state})

    def _mark_chat(self, s: Session, run_id: int, status: str):
        """Set the status of the chat this run is working on right now (not committed)."""
        rc = s.exec(select(TgRunChat).where(TgRunChat.run_id == run_id, TgRunChat.status == "running")).first()
        chat = s.get(TgChat, rc.chat_id) if rc else None
        if chat:
            chat.chat_status = status
            s.add(chat)

    def _next_chat(self, run_id: int) -> Optional[int]:
        with Session(db_engine) as s:
            return s.exec(select(TgRunChat.id).where(TgRunChat.run_id == run_id, TgRunChat.status == "pending")
                          .order_by(TgRunChat.position)).first()

    def _begin_chat(self, run_id: int, rc_id: int) -> bool:
        """Start working on a chat. False: its row is gone from the database, so only that chat fails."""
        now = utcnow()
        with Session(db_engine) as s:
            rc = s.get(TgRunChat, rc_id)
            chat = s.get(TgChat, rc.chat_id)
            if chat is None:
                rc.status, rc.error_reason, rc.started_at, rc.processed_at = "error", "The chat no longer exists", now, now
                run = s.get(TgRun, run_id)
                run.processed, run.errors = run.processed + 1, run.errors + 1
                s.add_all([rc, run])
                s.commit()
            else:
                rc.status, rc.started_at = "running", now
                chat.chat_status, chat.error_reason = "in_progress", ""
                s.add_all([rc, chat])
                s.commit()
        if chat is None:
            self._emit(run_id)
            return False
        self._save(run_id, current_run_chat_id=rc_id, current_step_index=0)
        return True

    def _sent(self, run_id: int, rc_id: int, next_step: Optional[int], kind: str):
        """One step was carried out: count it and move the position on (next_step None = it was the last step, so
        the chat is closed), all in one commit. A message counts as sent; blocking is not a message."""
        now = utcnow()
        with Session(db_engine) as s:
            rc = s.get(TgRunChat, rc_id)
            chat = s.get(TgChat, rc.chat_id)
            rc.steps_done += 1
            if kind == "block":
                chat.blocked = True
            else:
                chat.messages_sent += 1
            run = s.get(TgRun, run_id)
            if next_step is None:
                rc.status, rc.processed_at = "done", now
                chat.chat_status, chat.error_reason, chat.last_processed_at = "done", "", now
                run.processed, run.success = run.processed + 1, run.success + 1
            else:
                run.current_step_index = next_step
            s.add(run)
            s.add_all([rc, chat])
            s.commit()
        self._emit(run_id)

    def _fail_chat(self, run_id: int, rc_id: int, reason: str):
        """Mark the chat as failed; the run goes on with the next one."""
        self._close_chat(run_id, rc_id, "error", reason)
        self._emit(run_id)
        if reason == PEER_FLOOD:
            with Session(db_engine) as s:
                account_id = s.get(TgRun, run_id).account_id
            self.tg._publish({"type": "flood", "kind": "peer", "run_id": run_id, "account_id": account_id})

    def _close_chat(self, run_id: int, rc_id: int, status: str, reason: str = ""):
        """End the chat that is in progress: error (counted) or skipped (the run ended before it was finished;
        a chat that got no message goes back to not processed)."""
        now = utcnow()
        with Session(db_engine) as s:
            rc = s.get(TgRunChat, rc_id)
            chat = s.get(TgChat, rc.chat_id)
            rc.status, rc.error_reason, rc.processed_at = status, reason, now
            if status == "error":
                chat.chat_status, chat.error_reason, chat.last_processed_at = "error", reason, now
                run = s.get(TgRun, run_id)
                run.processed, run.errors = run.processed + 1, run.errors + 1
                if reason == PEER_FLOOD:
                    run.peer_floods += 1
                s.add(run)
            elif rc.steps_done:      # partly sent: neither untouched nor done
                chat.chat_status, chat.last_processed_at = "paused", now
            else:      # nothing went out: the chat is as it was before the run
                chat.chat_status = "pending"
            s.add_all([rc, chat])
            s.commit()

    def _finish(self, run_id: int, status: str, reason: str = ""):
        """End the run: the chat in progress is closed, the chats never reached are marked skipped."""
        with Session(db_engine) as s:
            current = s.exec(select(TgRunChat.id).where(TgRunChat.run_id == run_id,
                                                        TgRunChat.status == "running")).first()
        if current:
            self._close_chat(run_id, current, "error" if status == "error" else "skipped", reason)
        with Session(db_engine) as s:
            s.exec(sa_update(TgRunChat).where(TgRunChat.run_id == run_id, TgRunChat.status == "pending")
                   .values(status="skipped"))
            s.commit()
        self._save(run_id, status=status, status_msg=reason, finished_at=utcnow(), next_action_at=None, wait_kind="")
        self._emit(run_id)


tg = TelegramEngine()
