"""Telegram module backend: tables (tg_* — all modules share one database) and the /api/telegram routes.
The bot logic itself (Telethon sessions, workflow runner) lives in engine.py.
JSON columns must be re-assigned, not mutated in place (same rule as api/models.py)."""

import csv
import io
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any, Callable, Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from PIL import Image
from pydantic import AfterValidator, BaseModel
from sqlalchemy import JSON, Column, func
from sqlalchemy import delete as sa_delete
from sqlalchemy import update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, select

from api import settings as cfg
from api.models import AppSetting, get_session, iso, utcnow


class TgAccount(SQLModel, table=True):
    """A linked Telegram user account (MTProto session, not a Bot API bot)."""
    __tablename__ = "tg_account"
    id: Optional[int] = Field(default=None, primary_key=True)
    label: str = ""
    phone: str = Field(unique=True, index=True)
    api_id: int = 0
    api_hash: str = ""
    session_string: str = ""              # Telethon StringSession; empty = not logged in yet
    status: str = Field(default="offline", index=True)   # offline | connecting | online | error
    status_msg: str = ""
    auto_connect: bool = True             # reconnect at server start (False once the operator disconnected it)
    tg_user_id: Optional[str] = None      # the account's own Telegram id, filled after login
    tg_username: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    last_connected_at: Optional[datetime] = None


class TgChat(SQLModel, table=True):
    """One contact/chat of a linked account."""
    __tablename__ = "tg_chat"
    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="tg_account.id", index=True)
    telegram_id: str = Field(index=True)  # str: Telegram ids can exceed what JS numbers hold
    # A StringSession does not keep Telethon's entity cache, so after a server restart a chat can only be
    # addressed with its stored (id, access_hash). Never sent to the panel.
    access_hash: Optional[str] = ""       # nullable on purpose: older rows and raw inserts predate the column
    search_text: Optional[str] = ""       # casefolded "name username id" for the chat search (SQLite lower() is ASCII-only)
    username: str = Field(default="", index=True)
    display_name: str = ""
    first_contact_at: Optional[datetime] = None
    last_contact_at: Optional[datetime] = Field(default=None, index=True)
    last_message: str = ""
    blocked: bool = Field(default=False, sa_column_kwargs={"server_default": "0"})   # a workflow's "block user" step blocked this contact on Telegram
    chat_status: str = Field(default="pending", index=True)   # pending|in_progress|done|error|paused
    messages_sent: int = 0
    last_processed_at: Optional[datetime] = None
    error_reason: str = ""
    notes: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class TgWorkflow(SQLModel, table=True):
    """A saved message sequence. steps = [{"type": "text|image|voice", "content"/"file": ..., "pause_after": sec}]."""
    __tablename__ = "tg_workflow"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    steps: list = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class TgRun(SQLModel, table=True):
    """One execution: a workflow sent to a set of chats, one chat at a time."""
    __tablename__ = "tg_run"
    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="tg_account.id", index=True)
    workflow_id: Optional[int] = Field(default=None, foreign_key="tg_workflow.id")
    workflow_name: str = ""
    workflow_snapshot: dict = Field(default_factory=dict, sa_column=Column(JSON))  # frozen at start
    status: str = Field(default="queued", index=True)   # queued|running|paused|stopped|done|error
    total_chats: int = 0
    processed: int = 0
    success: int = 0
    errors: int = 0
    current_run_chat_id: Optional[int] = None   # TgRunChat being processed (resume point)
    current_step_index: int = 0
    next_action_at: Optional[datetime] = None   # end of the current pause
    on_error: str = "next"                      # next = go on with the next chat | retry
    # server_default: rows inserted without these columns (raw SQL, older code) stay valid
    retries: int = Field(default=3, sa_column_kwargs={"server_default": "3"})   # extra attempts per step when on_error = retry (1..5)
    wait_kind: str = Field(default="", sa_column_kwargs={"server_default": ""})  # what next_action_at waits for: pause | flood | retry
    status_msg: str = Field(default="", sa_column_kwargs={"server_default": ""})  # why a run is paused (e.g. "Account offline")
    auto_resume: bool = Field(default=False, sa_column_kwargs={"server_default": "0"})  # go on by itself when the account is back
    peer_floods: int = Field(default=0, sa_column_kwargs={"server_default": "0"})       # chats that failed with PeerFlood
    created_at: datetime = Field(default_factory=utcnow, index=True)
    started_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class TgRunChat(SQLModel, table=True):
    """A chat inside a run, with its own outcome (the audit trail: which chat, when, what happened)."""
    __tablename__ = "tg_run_chat"
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="tg_run.id", index=True)
    chat_id: int = Field(foreign_key="tg_chat.id", index=True)
    position: int = 0
    status: str = Field(default="pending", index=True)  # pending|running|done|error|skipped
    steps_done: int = 0
    error_reason: str = ""
    started_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Routes (mounted at /api/telegram behind the panel login)
# ---------------------------------------------------------------------------

from .engine import ACTIVE_RUN, TgError, run_state, tg  # noqa: E402  (engine.py needs the tables above, so it is imported after them)

router = APIRouter()


async def _call(coro):
    """Run an engine call; its operator-safe errors become HTTP errors."""
    try:
        return await coro
    except TgError as e:
        raise HTTPException(e.status, str(e))


def _get_account(s: Session, id_: int) -> TgAccount:
    acc = s.get(TgAccount, id_)
    if not acc:
        raise HTTPException(404, "Account not found")
    return acc


def _account_public(a: TgAccount, chats: int = 0) -> dict:
    d = a.model_dump(exclude={"session_string", "api_hash"})   # a session string is full access to the account
    d["has_session"] = bool(a.session_string)
    d["login_pending"] = a.id in tg.pending
    d["chats"] = chats
    d["sync"] = tg.syncing.get(a.id)        # {"scanned", "imported"} while a chat sync runs, else None
    d["created_at"], d["last_connected_at"] = iso(a.created_at), iso(a.last_connected_at)
    return d


def _saved_credentials(s: Session) -> dict:
    row = s.get(AppSetting, "telegram")
    value = (row.value if row else None) or {}
    return {"api_id": int(value.get("api_id") or 0), "api_hash": value.get("api_hash") or ""}


def _save_credentials(s: Session, api_id: int, api_hash: str):
    row = s.get(AppSetting, "telegram") or AppSetting(key="telegram", value={})
    row.value = {**(row.value or {}), "api_id": api_id, "api_hash": api_hash}
    s.add(row)
    s.commit()


def _normalize_phone(raw: str) -> str:
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not 7 <= len(digits) <= 15:
        raise HTTPException(422, "Invalid phone number")
    return "+" + digits


def _encodable(value: str) -> str:
    """A lone UTF-16 surrogate (valid in JSON, impossible in UTF-8) would fail the database write."""
    try:
        value.encode()
    except UnicodeEncodeError:
        raise ValueError("The text contains invalid characters")
    return value


Text = Annotated[str, AfterValidator(_encodable)]    # every free text a body can carry
MAX_LABEL = 60
MAX_API_HASH = 64       # the real one has 32 hex characters
MAX_API_ID = 2 ** 31 - 1


def _check_credentials(api_id: Optional[int], api_hash: str):
    if not api_id or not api_hash:
        raise HTTPException(422, "API ID and API Hash are required (my.telegram.org)")
    if not 0 < api_id <= MAX_API_ID or len(api_hash) > MAX_API_HASH:
        raise HTTPException(422, "API ID / API Hash are not valid (check my.telegram.org)")


class SettingsIn(BaseModel):
    api_id: int
    api_hash: Text


class StartIn(BaseModel):
    phone: Text
    api_id: Optional[int] = None      # only needed the first time; remembered for the next accounts
    api_hash: Optional[Text] = None


class CodeIn(BaseModel):
    code: Text


class PasswordIn(BaseModel):
    password: Text


class AccountPatch(BaseModel):
    label: Text


@router.get("/status")
def status(s: Session = Depends(get_session)):
    """Cheap health/overview call (the Dashboard numbers are in /stats)."""
    count = lambda q: s.exec(q).one()  # noqa: E731
    return {
        "module": "telegram",
        "accounts": count(select(func.count()).select_from(TgAccount)),
        "accounts_online": count(select(func.count()).select_from(TgAccount).where(TgAccount.status == "online")),
        "chats": count(select(func.count()).select_from(TgChat)),
        "runs": count(select(func.count()).select_from(TgRun)),
    }


class ResetIn(BaseModel):
    account_id: Optional[int] = None      # one account, or all of them


@router.post("/reset")
def reset_data(body: ResetIn, s: Session = Depends(get_session)):
    """Start the numbers from zero: delete the stored chats and every run (with its history) of one account or of all.
    Accounts, workflows and uploaded files stay. Chats that still exist in Telegram come back with the next sync."""
    one = body.account_id
    if one is not None:
        _get_account(s, one)
    run_where = [] if one is None else [TgRun.account_id == one]
    chat_where = [] if one is None else [TgChat.account_id == one]
    if s.exec(select(TgRun.id).where(TgRun.status.in_(ACTIVE_RUN), *run_where)).first():
        raise HTTPException(409, "A run is still active, stop it first")
    if any(one is None or acc == one for acc in tg.syncing):
        raise HTTPException(409, "A chat sync is running, wait until it has finished")
    run_ids = s.exec(select(TgRun.id).where(*run_where)).all()
    chats = s.exec(select(func.count()).select_from(TgChat).where(*chat_where)).one()
    for i in range(0, len(run_ids), 500):      # SQLite limits how many values one IN (...) may hold
        part = run_ids[i:i + 500]
        s.exec(sa_delete(TgRunChat).where(TgRunChat.run_id.in_(part)))
        s.exec(sa_delete(TgRun).where(TgRun.id.in_(part)))
    s.exec(sa_delete(TgChat).where(*chat_where))
    s.commit()
    tg._publish({"type": "reset", "account_id": one})
    return {"chats": chats, "runs": len(run_ids)}


@router.get("/settings")
def get_settings(s: Session = Depends(get_session)):
    c = _saved_credentials(s)
    return {"api_id": c["api_id"], "api_hash_hint": ("…" + c["api_hash"][-4:]) if c["api_hash"] else "",
            "configured": bool(c["api_id"] and c["api_hash"])}


@router.put("/settings")
def put_settings(body: SettingsIn, s: Session = Depends(get_session)):
    _check_credentials(body.api_id, body.api_hash.strip())
    _save_credentials(s, body.api_id, body.api_hash.strip())
    return get_settings(s)


@router.get("/accounts")
def list_accounts(s: Session = Depends(get_session)):
    counts = dict(s.exec(select(TgChat.account_id, func.count()).group_by(TgChat.account_id)).all())
    return [_account_public(a, counts.get(a.id, 0)) for a in s.exec(select(TgAccount).order_by(TgAccount.id)).all()]


@router.post("/accounts/start")
async def start_account(body: StartIn, s: Session = Depends(get_session)):
    """Step 1 of linking: validate the credentials and have Telegram send the login code."""
    phone = _normalize_phone(body.phone)
    saved = _saved_credentials(s)
    api_id, api_hash = body.api_id or saved["api_id"], (body.api_hash or "").strip() or saved["api_hash"]
    _check_credentials(api_id, api_hash)
    acc = s.exec(select(TgAccount).where(TgAccount.phone == phone)).first()
    created = acc is None
    if acc and acc.status == "online":
        raise HTTPException(409, "This account is already linked and online")
    if created:
        acc = TgAccount(phone=phone)
    acc.api_id, acc.api_hash = api_id, api_hash
    s.add(acc)
    s.commit()
    s.refresh(acc)
    try:
        await _call(tg.start_login(acc.id))
    except HTTPException:
        if created:
            s.delete(acc)
            s.commit()
        raise
    if body.api_id and body.api_hash:
        _save_credentials(s, api_id, api_hash)   # remembered only once Telegram accepted them
    return {"id": acc.id, "phone": phone, "step": "code"}


@router.post("/accounts/{id_}/code")
async def submit_code(id_: int, body: CodeIn, s: Session = Depends(get_session)):
    _get_account(s, id_)
    step = await _call(tg.submit_code(id_, body.code))
    if step != "done":
        return {"step": step}
    s.expire_all()
    return {"step": "done", "account": _account_public(_get_account(s, id_))}


@router.post("/accounts/{id_}/password")
async def submit_password(id_: int, body: PasswordIn, s: Session = Depends(get_session)):
    _get_account(s, id_)
    await _call(tg.submit_password(id_, body.password))
    s.expire_all()
    return {"step": "done", "account": _account_public(_get_account(s, id_))}


@router.post("/accounts/{id_}/cancel")
async def cancel_login(id_: int, s: Session = Depends(get_session)):
    """The operator closed the dialog: forget the pending login and the row it created."""
    acc = _get_account(s, id_)
    await tg.forget_pending(id_)
    if not acc.session_string and not s.exec(select(TgChat.id).where(TgChat.account_id == id_)).first():
        s.delete(acc)
        s.commit()
    return {"ok": True}


@router.post("/accounts/{id_}/connect")
async def connect_account(id_: int, s: Session = Depends(get_session)):
    _get_account(s, id_)
    await _call(tg.connect(id_))
    s.expire_all()
    return _account_public(_get_account(s, id_))


@router.post("/accounts/{id_}/disconnect")
async def disconnect_account(id_: int, s: Session = Depends(get_session)):
    _get_account(s, id_)
    await _call(tg.disconnect(id_))
    s.expire_all()
    return _account_public(_get_account(s, id_))


@router.patch("/accounts/{id_}")
def rename_account(id_: int, body: AccountPatch, s: Session = Depends(get_session)):
    acc = _get_account(s, id_)
    if len(body.label.strip()) > MAX_LABEL:
        raise HTTPException(422, f"The label is too long ({MAX_LABEL} characters at most)")
    acc.label = body.label.strip() or acc.phone
    s.add(acc)
    s.commit()
    s.refresh(acc)
    return _account_public(acc)


@router.delete("/accounts/{id_}")
async def delete_account(id_: int, s: Session = Depends(get_session)):
    _get_account(s, id_)
    active = s.exec(select(TgRun.id).where(TgRun.account_id == id_,
                                           TgRun.status.in_(ACTIVE_RUN))).first()
    if active:
        raise HTTPException(409, "This account has an active run, stop it first")
    run_ids = s.exec(select(TgRun.id).where(TgRun.account_id == id_)).all()
    await tg.forget(id_)
    if run_ids:
        s.exec(sa_delete(TgRunChat).where(TgRunChat.run_id.in_(run_ids)))
        s.exec(sa_delete(TgRun).where(TgRun.id.in_(run_ids)))
    s.exec(sa_delete(TgChat).where(TgChat.account_id == id_))
    s.exec(sa_delete(TgAccount).where(TgAccount.id == id_))
    s.commit()
    return {"ok": True}


@router.post("/accounts/{id_}/sync-chats")
async def sync_chats(id_: int, s: Session = Depends(get_session)):
    """Import the account's existing private chats in the background (progress arrives over the WebSocket)."""
    _get_account(s, id_)
    try:
        started = tg.start_sync(id_)
    except TgError as e:
        raise HTTPException(e.status, str(e))
    return {"started": started, "running": True}


# ---------------------------------------------------------------------------
# Chats
# ---------------------------------------------------------------------------

CHAT_STATUSES = ("pending", "in_progress", "done", "error", "paused")
CHAT_SORTS = {"id": TgChat.id, "last_contact_at": TgChat.last_contact_at, "first_contact_at": TgChat.first_contact_at,
              "display_name": TgChat.search_text,   # casefolded name first: case-insensitive, also for umlauts
              "chat_status": TgChat.chat_status, "messages_sent": TgChat.messages_sent}
ChatSort = Literal["id", "last_contact_at", "first_contact_at", "display_name", "chat_status", "messages_sent"]


class ChatPatch(BaseModel):
    chat_status: Optional[str] = None
    notes: Optional[Text] = None


class BulkStatusIn(BaseModel):
    ids: list[int]
    status: str


def _check_status(value: str) -> str:
    if value not in CHAT_STATUSES:
        raise HTTPException(422, "Invalid chat status")
    return value


def _when(value: str, end_of_day: bool = False) -> datetime:
    """A date ('2026-03-01', taken as UTC) or a datetime with offset -> aware UTC.
    A date used as the upper bound covers that whole day."""
    try:
        d = datetime.fromisoformat(value)
        d = d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)   # overflows at year 1 / 9999
        if end_of_day and len(value) <= 10:
            d = d.replace(hour=23, minute=59, second=59, microsecond=999999)
    except (ValueError, OverflowError):
        raise HTTPException(422, "Invalid date")
    return d


def _chat_filters(account_id, status, q, date_from, date_to) -> list:
    """WHERE conditions shared by the list, the id list and the summary."""
    where = []
    if account_id is not None:
        where.append(TgChat.account_id == account_id)
    statuses = [_check_status(x) for x in status.split(",") if x]
    if statuses:
        where.append(TgChat.chat_status.in_(statuses))
    needle = q.strip().lstrip("@").casefold()
    if needle:
        where.append(TgChat.search_text.contains(needle, autoescape=True))
    if date_from:
        where.append(TgChat.last_contact_at >= _when(date_from))
    if date_to:
        where.append(TgChat.last_contact_at <= _when(date_to, end_of_day=True))
    return where


def _chat_public(c: TgChat) -> dict:
    d = c.model_dump(exclude={"access_hash", "search_text"})
    for k in ("first_contact_at", "last_contact_at", "last_processed_at", "created_at"):
        d[k] = iso(d[k])
    return d


def _get_chat(s: Session, id_: int) -> TgChat:
    chat = s.get(TgChat, id_)
    if not chat:
        raise HTTPException(404, "Chat not found")
    return chat


@router.get("/chats")
def list_chats(account_id: Optional[int] = None, status: str = "", q: str = "",
               date_from: Optional[str] = None, date_to: Optional[str] = None,
               sort: ChatSort = "last_contact_at", order: Literal["asc", "desc"] = "desc",
               limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0),
               s: Session = Depends(get_session)):
    where = _chat_filters(account_id, status, q, date_from, date_to)
    total = s.exec(select(func.count()).select_from(TgChat).where(*where)).one()
    key = CHAT_SORTS[sort]
    rows = s.exec(select(TgChat).where(*where).order_by(key.desc() if order == "desc" else key.asc(), TgChat.id)
                  .offset(offset).limit(limit)).all()
    return {"total": total, "items": [_chat_public(c) for c in rows]}


@router.get("/chats/ids")
def chat_ids(account_id: Optional[int] = None, status: str = "", q: str = "",
             date_from: Optional[str] = None, date_to: Optional[str] = None, s: Session = Depends(get_session)):
    """Every id matching the filters (no paging): lets the panel select all 1,248 matches at once."""
    ids = s.exec(select(TgChat.id).where(*_chat_filters(account_id, status, q, date_from, date_to))
                 .order_by(TgChat.id)).all()
    return {"total": len(ids), "ids": ids}


@router.get("/chats/summary")
def chat_summary(account_id: Optional[int] = None, s: Session = Depends(get_session)):
    where = _chat_filters(account_id, "", "", None, None)
    counts = dict(s.exec(select(TgChat.chat_status, func.count()).where(*where).group_by(TgChat.chat_status)).all())
    by_status = {k: counts.get(k, 0) for k in CHAT_STATUSES}
    return {"total": sum(by_status.values()), "by_status": by_status}


@router.get("/chats/{id_}")
def get_chat(id_: int, s: Session = Depends(get_session)):
    return _chat_public(_get_chat(s, id_))


@router.patch("/chats/{id_}")
def patch_chat(id_: int, body: ChatPatch, s: Session = Depends(get_session)):
    chat = _get_chat(s, id_)
    if body.chat_status is not None:
        chat.chat_status = _check_status(body.chat_status)
        if chat.chat_status != "error":
            chat.error_reason = ""
    if body.notes is not None:
        if len(body.notes) > 2000:
            raise HTTPException(422, "Notes are too long (2000 characters at most)")
        chat.notes = body.notes
    s.add(chat)
    s.commit()
    s.refresh(chat)
    return _chat_public(chat)


@router.post("/chats/bulk-status")
def bulk_status(body: BulkStatusIn, s: Session = Depends(get_session)):
    status = _check_status(body.status)
    if not body.ids:
        raise HTTPException(422, "No chats selected")
    values = {"chat_status": status, **({} if status == "error" else {"error_reason": ""})}
    updated = 0
    for i in range(0, len(body.ids), 500):    # stay below SQLite's limit on bound parameters
        updated += s.exec(sa_update(TgChat).where(TgChat.id.in_(body.ids[i:i + 500])).values(**values)).rowcount
    s.commit()
    return {"updated": updated}


# ---------------------------------------------------------------------------
# Media (images and voice memos used by workflow steps)
# ---------------------------------------------------------------------------
# Files live in storage/telegram/media/ under generated names, so an uploaded name never reaches the disk.
# What a file is gets decided from its content (magic bytes); the uploaded extension only has to agree.
# To support another kind (video, document, ...): add it to MEDIA_KINDS, FORMATS and CONTENT_TYPES here,
# and one step type to STEP_TYPES below.

MB = 1024 * 1024
MEDIA_KINDS = {    # kind -> name prefix, size limit in bytes, extensions a stored file can have
    "image": {"prefix": "img", "limit": 10 * MB, "stored": ("jpg", "png", "webp")},
    "voice": {"prefix": "voice", "limit": 50 * MB, "stored": ("ogg",)},
}
FORMATS = {        # sniffed format -> (kind, extensions an upload may carry, extension it is stored under)
    "jpeg": ("image", ("jpg", "jpeg"), "jpg"),
    "png": ("image", ("png",), "png"),
    "webp": ("image", ("webp",), "webp"),
    "ogg": ("voice", ("ogg", "oga", "opus"), "ogg"),
    "mp3": ("voice", ("mp3",), "ogg"),
    "m4a": ("voice", ("m4a",), "ogg"),
    "wav": ("voice", ("wav",), "ogg"),
    "aac": ("voice", ("aac",), "ogg"),
}
CONTENT_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp", "ogg": "audio/ogg"}
MEDIA_NAME = re.compile("(%s)-[0-9a-f]{32}\\.(%s)" % (
    "|".join(k["prefix"] for k in MEDIA_KINDS.values()),
    "|".join(e for k in MEDIA_KINDS.values() for e in k["stored"])))
UPLOAD_HINT = "use jpg, png, webp, ogg, opus, mp3, m4a, wav or aac"


class MediaError(Exception):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


def media_dir() -> Path:
    d = cfg.STORAGE_DIR / "telegram" / "media"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _kind_of(name: str) -> str:
    return next(k for k, v in MEDIA_KINDS.items() if name.startswith(v["prefix"] + "-"))


def _sniff(head: bytes) -> Optional[str]:
    """The real format of a file, from its first bytes."""
    if head[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head[:4] == b"OggS":
        return "ogg"
    if head[4:8] == b"ftyp":
        return "m4a"
    if len(head) > 1 and head[0] == 0xFF and head[1] & 0xF6 == 0xF0:    # ADTS frame: sync word, layer 00
        return "aac"
    if head[:3] == b"ID3" or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0 and (head[1] >> 1) & 3):
        return "mp3"
    return None


def _is_opus(head: bytes) -> bool:
    return head[:4] == b"OggS" and b"OpusHead" in head[:128]


def _voice_seconds(path: Path) -> Optional[float]:
    """Length of an OGG/Opus file from the granule position of its last page (no decoding needed)."""
    size = path.stat().st_size
    with open(path, "rb") as f:
        head = f.read(128)
        if not _is_opus(head):
            return None
        f.seek(max(0, size - 65536))
        tail = f.read()
    pre_skip = int.from_bytes(head[head.find(b"OpusHead") + 10:][:2], "little")
    last = tail.rfind(b"OggS")
    if last < 0 or len(tail) < last + 14:
        return None
    granule = int.from_bytes(tail[last + 6:last + 14], "little", signed=True)
    return round(max(granule - pre_skip, 0) / 48000, 1) if granule >= 0 else None


def _ffmpeg() -> Optional[str]:
    return shutil.which(os.environ.get("FFMPEG_BIN") or "ffmpeg")


def _to_opus(data: bytes, ext: str) -> bytes:
    """Telegram shows a voice bubble only for OGG/Opus, so every other audio format is converted."""
    exe = _ffmpeg()
    if not exe:
        raise MediaError("Converting this audio file needs ffmpeg, which is not installed on the server. "
                         "Upload an OGG/Opus file instead.", 503)
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp, "in." + ext), Path(tmp, "out.ogg")
        src.write_bytes(data)
        cmd = [exe, "-nostdin", "-v", "error", "-y", "-i", str(src), "-vn", "-map_metadata", "-1", "-c:a", "libopus",
               "-b:a", "32k", "-ar", "48000", "-ac", "1", "-application", "voip", "-f", "ogg", str(dst)]
        try:
            done = subprocess.run(cmd, capture_output=True, timeout=300)
        except (OSError, subprocess.SubprocessError):
            raise MediaError("The audio conversion failed (ffmpeg could not be run)", 500)
        converted = done.returncode == 0 and dst.exists()
        limit = MEDIA_KINDS["voice"]["limit"]
        if converted and dst.stat().st_size > limit:      # the output can be bigger than the upload
            raise MediaError(f"The file is too large ({limit // MB} MB at most for this type)", 413)
        out = dst.read_bytes() if converted else b""
    if not _is_opus(out[:128]):
        raise MediaError("The audio file could not be converted, it may be damaged")
    return out


def _check_filename(filename: str) -> str:
    """The extension of an upload. Names that could leave the folder are refused. Dots inside the name are fine
    (WhatsApp Audio 2026-10-11 at 01.23.45.ogg): the file is stored under a generated name and what it is gets
    decided from its content, so a name like shell.php.jpg cannot do anything."""
    if (not filename or len(filename) > 255 or ".." in filename
            or any(c in filename for c in "/\\:") or any(ord(c) < 32 for c in filename)):
        raise MediaError("Invalid file name")
    stem, dot, ext = filename.rpartition(".")
    if not dot or not stem:
        raise MediaError(f"The file has no extension, {UPLOAD_HINT}")
    return ext.lower()


def _save_media(filename: str, source) -> dict:
    """Validate one upload (name, real content, size), store it and return its media info."""
    ext = _check_filename(filename)
    head = source.read(32)
    if not head:
        raise MediaError("The file is empty")
    fmt = _sniff(head)
    if fmt is None:
        raise MediaError(f"Unsupported file type, {UPLOAD_HINT}")
    kind, exts, stored = FORMATS[fmt]
    if ext not in exts:
        raise MediaError(f"The file content does not match its extension (.{ext})")
    limit = MEDIA_KINDS[kind]["limit"]
    data = head + source.read(limit + 1 - len(head))
    if len(data) > limit:
        raise MediaError(f"The file is too large ({limit // MB} MB at most for this type)", 413)
    if kind == "image":
        try:
            with Image.open(io.BytesIO(data)) as im:
                if (im.format or "").lower() != fmt:
                    raise ValueError(fmt)
                im.verify()
        except Exception:  # noqa: BLE001  Pillow raises many different types for damaged files
            raise MediaError("The image is damaged or not a real image")
    elif not _is_opus(data[:128]):
        data = _to_opus(data, ext)
    name = f"{MEDIA_KINDS[kind]['prefix']}-{secrets.token_hex(16)}.{stored}"
    (media_dir() / name).write_bytes(data)
    return _media_info(name)


def _media_info(name: str) -> dict:
    path = media_dir() / name
    kind = _kind_of(name)
    return {"name": name, "kind": kind, "size": path.stat().st_size,
            "duration": _voice_seconds(path) if kind == "voice" else None}


def _media_path(name: str) -> Path:
    if not MEDIA_NAME.fullmatch(name):
        raise HTTPException(404, "File not found")
    path = media_dir() / name
    if not path.is_file():
        raise HTTPException(404, "File not found")
    return path


def _media_users(s: Session, name: str) -> list[str]:
    """Workflows and unfinished runs that still send this file."""
    users = [w.name for w in s.exec(select(TgWorkflow)).all() if any(st.get("file") == name for st in w.steps)]
    for r in s.exec(select(TgRun).where(TgRun.status.in_(ACTIVE_RUN))).all():
        if any(st.get("file") == name for st in (r.workflow_snapshot or {}).get("steps", [])):
            users.append(f"{r.workflow_name} (run {r.id})")
    return users


@router.post("/media")
def upload_media(files: list[UploadFile] = File(...)):
    """One or many files. Files that fail validation are listed in `rejected`; when none was accepted
    the call fails with the first reason."""
    saved, rejected, first = [], [], None
    for f in files:
        try:
            saved.append(_save_media(f.filename or "", f.file))
        except MediaError as e:
            first = first or e
            rejected.append({"filename": f.filename or "", "error": str(e)})
    if not saved:
        raise HTTPException(first.status, str(first))
    return {"saved": saved, "rejected": rejected}


@router.get("/media")
def list_media(s: Session = Depends(get_session)):
    paths = sorted((p for p in media_dir().iterdir() if MEDIA_NAME.fullmatch(p.name)),
                   key=lambda p: (-p.stat().st_mtime, p.name))
    return [{**_media_info(p.name), "used_by": _media_users(s, p.name)} for p in paths]


def _unused_media(s: Session, min_age: timedelta) -> list[dict]:
    """Files no workflow and no unfinished run uses, and that were uploaded at least `min_age` ago (a file the editor
    just uploaded is not in any workflow until the operator saves it)."""
    used = {st.get("file") for w in s.exec(select(TgWorkflow)).all() for st in w.steps}
    used |= {st.get("file") for r in s.exec(select(TgRun).where(TgRun.status.in_(ACTIVE_RUN))).all()
             for st in (r.workflow_snapshot or {}).get("steps", [])}
    cutoff = time.time() - min_age.total_seconds()
    paths = (p for p in media_dir().iterdir() if MEDIA_NAME.fullmatch(p.name) and p.name not in used)
    return [_media_info(p.name) for p in sorted(paths) if p.stat().st_mtime <= cutoff]


class MediaCleanupIn(BaseModel):
    min_age_minutes: int = Field(60, ge=0, le=525600)


@router.get("/media/unused")
def unused_media(min_age_minutes: int = Query(60, ge=0, le=525600), s: Session = Depends(get_session)):
    """Uploaded files that no workflow uses any more (what POST /media/cleanup would delete)."""
    items = _unused_media(s, timedelta(minutes=min_age_minutes))
    return {"items": items, "bytes": sum(i["size"] for i in items)}


@router.post("/media/cleanup")
def cleanup_media(body: MediaCleanupIn, s: Session = Depends(get_session)):
    """Delete the files GET /media/unused lists."""
    items = _unused_media(s, timedelta(minutes=body.min_age_minutes))
    for i in items:
        (media_dir() / i["name"]).unlink(missing_ok=True)
    return {"deleted": len(items), "bytes": sum(i["size"] for i in items)}


@router.get("/media/{name}")
def get_media(name: str):
    path = _media_path(name)
    return FileResponse(path, media_type=CONTENT_TYPES[path.suffix[1:]],
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"})


@router.delete("/media/{name}")
def delete_media(name: str, s: Session = Depends(get_session)):
    path = _media_path(name)
    users = _media_users(s, name)
    if users:
        raise HTTPException(409, f"This file is used by: {', '.join(users)}")
    path.unlink()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------
# A step is {"type", <what it sends>, "pause_after": seconds}. Each step type is ONE entry in STEP_TYPES:
# a function that takes the raw step and returns the cleaned fields it owns ("content" or "file"),
# raising ValueError with the reason. A new type (video, document, sticker, ...) is one more entry.

MAX_PAUSE = 86400
MAX_TEXT = 4096
MAX_STEPS = 100


def _text_step(step: dict) -> dict:
    text = step.get("content")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text is required")
    if len(text) > MAX_TEXT:
        raise ValueError(f"text is too long ({MAX_TEXT} characters at most)")
    _encodable(text)
    return {"content": text}


# Telegram's "show for ..." choices of self-destructing media: "once" (view once) or a number of seconds.
# A voice message can only be played once.
SELF_DESTRUCT = {"image": ("once", 3, 10, 30), "voice": ("once",)}


def _media_step(kind: str) -> Callable[[dict], dict]:
    def check(step: dict) -> dict:
        name = step.get("file")
        if not isinstance(name, str) or not name:
            raise ValueError(f"a {kind} file is required")
        if not MEDIA_NAME.fullmatch(name) or _kind_of(name) != kind:
            raise ValueError(f"the file is not a {kind} file")
        if not (media_dir() / name).is_file():
            raise ValueError("the uploaded file does not exist, upload it again")
        shown = step.get("self_destruct")        # how long the contact can see it after opening; absent = it stays
        if shown is not None and (type(shown) not in (int, str) or shown not in SELF_DESTRUCT[kind]):
            raise ValueError("self_destruct must be one of: " + ", ".join(str(v) for v in SELF_DESTRUCT[kind]))
        return {"file": name, **({"self_destruct": shown} if shown is not None else {})}
    return check


def _block_step(step: dict) -> dict:
    return {}      # an action without content: the engine blocks the contact on Telegram


STEP_TYPES: dict[str, Callable[[dict], dict]] = {
    "text": _text_step,
    "image": _media_step("image"),
    "voice": _media_step("voice"),
    "block": _block_step,
}
LAST_ONLY = {"block"}      # step types that end a chat, so they may only be the last step (and only once)


def _clean_steps(raw: list) -> list[dict]:
    if not raw:
        raise HTTPException(422, "A workflow needs at least one step")
    if len(raw) > MAX_STEPS:
        raise HTTPException(422, f"A workflow can have {MAX_STEPS} steps at most")
    steps = []
    for n, step in enumerate(raw, 1):
        if not isinstance(step, dict):
            raise HTTPException(422, f"Step {n}: invalid step")
        kind = step.get("type")
        if not isinstance(kind, str) or kind not in STEP_TYPES:
            raise HTTPException(422, f"Step {n}: unknown step type")
        pause = step.get("pause_after", 0)
        if type(pause) is not int or not 0 <= pause <= MAX_PAUSE:
            raise HTTPException(422, f"Step {n}: the pause must be a whole number of seconds from 0 to {MAX_PAUSE}")
        if kind in LAST_ONLY and n != len(raw):
            raise HTTPException(422, f"Step {n}: blocking the user is only allowed as the last step")
        try:
            fields = STEP_TYPES[kind](step)
        except ValueError as e:
            raise HTTPException(422, f"Step {n}: {e}")
        steps.append({"type": kind, **fields, "pause_after": 0 if kind in LAST_ONLY else pause})
    return steps


def _taken_names(s: Session, own_id: Optional[int] = None) -> set[str]:
    return {w.name.casefold() for w in s.exec(select(TgWorkflow)).all() if w.id != own_id}


def _clean_name(s: Session, raw: str, own_id: Optional[int] = None) -> str:
    name = raw.strip()
    if not 1 <= len(name) <= 80:
        raise HTTPException(422, "The workflow name must be 1 to 80 characters long")
    if name.casefold() in _taken_names(s, own_id):
        raise HTTPException(409, "A workflow with this name already exists")
    return name


def _get_workflow(s: Session, id_: int) -> TgWorkflow:
    w = s.get(TgWorkflow, id_)
    if not w:
        raise HTTPException(404, "Workflow not found")
    return w


def _workflow_public(w: TgWorkflow) -> dict:
    """`media` describes the files the steps use (size, voice length), or marks one as missing."""
    media = {}
    for st in w.steps:
        name = st.get("file")
        if name and name not in media:
            media[name] = _media_info(name) if (media_dir() / name).is_file() else {"missing": True}
    return {"id": w.id, "name": w.name, "steps": w.steps, "media": media,
            "created_at": iso(w.created_at), "updated_at": iso(w.updated_at)}


def _store_workflow(s: Session, w: TgWorkflow) -> dict:
    w.updated_at = utcnow()
    s.add(w)
    try:
        s.commit()
    except IntegrityError:   # two saves of the same new name at once (double click): the unique index decides
        s.rollback()
        raise HTTPException(409, "A workflow with this name already exists")
    s.refresh(w)
    return _workflow_public(w)


class WorkflowIn(BaseModel):
    name: Text
    steps: list[Any]


class WorkflowRename(BaseModel):
    name: Text


class WorkflowCopy(BaseModel):
    name: Optional[Text] = None


@router.get("/workflows")
def list_workflows(s: Session = Depends(get_session)):
    return [_workflow_public(w) for w in s.exec(select(TgWorkflow).order_by(TgWorkflow.id)).all()]


@router.post("/workflows")
def create_workflow(body: WorkflowIn, s: Session = Depends(get_session)):
    return _store_workflow(s, TgWorkflow(name=_clean_name(s, body.name), steps=_clean_steps(body.steps)))


@router.get("/workflows/{id_}")
def get_workflow(id_: int, s: Session = Depends(get_session)):
    return _workflow_public(_get_workflow(s, id_))


@router.put("/workflows/{id_}")
def save_workflow(id_: int, body: WorkflowIn, s: Session = Depends(get_session)):
    """Replace name and steps (the editor's Save). Runs already started keep the snapshot they froze."""
    w = _get_workflow(s, id_)
    w.name, w.steps = _clean_name(s, body.name, id_), _clean_steps(body.steps)
    return _store_workflow(s, w)


@router.patch("/workflows/{id_}")
def rename_workflow(id_: int, body: WorkflowRename, s: Session = Depends(get_session)):
    w = _get_workflow(s, id_)
    w.name = _clean_name(s, body.name, id_)
    return _store_workflow(s, w)


@router.post("/workflows/{id_}/duplicate")
def duplicate_workflow(id_: int, body: Optional[WorkflowCopy] = None, s: Session = Depends(get_session)):
    src = _get_workflow(s, id_)
    if body and body.name is not None:
        name = _clean_name(s, body.name)
    else:    # "Name (copy)", "Name (copy 2)", ... kept within 80 characters
        taken, n = _taken_names(s), 1
        while True:
            suffix = " (copy)" if n == 1 else f" (copy {n})"
            name = src.name[:80 - len(suffix)] + suffix
            if name.casefold() not in taken:
                break
            n += 1
    return _store_workflow(s, TgWorkflow(name=name, steps=[dict(st) for st in src.steps]))


@router.delete("/workflows/{id_}")
def delete_workflow(id_: int, s: Session = Depends(get_session)):
    _get_workflow(s, id_)
    if s.exec(select(TgRun.id).where(TgRun.workflow_id == id_, TgRun.status.in_(ACTIVE_RUN))).first():
        raise HTTPException(409, "This workflow has an active run, stop it first")
    # finished runs keep their name and frozen snapshot; only the link to the deleted row goes
    s.exec(sa_update(TgRun).where(TgRun.workflow_id == id_).values(workflow_id=None))
    s.exec(sa_delete(TgWorkflow).where(TgWorkflow.id == id_))
    s.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Runs (a workflow sent to chosen chats, one chat at a time; the work itself is in engine.py)
# ---------------------------------------------------------------------------

RUN_STATUSES = ("queued", "running", "paused", "stopped", "done", "error")


class RunIn(BaseModel):
    account_id: int
    workflow_id: int
    chat_ids: list[int]
    on_error: Literal["next", "retry"] = "next"    # a failed chat: go on with the next one | try the step again
    retries: int = Field(3, ge=1, le=5)            # extra attempts per step when on_error = retry
    auto_resume: bool = False                      # go on by itself when the account is online again after a pause


# pause, resume and stop are async on purpose: they flip the run task's asyncio gate, which belongs to the event loop
def _get_run(s: Session, id_: int) -> TgRun:
    run = s.get(TgRun, id_)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


def _run_now(s: Session, id_: int) -> dict:
    """The run's state as the engine left it (the session may still hold an older copy)."""
    s.expire_all()
    return run_state(s, _get_run(s, id_))


def _start_run(s: Session, account_id: int, workflow_id: Optional[int], name: str, snapshot: dict,
               chat_ids: list[int], on_error: str, retries: int, auto_resume: bool) -> dict:
    run_id = tg.runs.start(account_id, workflow_id, name, snapshot, chat_ids, on_error, retries, auto_resume)
    return _run_now(s, run_id)


@router.post("/runs")
async def create_run(body: RunIn, s: Session = Depends(get_session)):
    """Start a run: the workflow is copied (later edits do not change it) and the chats are worked in the given order."""
    _get_account(s, body.account_id)
    w = _get_workflow(s, body.workflow_id)
    steps = _clean_steps(w.steps)       # the same check as saving: a media file may have been removed since
    chat_ids = list(dict.fromkeys(body.chat_ids))
    if not chat_ids:
        raise HTTPException(422, "No chats selected")
    own = 0
    for i in range(0, len(chat_ids), 500):
        own += s.exec(select(func.count()).select_from(TgChat)
                      .where(TgChat.account_id == body.account_id, TgChat.id.in_(chat_ids[i:i + 500]))).one()
    if own != len(chat_ids):
        raise HTTPException(422, "Some of the chats do not belong to this account")
    try:
        return _start_run(s, body.account_id, w.id, w.name, {"name": w.name, "steps": steps}, chat_ids,
                          body.on_error, body.retries, body.auto_resume)
    except TgError as e:
        raise HTTPException(e.status, str(e))


def _run_filters(account_id, workflow_id, status, date_from, date_to) -> list:
    """WHERE conditions shared by the run list and its CSV export."""
    where = []
    if account_id is not None:
        where.append(TgRun.account_id == account_id)
    if workflow_id is not None:
        where.append(TgRun.workflow_id == workflow_id)
    statuses = [x for x in status.split(",") if x]
    if any(x not in RUN_STATUSES for x in statuses):
        raise HTTPException(422, "Invalid run status")
    if statuses:
        where.append(TgRun.status.in_(statuses))
    if date_from:
        where.append(TgRun.created_at >= _when(date_from))
    if date_to:
        where.append(TgRun.created_at <= _when(date_to, end_of_day=True))
    return where


@router.get("/runs")
def list_runs(account_id: Optional[int] = None, workflow_id: Optional[int] = None, status: str = "",
              date_from: Optional[str] = None, date_to: Optional[str] = None,
              limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0), s: Session = Depends(get_session)):
    """Newest first."""
    where = _run_filters(account_id, workflow_id, status, date_from, date_to)
    total = s.exec(select(func.count()).select_from(TgRun).where(*where)).one()
    rows = s.exec(select(TgRun).where(*where).order_by(TgRun.created_at.desc(), TgRun.id.desc())
                  .offset(offset).limit(limit)).all()
    return {"total": total, "items": [run_state(s, r) for r in rows]}


# --- history: CSV export and cleanup (declared before /runs/{id_} so "export.csv" is not read as an id) ---

def _csv_cell(value):
    """Chat names are typed by strangers: a leading = + - @ would make Excel run the cell as a formula."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def _csv_response(filename: str, header: list[str], rows) -> Response:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)
    for row in rows:
        writer.writerow([_csv_cell(v) for v in row])
    # the byte order mark makes Excel read umlauts and emoji as UTF-8
    return Response("\ufeff" + out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/runs/export.csv")
def export_runs(account_id: Optional[int] = None, workflow_id: Optional[int] = None, status: str = "",
                date_from: Optional[str] = None, date_to: Optional[str] = None, s: Session = Depends(get_session)):
    """One row per run, the same filters as the list."""
    where = _run_filters(account_id, workflow_id, status, date_from, date_to)
    rows = s.exec(select(TgRun).where(*where).order_by(TgRun.created_at.desc(), TgRun.id.desc())).all()
    accounts = {a.id: a.label or a.phone for a in s.exec(select(TgAccount)).all()}
    states = [run_state(s, r) for r in rows]
    return _csv_response("telegram-runs.csv",
                         ["run_id", "account", "workflow", "status", "started_at", "finished_at", "chats_selected",
                          "successful", "errors", "aborted", "duration_seconds"],
                         [[r["id"], accounts.get(r["account_id"], ""), r["workflow_name"], r["status"], r["started_at"] or "",
                           r["finished_at"] or "", r["total"], r["success"], r["errors"], r["skipped"],
                           "" if r["duration_seconds"] is None else r["duration_seconds"]] for r in states])


class CleanupIn(BaseModel):
    days: int = Field(ge=1, le=36500)


@router.post("/runs/cleanup")
def cleanup_runs(body: CleanupIn, s: Session = Depends(get_session)):
    """Delete finished runs that ended more than `days` days ago, with their per-chat results.
    The chats keep their status, message count and notes."""
    cutoff = utcnow() - timedelta(days=body.days)
    ids = s.exec(select(TgRun.id).where(TgRun.status.notin_(ACTIVE_RUN),
                                        func.coalesce(TgRun.finished_at, TgRun.created_at) < cutoff)).all()
    for i in range(0, len(ids), 500):
        part = ids[i:i + 500]
        s.exec(sa_delete(TgRunChat).where(TgRunChat.run_id.in_(part)))
        s.exec(sa_delete(TgRun).where(TgRun.id.in_(part)))
    s.commit()
    return {"deleted": len(ids)}


@router.get("/runs/{id_}")
def get_run(id_: int, s: Session = Depends(get_session)):
    return run_state(s, _get_run(s, id_))


@router.get("/runs/{id_}/chats")
def run_chats(id_: int, status: str = "", limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0),
              s: Session = Depends(get_session)):
    """What happened to each chat of the run, in the order they are worked."""
    _get_run(s, id_)
    statuses = [x for x in status.split(",") if x]
    where = [TgRunChat.run_id == id_, *([TgRunChat.status.in_(statuses)] if statuses else [])]
    total = s.exec(select(func.count()).select_from(TgRunChat).where(*where)).one()
    rows = s.exec(select(TgRunChat, TgChat).join(TgChat, TgChat.id == TgRunChat.chat_id).where(*where)
                  .order_by(TgRunChat.position).offset(offset).limit(limit)).all()
    return {"total": total, "items": [
        {"id": rc.id, "position": rc.position, "chat_id": chat.id, "display_name": chat.display_name,
         "username": chat.username, "telegram_id": chat.telegram_id, "status": rc.status, "steps_done": rc.steps_done,
         "error_reason": rc.error_reason, "started_at": iso(rc.started_at), "processed_at": iso(rc.processed_at)}
        for rc, chat in rows]}


@router.get("/runs/{id_}/export.csv")
def export_run_chats(id_: int, s: Session = Depends(get_session)):
    """What happened to each chat of the run: when, the result and the error reason."""
    _get_run(s, id_)
    rows = s.exec(select(TgRunChat, TgChat).join(TgChat, TgChat.id == TgRunChat.chat_id)
                  .where(TgRunChat.run_id == id_).order_by(TgRunChat.position)).all()
    return _csv_response(f"telegram-run-{id_}.csv",
                         ["position", "chat", "username", "telegram_id", "result", "steps_done", "error_reason",
                          "started_at", "processed_at"],
                         [[rc.position + 1, chat.display_name, chat.username, chat.telegram_id, rc.status, rc.steps_done,
                           rc.error_reason, iso(rc.started_at) or "", iso(rc.processed_at) or ""] for rc, chat in rows])


@router.delete("/runs/{id_}")
def delete_run(id_: int, s: Session = Depends(get_session)):
    """Remove a finished run and its per-chat results (the chats themselves are untouched)."""
    run = _get_run(s, id_)
    if run.status in ACTIVE_RUN:
        raise HTTPException(409, "The run is still active, stop it first")
    s.exec(sa_delete(TgRunChat).where(TgRunChat.run_id == id_))
    s.delete(run)
    s.commit()
    return {"ok": True}


@router.post("/runs/{id_}/pause")
async def pause_run(id_: int, s: Session = Depends(get_session)):
    _get_run(s, id_)
    try:
        tg.runs.pause(id_)
    except TgError as e:
        raise HTTPException(e.status, str(e))
    return _run_now(s, id_)


@router.post("/runs/{id_}/resume")
async def resume_run(id_: int, s: Session = Depends(get_session)):
    _get_run(s, id_)
    try:
        tg.runs.resume(id_)
    except TgError as e:
        raise HTTPException(e.status, str(e))
    return _run_now(s, id_)


@router.post("/runs/{id_}/stop")
async def stop_run(id_: int, s: Session = Depends(get_session)):
    _get_run(s, id_)
    await _call(tg.runs.stop(id_))
    return _run_now(s, id_)


@router.post("/runs/{id_}/restart")
async def restart_run(id_: int, s: Session = Depends(get_session)):
    """A new run over the same workflow snapshot and the same chats, in the same order."""
    old = _get_run(s, id_)
    if old.status in ACTIVE_RUN:
        raise HTTPException(409, "The run is still active, stop it first")
    chat_ids = s.exec(select(TgRunChat.chat_id).where(TgRunChat.run_id == id_).order_by(TgRunChat.position)).all()
    try:
        return _start_run(s, old.account_id, old.workflow_id, old.workflow_name, old.workflow_snapshot, chat_ids,
                          old.on_error, old.retries, old.auto_resume)
    except TgError as e:
        raise HTTPException(e.status, str(e))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/stats")
def stats(account_id: Optional[int] = None, days: int = Query(14, ge=1, le=90), s: Session = Depends(get_session)):
    """Everything the Dashboard shows. With account_id every number is about that account only.
    A "send" is one chat the workflow was run through: successful = all steps went out, failed = it ended in an error.
    The per-day figures count UTC days."""
    if account_id is not None:
        _get_account(s, account_id)
    chat_where = _chat_filters(account_id, "", "", None, None)
    run_where = [TgRun.account_id == account_id] if account_id is not None else []
    by_status = dict(s.exec(select(TgChat.chat_status, func.count()).where(*chat_where).group_by(TgChat.chat_status)).all())
    chats_by = {k: by_status.get(k, 0) for k in CHAT_STATUSES}

    def sends(*extra):     # run-chat results, limited to the account's runs
        q = select(TgRunChat.status, func.count()).join(TgRun, TgRun.id == TgRunChat.run_id).where(*run_where, *extra)
        return q.group_by(TgRunChat.status)
    results = dict(s.exec(sends()).all())
    since = (utcnow() - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    day = func.date(TgRunChat.processed_at)
    per_day = {}
    for d, status, n in s.exec(select(day, TgRunChat.status, func.count()).join(TgRun, TgRun.id == TgRunChat.run_id)
                               .where(*run_where, TgRunChat.status.in_(("done", "error")), TgRunChat.processed_at >= since)
                               .group_by(day, TgRunChat.status)).all():
        per_day.setdefault(str(d), {"done": 0, "error": 0})[status] = n

    active = s.exec(select(TgRun).where(*run_where, TgRun.status.in_(ACTIVE_RUN))
                    .order_by(TgRun.created_at.desc(), TgRun.id.desc())).first()
    last = s.exec(select(TgRun).where(*run_where, TgRun.status.notin_(ACTIVE_RUN))
                  .order_by(func.coalesce(TgRun.finished_at, TgRun.created_at).desc(), TgRun.id.desc())).first()
    accounts = s.exec(select(TgAccount.status, func.count()).group_by(TgAccount.status)).all()
    return {
        "accounts": sum(n for _, n in accounts), "accounts_online": sum(n for st, n in accounts if st == "online"),
        "chats": {"total": sum(chats_by.values()), "unprocessed": chats_by["pending"], "processed": chats_by["done"],
                  "errors": chats_by["error"], "in_progress": chats_by["in_progress"], "paused": chats_by["paused"]},
        "runs": s.exec(select(func.count()).select_from(TgRun).where(*run_where)).one(),
        "sends": {"successful": results.get("done", 0), "failed": results.get("error", 0),
                  "messages": s.exec(select(func.coalesce(func.sum(TgChat.messages_sent), 0)).where(*chat_where)).one()},
        "active_run": run_state(s, active) if active else None,    # name, id, chat and progress of the run in progress
        "last_run": run_state(s, last) if last else None,
        "per_day": [{"date": str(d), "successful": per_day.get(str(d), {}).get("done", 0),
                     "failed": per_day.get(str(d), {}).get("error", 0)}
                    for d in (since.date() + timedelta(days=i) for i in range(days))],
    }
