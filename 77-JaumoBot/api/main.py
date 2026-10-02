"""FastAPI admin backend. Run with a single worker:  uvicorn api.main:app"""

import asyncio
import io
import json
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import date, datetime, time as dtime, timedelta, timezone
from typing import Optional

from fastapi import (Depends, FastAPI, File, HTTPException, Query, Request, Response,
                     UploadFile, WebSocket, WebSocketDisconnect)
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy import delete as sa_delete
from sqlalchemy import case, func, or_
from sqlmodel import Session, select

from . import settings as cfg
from bot.engine import AUTO_FEMALE_NAMES, RELATIONSHIP_VALUES

from .auth import (COOKIE_NAME, check_credentials, is_https, make_token, require_auth,
                   verify_token, ws_authenticated)
from .manager import (ACTIVE_STATUSES, BOT_DEFAULTS, IDENTITY_DEFAULTS, Hub, RunManager, event_public,
                      about_pool_for, about_usage, get_bot_settings, get_identity, get_main_config, name_pool_for,
                      name_usage, run_public)
from .photolib import THUMBS_DIR, delete_photo_files, import_uploads, photo_usage, sync_library
from .models import (Account, AccountEvent, ApkProfile, AppSetting, BotConfig, BotRun, Photo, Proxy, RunLog, engine,
                     get_session, init_db, iso, utcnow)
from .proxies import parse_proxy_line, save_test_result, split_lines, test_proxy
from .schemas import (StatsSyncIn, SwipeIn, SettingsIn, PhotoBulkDelete, AccountPatch, ApkMoveConfigs, ApkPatch, ApkProfileIn, CleanupIn, ConfigIn, ConfigPatch, ConfigSettings,
                      LoginIn, MessageLaunch, ProxyBulkAction, ProxyBulkIn, ProxyIn,
                      ProxyUpdate, RunLaunch)

hub = Hub()
manager = RunManager(hub)

_SOURCE_FILES = [*(cfg.ROOT_DIR / "api").glob("*.py"), *(cfg.ROOT_DIR / "bot").glob("*.py")]


def _code_stamp() -> float:
    """Newest modification time of the Python sources on disk."""
    return max((f.stat().st_mtime for f in _SOURCE_FILES if f.exists()), default=0.0)


SERVER_CODE_STAMP = _code_stamp()  # what this process actually loaded


# ---------------------------------------------------------------------------
# Startup: DB, seeds, legacy import
# ---------------------------------------------------------------------------

DEFAULT_USER_AGENT = "Android 202609.1.4 (1001864) (GooglePlay;Free)"


def _env_apk(s: Session):
    """The APK key pair from JAUMO_CLIENT_ID / JAUMO_SIGN_SECRET / JAUMO_USER_AGENT, kept as an
    ApkProfile row so health tracking keeps working. None when the env vars are not set."""
    if not (cfg.SEED_CLIENT_ID and cfg.SEED_SIGN_SECRET):
        return None
    apk = s.exec(select(ApkProfile).where(ApkProfile.client_id == cfg.SEED_CLIENT_ID)).first()
    if apk is None:
        name, n = "Jaumo APK", 2
        while s.exec(select(ApkProfile).where(ApkProfile.name == name)).first():
            name, n = f"Jaumo APK {n}", n + 1
        apk = ApkProfile(name=name, client_id=cfg.SEED_CLIENT_ID, sign_secret=cfg.SEED_SIGN_SECRET,
                         user_agent=cfg.SEED_USER_AGENT or DEFAULT_USER_AGENT)
    else:
        apk.sign_secret = cfg.SEED_SIGN_SECRET
        apk.user_agent = cfg.SEED_USER_AGENT or apk.user_agent
        apk.enabled = True
    s.add(apk)
    s.commit()
    s.refresh(apk)
    return apk


def _seed():
    """One Jaumo configuration; its APK keys come from the env vars, else the profile stored before."""
    with Session(engine) as s:
        apk = _env_apk(s)
        if not s.exec(select(BotConfig)).first():
            fallback = apk or s.exec(select(ApkProfile).where(ApkProfile.enabled == True)).first()  # noqa: E712
            s.add(BotConfig(name="Jaumo", apk_profile_id=fallback.id if fallback else None,
                            settings=ConfigSettings().model_dump()))
            s.commit()
        main = get_main_config(s)
        current = s.get(ApkProfile, main.apk_profile_id) if main.apk_profile_id else None
        if apk:
            main.apk_profile_id = apk.id
        elif not current or not current.enabled:
            stored = s.exec(select(ApkProfile).where(ApkProfile.enabled == True).order_by(ApkProfile.id)).first()  # noqa: E712
            main.apk_profile_id = stored.id if stored else main.apk_profile_id
        s.add(main)
        s.commit()


def _import_legacy_accounts():
    """One-time import of the old accounts.txt (JSON lines) into the Account table."""
    path = cfg.LEGACY_ACCOUNTS_FILE
    if not path.exists():
        return
    with Session(engine) as s:
        existing = set(s.exec(select(Account.android_id)).all())
        added = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                a = json.loads(line)
            except ValueError:
                continue
            if a.get("android_id") in existing:
                continue
            created = a.get("created")
            try:
                created_at = datetime.fromisoformat(created) if created else utcnow()
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
            except ValueError:
                created_at = utcnow()
            liked = [str(x) for x in a.get("liked", [])]
            disliked = [str(x) for x in a.get("disliked", [])]
            matches = [str(x) for x in a.get("matches", [])]
            s.add(Account(
                created_at=created_at, name=a.get("name", ""), gender=a.get("gender", 2),
                birthday=a.get("birthday", ""), looking_for_gender=a.get("looking_for_gender", 1),
                location=a.get("location", ""), photo_url=a.get("photo_url"), status="legacy",
                photo_uploaded=bool(a.get("photo_uploaded")), gallery_count=a.get("gallery_count") or 0,
                android_id=a.get("android_id", ""), device_id=a.get("device_id", ""),
                access_token=a.get("access_token", ""), refresh_token=a.get("refresh_token", ""),
                liked=liked, disliked=disliked, matches=matches,
                liked_count=len(liked), disliked_count=len(disliked), matches_count=len(matches),
                messages_sent=a.get("messages_sent", 0) or 0, notes="imported from accounts.txt",
            ))
            existing.add(a.get("android_id"))
            added += 1
        s.commit()
    path.rename(path.with_suffix(".txt.imported"))
    print(f"[startup] imported {added} legacy accounts from {path.name}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg.PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    manager.mark_interrupted()
    _seed()
    _import_legacy_accounts()
    with Session(engine) as s:
        sync_library(s)
        manager.set_parallel(get_bot_settings(s)["parallel_accounts"])
    hub.loop = asyncio.get_running_loop()
    if cfg.SECRET_KEY_IS_RANDOM:
        print("[startup] SECRET_KEY not set — sessions will reset on every restart")
    if cfg.ADMIN_PASS == "changeme":
        print("[startup] WARNING: ADMIN_PASS is the default 'changeme'")
    yield
    manager.shutdown()


app = FastAPI(title="Jaumo Bot Admin", lifespan=lifespan, docs_url=None, redoc_url=None)
auth = [Depends(require_auth)]


def _iso(d):
    return iso(d)


def _local_midnight(d: date) -> datetime:
    """Start of a calendar day in the server's local timezone, as aware datetime."""
    return datetime.combine(d, dtime.min).astimezone()


def _get_or_404(s: Session, model, id_):
    obj = s.get(model, id_)
    if not obj:
        raise HTTPException(404, f"{model.__name__} not found")
    return obj


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.post("/api/login")
def login(body: LoginIn, request: Request, response: Response):
    if not check_credentials(body.username, body.password):
        time.sleep(1)
        raise HTTPException(401, "Invalid username or password")
    response.set_cookie(COOKIE_NAME, make_token(body.username), httponly=True, samesite="lax",
                        secure=is_https(request), max_age=cfg.SESSION_DAYS * 86400)
    return {"ok": True, "user": body.username}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@app.get("/api/version")
def version():
    """outdated=True when the Python code on disk changed after this server started (needs a restart)."""
    return {"outdated": _code_stamp() > SERVER_CODE_STAMP + 1}


@app.get("/api/me")
def me(request: Request):
    user = verify_token(request.cookies.get(COOKIE_NAME))
    return {"authenticated": bool(user), "user": user}


@app.get("/api/meta", dependencies=auth)
def meta():
    with Session(engine) as s:
        offered = s.get(AppSetting, "signup_defaults")
    return {"signup_defaults": offered.value if offered else None,
            "relationship_values": list(RELATIONSHIP_VALUES),
            "default_settings": ConfigSettings().model_dump(),
            "auto_names": AUTO_FEMALE_NAMES}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@app.get("/api/stats", dependencies=auth)
def stats(s: Session = Depends(get_session)):
    today = _local_midnight(date.today())
    count = lambda q: s.exec(q).one()  # noqa: E731
    acc_by_status = dict(s.exec(select(Account.status, func.count()).group_by(Account.status)).all())
    totals = s.exec(select(func.coalesce(func.sum(Account.liked_count), 0),
                           func.coalesce(func.sum(Account.disliked_count), 0),
                           func.coalesce(func.sum(Account.matches_count), 0),
                           func.coalesce(func.sum(Account.messages_sent), 0))).one()
    return {
        "running": count(select(func.count()).select_from(BotRun).where(BotRun.status == "running", BotRun.kind != "sync")),
        "queued": count(select(func.count()).select_from(BotRun).where(BotRun.status == "queued", BotRun.kind != "sync")),
        "syncing": count(select(func.count()).select_from(BotRun).where(BotRun.status.in_(ACTIVE_STATUSES), BotRun.kind == "sync")),
        "parallel": manager.parallel,
        "created_today": count(select(func.count()).select_from(Account).where(Account.created_at >= today)),
        "accounts_total": sum(acc_by_status.values()),
        "accounts_by_status": acc_by_status,
        "liked": totals[0], "disliked": totals[1], "matches": totals[2], "messages_sent": totals[3],
        "proxies_enabled": count(select(func.count()).select_from(Proxy).where(Proxy.enabled == True)),  # noqa: E712
        "proxies_in_use": manager.pool.usage(),
        "apk_warnings": _apk_warnings(s),
    }


STATUS_GROUPS = {"active": "active", "legacy": "active", "blocked": "blocked",
                 "photo_failed": "failed", "failed": "failed"}


@app.get("/api/stats/daily", dependencies=auth)
def stats_daily(days: int = Query(14, ge=1, le=90), tz_offset: int = 0, s: Session = Depends(get_session)):
    """
    Accounts created per local calendar day, split by current outcome.
    tz_offset is the browser's Date.getTimezoneOffset() (minutes, UTC − local).
    """
    offset = timedelta(minutes=-tz_offset)
    today_local = (utcnow() + offset).date()
    start_local = today_local - timedelta(days=days - 1)
    start_utc = datetime.combine(start_local, dtime.min, tzinfo=timezone.utc) - offset
    buckets = {start_local + timedelta(days=i): {"created": 0, "active": 0, "blocked": 0, "failed": 0,
                                                  "other": 0, "likes": 0, "matches": 0}
               for i in range(days)}
    rows = s.exec(select(Account.created_at, Account.status, Account.liked_count, Account.matches_count)
                  .where(Account.created_at >= start_utc)).all()
    for created, status, liked, matches in rows:
        b = buckets.get((created + offset).date())
        if b is None:
            continue
        b["created"] += 1
        b[STATUS_GROUPS.get(status, "other")] += 1
        b["likes"] += liked or 0
        b["matches"] += matches or 0
    return [{"date": d.isoformat(), **v} for d, v in buckets.items()]


def _apk_warnings(s: Session) -> list[dict]:
    """APK profiles that need attention: failing, or disabled but still used by configs."""
    used = {}
    for c in s.exec(select(BotConfig)).all():
        used.setdefault(c.apk_profile_id, []).append(c.name)
    out = []
    for a in s.exec(select(ApkProfile)).all():
        configs = used.get(a.id, [])
        if a.enabled and a.fail_streak >= APK_FAIL_WARN:
            out.append({"id": a.id, "name": a.name, "problem": f"{a.fail_streak} failures in a row",
                        "last_error": a.last_error, "configs": configs})
        elif not a.enabled and configs:
            out.append({"id": a.id, "name": a.name, "problem": "disabled but still used by configs",
                        "last_error": a.last_error, "configs": configs})
    return out


# ---------------------------------------------------------------------------
# APK profiles
# ---------------------------------------------------------------------------

APK_FAIL_WARN = 3  # consecutive client-token failures before an APK profile is flagged


def _apk_public(a: ApkProfile, s: Session) -> dict:
    d = a.model_dump(exclude={"sign_secret"})
    d["sign_secret_hint"] = ("…" + a.sign_secret[-4:]) if a.sign_secret else ""
    for k in ("created_at", "last_ok_at", "last_fail_at"):
        d[k] = _iso(getattr(a, k))
    d["used_by"] = s.exec(select(BotConfig.name).where(BotConfig.apk_profile_id == a.id)).all()
    if not a.enabled:
        d["health"] = "disabled"
    elif a.fail_streak >= APK_FAIL_WARN:
        d["health"] = "failing"
    elif a.last_ok_at is None and a.last_fail_at is None:
        d["health"] = "untested"
    else:
        d["health"] = "ok" if a.fail_streak == 0 else "warning"
    return d


@app.get("/api/apk-profiles", dependencies=auth)
def list_apk(s: Session = Depends(get_session)):
    return [_apk_public(a, s) for a in s.exec(select(ApkProfile).order_by(ApkProfile.id)).all()]


@app.post("/api/apk-profiles", dependencies=auth)
def create_apk(body: ApkProfileIn, s: Session = Depends(get_session)):
    if not body.sign_secret:
        raise HTTPException(422, "sign_secret is required")
    if s.exec(select(ApkProfile).where(ApkProfile.name == body.name)).first():
        raise HTTPException(409, "name already exists")
    a = ApkProfile(**body.model_dump())
    s.add(a)
    s.commit()
    s.refresh(a)
    return _apk_public(a, s)


@app.put("/api/apk-profiles/{id_}", dependencies=auth)
def update_apk(id_: int, body: ApkProfileIn, s: Session = Depends(get_session)):
    a = _get_or_404(s, ApkProfile, id_)
    data = body.model_dump()
    if not data["sign_secret"]:
        data.pop("sign_secret")
    creds_changed = any(k in data and data[k] != getattr(a, k) for k in ApkProfile.CREDENTIAL_FIELDS)
    for k, v in data.items():
        setattr(a, k, v)
    if creds_changed:
        a.fail_streak, a.last_error = 0, ""  # new credentials — start health fresh
    s.add(a)
    s.commit()
    s.refresh(a)
    return _apk_public(a, s)


@app.patch("/api/apk-profiles/{id_}", dependencies=auth)
def patch_apk(id_: int, body: ApkPatch, s: Session = Depends(get_session)):
    a = _get_or_404(s, ApkProfile, id_)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(a, k, v)
    s.add(a)
    s.commit()
    s.refresh(a)
    return _apk_public(a, s)


@app.post("/api/apk-profiles/{id_}/reset-health", dependencies=auth)
def reset_apk_health(id_: int, s: Session = Depends(get_session)):
    a = _get_or_404(s, ApkProfile, id_)
    a.fail_streak, a.last_error = 0, ""
    s.add(a)
    s.commit()
    s.refresh(a)
    return _apk_public(a, s)


@app.post("/api/apk-profiles/{id_}/move-configs", dependencies=auth)
def move_apk_configs(id_: int, body: ApkMoveConfigs, s: Session = Depends(get_session)):
    """Switch every config using this APK profile to another one (e.g. after a ban)."""
    _get_or_404(s, ApkProfile, id_)
    target = _get_or_404(s, ApkProfile, body.to_apk_profile_id)
    if target.id == id_:
        raise HTTPException(422, "choose a different APK profile")
    configs = s.exec(select(BotConfig).where(BotConfig.apk_profile_id == id_)).all()
    for c in configs:
        c.apk_profile_id = target.id
        c.updated_at = utcnow()
        s.add(c)
    s.commit()
    return {"moved": len(configs), "configs": [c.name for c in configs], "to": target.name}


@app.delete("/api/apk-profiles/{id_}", dependencies=auth)
def delete_apk(id_: int, s: Session = Depends(get_session)):
    a = _get_or_404(s, ApkProfile, id_)
    used = s.exec(select(BotConfig.name).where(BotConfig.apk_profile_id == id_)).all()
    if used:
        raise HTTPException(409, f"in use by configs: {', '.join(used)}")
    s.delete(a)
    s.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Configs
# ---------------------------------------------------------------------------

def _config_public(c: BotConfig, apk_names: dict, usage=None) -> dict:
    d = c.model_dump()
    # Fill in any settings keys added after this config was saved.
    d["settings"] = ConfigSettings.model_validate({**ConfigSettings().model_dump(), **(c.settings or {})}).model_dump()
    if usage is not None:
        pool = name_pool_for(d["settings"])
        d["names_total"] = len(pool)
        d["names_unused"] = sum(1 for n in pool if not usage[n.strip().casefold()])
    apk = apk_names.get(c.apk_profile_id)
    d["apk_profile_name"] = apk.name if apk else None
    d["apk_profile_enabled"] = apk.enabled if apk else None
    d["apk_profile_fail_streak"] = apk.fail_streak if apk else 0
    d["created_at"], d["updated_at"] = _iso(c.created_at), _iso(c.updated_at)
    return d


def _apk_names(s):
    return {a.id: a for a in s.exec(select(ApkProfile)).all()}


@app.get("/api/configs", dependencies=auth)
def list_configs(s: Session = Depends(get_session)):
    names, usage = _apk_names(s), name_usage(s)
    return [_config_public(c, names, usage) for c in s.exec(select(BotConfig).order_by(BotConfig.id)).all()]


def _main_config_public(s: Session) -> dict:
    c = get_main_config(s)
    if not c:
        raise HTTPException(404, "no configuration")
    d = _config_public(c, _apk_names(s), name_usage(s))
    apk = s.get(ApkProfile, c.apk_profile_id) if c.apk_profile_id else None
    d["apk"] = _apk_public(apk, s) if apk else None
    texts, used = about_pool_for(d["settings"]), about_usage(s)
    d["about_total"] = len(texts)
    d["about_unused"] = sum(1 for x in texts if not used[x.strip().casefold()])
    from_env = bool(apk and cfg.SEED_CLIENT_ID and cfg.SEED_SIGN_SECRET and apk.client_id == cfg.SEED_CLIENT_ID)
    d["apk_source"] = "env" if from_env else "stored" if apk else "none"
    return d


@app.get("/api/config", dependencies=auth)
def get_config(s: Session = Depends(get_session)):
    """The single Jaumo configuration, with the APK key status (never the secret)."""
    return _main_config_public(s)


@app.put("/api/config", dependencies=auth)
def put_config(body: ConfigPatch, s: Session = Depends(get_session)):
    """Update part of the settings (each panel page saves only its own fields)."""
    c = get_main_config(s)
    if not c:
        raise HTTPException(404, "no configuration")
    current = {**ConfigSettings().model_dump(), **(c.settings or {})}
    try:
        merged = ConfigSettings.model_validate({**current, **body.settings})
    except ValidationError as e:
        raise HTTPException(422, "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()))
    c.settings = merged.model_dump()
    c.updated_at = utcnow()
    s.add(c)
    s.commit()
    hub.publish("events", {"type": "settings"})
    return _main_config_public(s)


@app.get("/api/about/usage", dependencies=auth)
def about_texts_usage(s: Session = Depends(get_session)):
    """Profile texts already taken (case-insensitive key -> count), for the Profiltexte page."""
    return dict(about_usage(s))


@app.get("/api/names/usage", dependencies=auth)
def names_usage(s: Session = Depends(get_session)):
    """Names already taken (case-insensitive key -> count), for the config editor."""
    return dict(name_usage(s))


def _check_apk(s, apk_id):
    if apk_id is not None and not s.get(ApkProfile, apk_id):
        raise HTTPException(422, "APK profile not found")


@app.post("/api/configs", dependencies=auth)
def create_config(body: ConfigIn, s: Session = Depends(get_session)):
    _check_apk(s, body.apk_profile_id)
    if s.exec(select(BotConfig).where(BotConfig.name == body.name)).first():
        raise HTTPException(409, "name already exists")
    c = BotConfig(name=body.name, apk_profile_id=body.apk_profile_id, settings=body.settings.model_dump())
    s.add(c)
    s.commit()
    s.refresh(c)
    return _config_public(c, _apk_names(s))


@app.put("/api/configs/{id_}", dependencies=auth)
def update_config(id_: int, body: ConfigIn, s: Session = Depends(get_session)):
    c = _get_or_404(s, BotConfig, id_)
    _check_apk(s, body.apk_profile_id)
    clash = s.exec(select(BotConfig).where(BotConfig.name == body.name, BotConfig.id != id_)).first()
    if clash:
        raise HTTPException(409, "name already exists")
    c.name, c.apk_profile_id = body.name, body.apk_profile_id
    c.settings = body.settings.model_dump()
    c.updated_at = utcnow()
    s.add(c)
    s.commit()
    s.refresh(c)
    return _config_public(c, _apk_names(s))


@app.post("/api/configs/{id_}/duplicate", dependencies=auth)
def duplicate_config(id_: int, s: Session = Depends(get_session)):
    c = _get_or_404(s, BotConfig, id_)
    base, n = f"{c.name} (copy)", 2
    name = base
    while s.exec(select(BotConfig).where(BotConfig.name == name)).first():
        name, n = f"{base} {n}", n + 1
    copy = BotConfig(name=name, apk_profile_id=c.apk_profile_id, settings=dict(c.settings))
    s.add(copy)
    s.commit()
    s.refresh(copy)
    return _config_public(copy, _apk_names(s))


@app.delete("/api/configs/{id_}", dependencies=auth)
def delete_config(id_: int, s: Session = Depends(get_session)):
    c = _get_or_404(s, BotConfig, id_)
    s.delete(c)
    s.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Proxies
# ---------------------------------------------------------------------------

def _proxy_public(p: Proxy, usage: dict) -> dict:
    d = p.model_dump()
    for k in ("last_used_at", "last_test_at", "created_at"):
        d[k] = _iso(d[k])
    d["in_use"] = usage.get(p.id, 0)
    return d


@app.get("/api/proxies", dependencies=auth)
def list_proxies(s: Session = Depends(get_session)):
    usage = manager.pool.usage()
    return [_proxy_public(p, usage) for p in s.exec(select(Proxy).order_by(Proxy.id)).all()]


@app.post("/api/proxies", dependencies=auth)
def create_proxy(body: ProxyIn, s: Session = Depends(get_session)):
    if body.line:
        try:
            fields = parse_proxy_line(body.line)
        except ValueError as e:
            raise HTTPException(422, str(e))
    else:
        if not body.host or not body.port:
            raise HTTPException(422, "host and port are required")
        fields = {"scheme": body.scheme, "host": body.host, "port": body.port,
                  "username": body.username, "password": body.password}
    p = Proxy(**fields, label=body.label, shared=body.shared, enabled=body.enabled)
    s.add(p)
    s.commit()
    s.refresh(p)
    manager.pool.notify()
    return _proxy_public(p, manager.pool.usage())


@app.post("/api/proxies/bulk", dependencies=auth)
def bulk_add_proxies(body: ProxyBulkIn, s: Session = Depends(get_session)):
    lines = split_lines(body.text)
    if not lines:
        raise HTTPException(422, "no proxy lines found")
    parsed, errors = [], []
    for i, line in enumerate(lines, 1):
        try:
            parsed.append(parse_proxy_line(line))
        except ValueError as e:
            errors.append(f"line {i}: {e}")
    if errors:
        raise HTTPException(422, "; ".join(errors[:20]))
    if body.replace:
        for p in s.exec(select(Proxy)).all():
            s.delete(p)
    for i, fields in enumerate(parsed, 1):
        label = f"{body.label} #{i}" if body.label and len(parsed) > 1 else body.label
        s.add(Proxy(**fields, label=label, shared=body.shared))
    s.commit()
    manager.pool.notify()
    return {"added": len(parsed)}


@app.put("/api/proxies/{id_}", dependencies=auth)
def update_proxy(id_: int, body: ProxyUpdate, s: Session = Depends(get_session)):
    p = _get_or_404(s, Proxy, id_)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    s.add(p)
    s.commit()
    s.refresh(p)
    manager.pool.notify()
    return _proxy_public(p, manager.pool.usage())


@app.delete("/api/proxies/{id_}", dependencies=auth)
def delete_proxy(id_: int, s: Session = Depends(get_session)):
    p = _get_or_404(s, Proxy, id_)
    s.delete(p)
    s.commit()
    return {"ok": True}


@app.post("/api/proxies/{id_}/test", dependencies=auth)
def test_one_proxy(id_: int, s: Session = Depends(get_session)):
    p = _get_or_404(s, Proxy, id_)
    result = test_proxy(p)
    save_test_result(s, p, result)
    s.commit()
    return result


def _test_many(ids: Optional[list[int]] = None):
    with Session(engine) as s:
        q = select(Proxy) if ids is None else select(Proxy).where(Proxy.id.in_(ids))
        proxies = s.exec(q).all()
        with ThreadPoolExecutor(max_workers=10) as ex:
            results = list(ex.map(test_proxy, proxies))
        for p, r in zip(proxies, results):
            save_test_result(s, p, r)
        s.commit()
        return {"tested": len(proxies), "ok": sum(r["ok"] for r in results)}


@app.post("/api/proxies/test-all", dependencies=auth)
def test_all_proxies():
    return _test_many()


@app.post("/api/proxies/bulk-action", dependencies=auth)
def proxies_bulk_action(body: ProxyBulkAction, s: Session = Depends(get_session)):
    if body.action == "test":
        return _test_many(body.ids)
    proxies = s.exec(select(Proxy).where(Proxy.id.in_(body.ids))).all()
    for p in proxies:
        if body.action == "delete":
            s.delete(p)
        elif body.action in ("enable", "disable"):
            p.enabled = body.action == "enable"
            s.add(p)
        elif body.action in ("shared", "dedicated"):
            p.shared = body.action == "shared"
            s.add(p)
        else:
            raise HTTPException(422, "unknown action")
    s.commit()
    manager.pool.notify()
    return {"ok": True, "count": len(proxies)}


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

@app.post("/api/runs", dependencies=auth)
def launch_runs(body: RunLaunch):
    try:
        ids = manager.launch_signup(body.config_id, body.count, body.names)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"run_ids": ids}


@app.post("/api/runs/check", dependencies=auth)
def check_runs(body: RunLaunch):
    """What would stop POST /api/runs with the same body (nothing is started)."""
    try:
        problems = manager.check_signup(body.config_id, body.count, body.names)
    except LookupError as e:
        raise HTTPException(404, str(e))
    return {"ok": not problems, "problems": problems}


@app.get("/api/runs", dependencies=auth)
def list_runs(status: Optional[str] = None, kind: Optional[str] = None, active: bool = False,
              limit: int = Query(100, le=1000), offset: int = 0, s: Session = Depends(get_session)):
    q = select(BotRun)
    cq = select(func.count()).select_from(BotRun)
    conds = []
    if active:
        conds.append(BotRun.status.in_(ACTIVE_STATUSES))
    elif status:
        conds.append(BotRun.status.in_(status.split(",")))
    if kind:
        conds.append(BotRun.kind == kind)
    for c in conds:
        q, cq = q.where(c), cq.where(c)
    rows = s.exec(q.order_by(BotRun.id.desc()).offset(offset).limit(limit)).all()
    return {"total": s.exec(cq).one(), "items": [run_public(r) for r in rows]}


@app.get("/api/runs/{id_}", dependencies=auth)
def get_run(id_: int, s: Session = Depends(get_session)):
    run = _get_or_404(s, BotRun, id_)
    d = run_public(run)
    d["settings"] = run.config_snapshot.get("settings")
    d["apk_profile_name"] = run.config_snapshot.get("apk_profile_name")
    return d


@app.get("/api/runs/{id_}/logs", dependencies=auth)
def run_logs(id_: int, after_id: int = 0, levels: Optional[str] = None,
             limit: int = Query(2000, le=10000), s: Session = Depends(get_session)):
    q = select(RunLog).where(RunLog.run_id == id_, RunLog.id > after_id)
    if levels:
        q = q.where(RunLog.level.in_(levels.split(",")))
    rows = s.exec(q.order_by(RunLog.id).limit(limit)).all()
    return [{"id": r.id, "ts": _iso(r.ts), "level": r.level, "msg": r.msg} for r in rows]


@app.post("/api/runs/stop-all", dependencies=auth)
def stop_all_runs():
    return {"stopped": manager.stop_all()}


@app.post("/api/runs/{id_}/stop", dependencies=auth)
def stop_run(id_: int):
    if not manager.stop(id_):
        raise HTTPException(409, "run is not active")
    return {"ok": True}


@app.delete("/api/runs/{id_}", dependencies=auth)
def delete_run(id_: int, s: Session = Depends(get_session)):
    run = _get_or_404(s, BotRun, id_)
    if run.status in ACTIVE_STATUSES:
        raise HTTPException(409, "stop the run first")
    s.exec(sa_delete(RunLog).where(RunLog.run_id == id_))
    s.delete(run)
    s.commit()
    return {"ok": True}


@app.post("/api/runs/cleanup", dependencies=auth)
def cleanup_runs(body: CleanupIn, s: Session = Depends(get_session)):
    cutoff = utcnow() - timedelta(days=body.days)
    old = select(BotRun.id).where(BotRun.status.not_in(ACTIVE_STATUSES), BotRun.created_at < cutoff)
    ids = s.exec(old).all()
    if ids:
        s.exec(sa_delete(RunLog).where(RunLog.run_id.in_(ids)))
        if body.delete_runs:
            s.exec(sa_delete(BotRun).where(BotRun.id.in_(ids)))
    s.commit()
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
    return {"runs_cleaned": len(ids)}


# ---------------------------------------------------------------------------
# Messaging job
# ---------------------------------------------------------------------------

@app.post("/api/messages", dependencies=auth)
def launch_messages(body: MessageLaunch):
    try:
        ids = manager.launch_messages(body.config_id, body.account_ids)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"run_ids": ids}


# ---------------------------------------------------------------------------
# Photos
# ---------------------------------------------------------------------------

def _photo_path(name: str, thumb: bool = False):
    base = THUMBS_DIR if thumb else cfg.PHOTOS_DIR
    path = (base / name).resolve()
    if path.parent != base.resolve() or not path.is_file():
        raise HTTPException(404, "photo not found")
    return path


@app.get("/api/photos", dependencies=auth)
def list_photos(s: Session = Depends(get_session)):
    usage, owner, reserved = photo_usage(s)
    out = []
    for p in s.exec(select(Photo).order_by(Photo.id.desc())).all():
        acc = owner.get(p.filename)
        status = "used" if acc else "reserved" if p.filename in reserved else "available"
        out.append({"name": p.filename, "size": p.size, "width": p.width, "height": p.height,
                    "original_name": p.original_name, "created_at": _iso(p.created_at), "status": status,
                    "uses": usage[p.filename],
                    "account": {"id": acc[0], "name": acc[1], "status": acc[2]} if acc else None})
    return out


@app.post("/api/photos", dependencies=auth)
def upload_photos(files: list[UploadFile] = File(...), s: Session = Depends(get_session)):
    """Images (jpg/png/webp/...) and/or ZIP archives. Each image is cleaned, de-duplicated and thumbnailed."""
    payload = [(f.filename or "upload", f.file.read()) for f in files]
    results = import_uploads(s, payload)
    counts = {k: sum(1 for r in results if r["status"] == k) for k in ("saved", "duplicate", "error")}
    return {**counts, "results": results}


@app.get("/api/photos/{name}/file", dependencies=auth)
def get_photo(name: str):
    return FileResponse(_photo_path(name), media_type="image/jpeg")


@app.get("/api/photos/{name}/thumb", dependencies=auth)
def get_photo_thumb(name: str):
    try:
        path = _photo_path(name, thumb=True)
    except HTTPException:
        path = _photo_path(name)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


def _delete_photos(s: Session, names: list[str]) -> dict:
    usage, owner, reserved = photo_usage(s)
    deleted, blocked = [], []
    for name in names:
        row = s.exec(select(Photo).where(Photo.filename == name)).first()
        if not row:
            continue
        if owner.get(name) or name in reserved:
            blocked.append(name)
            continue
        s.delete(row)
        delete_photo_files(name)
        deleted.append(name)
    s.commit()
    return {"deleted": deleted, "blocked": blocked}


@app.delete("/api/photos/{name}", dependencies=auth)
def delete_photo(name: str, s: Session = Depends(get_session)):
    res = _delete_photos(s, [name])
    if res["blocked"]:
        raise HTTPException(409, "photo is used by an account (or reserved by a queued bot) and is kept for its history")
    if not res["deleted"]:
        raise HTTPException(404, "photo not found")
    return {"ok": True}


@app.post("/api/photos/bulk-delete", dependencies=auth)
def bulk_delete_photos(body: PhotoBulkDelete, s: Session = Depends(get_session)):
    return _delete_photos(s, body.names)


# ---------------------------------------------------------------------------
# Settings (global)
# ---------------------------------------------------------------------------

@app.get("/api/settings", dependencies=auth)
def get_settings(s: Session = Depends(get_session)):
    usage, owner, reserved = photo_usage(s)
    photos = s.exec(select(Photo.filename)).all()
    return {
        "identity": get_identity(s),
        "bot": get_bot_settings(s),
        "counts": {
            "photos_total": len(photos),
            "photos_available": sum(1 for f in photos if not usage[f]),
            "names_used": len(name_usage(s)),
        },
    }


@app.put("/api/settings", dependencies=auth)
def put_settings(body: SettingsIn, s: Session = Depends(get_session)):
    for key, part, defaults in (("identity", body.identity, IDENTITY_DEFAULTS), ("bot", body.bot, BOT_DEFAULTS)):
        if part is None:
            continue
        row = s.get(AppSetting, key) or AppSetting(key=key, value=dict(defaults))
        row.value = {**defaults, **(row.value or {}), **part.model_dump(exclude_unset=True)}
        s.add(row)
    s.commit()
    manager.set_parallel(get_bot_settings(s)["parallel_accounts"])
    hub.publish("events", {"type": "settings"})
    return get_settings(s)


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

ACCOUNT_SORTS = {"id", "created_at", "name", "location", "status", "liked_count", "worker",
                 "disliked_count", "matches_count", "messages_sent", "last_activity_at"}

# Client-facing account state (Aktiv / Arbeitet / Gesperrt / Fehler / Gestoppt)
STATE_STATUSES = {
    "active": ("active", "legacy"),
    "blocked": ("blocked",),
    "error": ("failed", "photo_failed"),
    "stopped": ("stopped",),
}


def _working_ids(s: Session) -> set:
    """Accounts a worker is busy with right now."""
    ids = set(s.exec(select(BotRun.account_id).where(BotRun.status.in_(ACTIVE_STATUSES), BotRun.kind != "sync",
                                                     BotRun.account_id.is_not(None))).all())
    ids |= set(s.exec(select(Account.id).where(Account.status == "signing_up")).all())
    return ids


def _account_public(a: Account, full=False, working: Optional[set] = None) -> dict:
    exclude = {"access_token", "refresh_token"} | (set() if full else {"liked", "disliked", "matches", "messaged"})
    d = a.model_dump(exclude=exclude)
    d["created_at"], d["updated_at"] = _iso(a.created_at), _iso(a.updated_at)
    d["last_activity_at"] = _iso(a.last_activity_at or a.updated_at or a.created_at)
    d["stats_synced_at"] = _iso(a.stats_synced_at)
    d["has_token"] = bool(a.refresh_token or a.access_token)
    d["pending_messages"] = len(set(map(str, a.matches or [])) - set(map(str, a.messaged or [])))
    d["actions"] = (a.liked_count or 0) + (a.disliked_count or 0) + (a.messages_sent or 0)
    is_working = working is not None and a.id in working
    d["working"] = is_working
    d["state"] = "working" if is_working else next((k for k, v in STATE_STATUSES.items() if a.status in v), "working")
    return d


def _account_query(q, status, location, date_from, date_to, search, state=None, worker=None, working=None):
    if state == "working":
        q = q.where(Account.id.in_(working or {-1}))
    elif state in STATE_STATUSES:
        q = q.where(Account.status.in_(STATE_STATUSES[state]))
        if working:
            q = q.where(Account.id.not_in(working))
    if worker:
        q = q.where(Account.worker == worker)
    if status:
        q = q.where(Account.status.in_(status.split(",")))
    if location:
        q = q.where(Account.location == location)
    if date_from:
        q = q.where(Account.created_at >= _local_midnight(date_from))
    if date_to:
        q = q.where(Account.created_at < _local_midnight(date_to + timedelta(days=1)))
    if search:
        search = search.strip().lstrip("#@")
        like = f"%{search}%"
        conds = [Account.name.ilike(like), Account.android_id.ilike(like), Account.notes.ilike(like),
                 Account.jaumo_id.ilike(like), Account.location.ilike(like)]
        if search.isdigit():
            conds.append(Account.id == int(search))
        m = search.lower().replace("worker", "").strip(" -_")
        if m.isdigit() and "worker" in search.lower():
            conds.append(Account.worker == int(m))
        q = q.where(or_(*conds))
    return q


@app.get("/api/accounts", dependencies=auth)
def list_accounts(status: Optional[str] = None, location: Optional[str] = None,
                  date_from: Optional[date] = None, date_to: Optional[date] = None,
                  q: Optional[str] = None, state: Optional[str] = None, worker: Optional[int] = None,
                  sort: str = "id", order: str = "desc",
                  limit: int = Query(100, le=1000), offset: int = 0, s: Session = Depends(get_session)):
    col = getattr(Account, sort if sort in ACCOUNT_SORTS else "id")
    working = _working_ids(s)
    args = (status, location, date_from, date_to, q, state, worker, working)
    base = _account_query(select(Account), *args)
    total = s.exec(_account_query(select(func.count()).select_from(Account), *args)).one()
    ordering = [col.asc() if order == "asc" else col.desc(), Account.id.desc()]
    term = (q or "").strip().lstrip("#@")
    if term:
        # exact hits (ID, Jaumo ID, name) first, then the partial matches
        exact = or_(Account.jaumo_id == term, func.lower(Account.name) == term.lower(),
                    *([Account.id == int(term)] if term.isdigit() else []))
        ordering.insert(0, case((exact, 0), else_=1))
    rows = s.exec(base.order_by(*ordering).offset(offset).limit(limit)).all()
    return {"total": total, "items": [_account_public(a, working=working) for a in rows]}


@app.get("/api/accounts/summary", dependencies=auth)
def accounts_summary(tz_offset: int = 0, s: Session = Depends(get_session)):
    """Header cards of the accounts page: totals plus what happened today (browser-local day)."""
    offset = timedelta(minutes=-tz_offset)
    today = datetime.combine((utcnow() + offset).date(), dtime.min, tzinfo=timezone.utc) - offset
    tot = s.exec(select(func.count(), func.coalesce(func.sum(Account.liked_count), 0),
                        func.coalesce(func.sum(Account.disliked_count), 0),
                        func.coalesce(func.sum(Account.matches_count), 0),
                        func.coalesce(func.sum(Account.messages_sent), 0),
                        func.coalesce(func.sum(Account.messages_received), 0),
                        func.count(Account.messages_received),
                        func.coalesce(func.sum(Account.profile_visits), 0),
                        func.coalesce(func.sum(Account.likes_received), 0),
                        func.count(Account.stats_synced_at),
                        func.max(Account.stats_synced_at))).one()
    today_events = dict(s.exec(select(AccountEvent.kind, func.count()).where(AccountEvent.ts >= today)
                               .group_by(AccountEvent.kind)).all())
    created_today = s.exec(select(func.count()).select_from(Account).where(Account.created_at >= today)).one()
    working = _working_ids(s)
    workers = sorted(w for w in s.exec(select(Account.worker).distinct()).all() if w)
    likes_today = today_events.get("like", 0) + today_events.get("match", 0)
    return {
        "accounts": tot[0], "accounts_today": created_today,
        "likes": tot[1], "likes_today": likes_today,
        "dislikes": tot[2], "dislikes_today": today_events.get("dislike", 0),
        "matches": tot[3], "matches_today": today_events.get("match", 0),
        "messages_sent": tot[4], "messages_sent_today": today_events.get("message", 0),
        "messages_received": tot[5], "messages_received_synced": tot[6],
        "profile_visits": tot[7],
        # client definitions: received (from stats sync) vs sent (by the bot)
        "likes_sent": tot[1], "likes_sent_today": likes_today,
        "likes_received": tot[8], "visits_received": tot[7],
        "stats_synced_accounts": tot[9], "stats_last_synced_at": _iso(tot[10]),
        "actions": tot[1] + tot[2] + tot[4],
        "actions_today": likes_today + today_events.get("dislike", 0) + today_events.get("message", 0),
        "working": len(working),
        "workers": sorted(set(workers) | set(range(1, manager.parallel + 1))),
        "parallel": manager.parallel,
    }


@app.get("/api/accounts/locations", dependencies=auth)
def account_locations(s: Session = Depends(get_session)):
    return sorted(l for l in s.exec(select(Account.location).distinct()).all() if l)


@app.get("/api/accounts/export", dependencies=auth)
def export_accounts(status: Optional[str] = None, location: Optional[str] = None,
                    date_from: Optional[date] = None, date_to: Optional[date] = None,
                    q: Optional[str] = None, state: Optional[str] = None, worker: Optional[int] = None,
                    s: Session = Depends(get_session)):
    working = _working_ids(s)
    rows = s.exec(_account_query(select(Account), status, location, date_from, date_to, q, state, worker, working)
                  .order_by(Account.id)).all()
    buf = io.StringIO()
    for a in rows:
        d = a.model_dump()
        buf.write(json.dumps(d, ensure_ascii=False,
                             default=lambda o: _iso(o) if isinstance(o, datetime) else str(o)) + "\n")
    name = f"accounts_{datetime.now():%Y%m%d_%H%M}.jsonl"
    return StreamingResponse(iter([buf.getvalue()]), media_type="application/x-ndjson",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/accounts/{id_}", dependencies=auth)
def get_account(id_: int, s: Session = Depends(get_session)):
    return _account_public(_get_or_404(s, Account, id_), full=True, working=_working_ids(s))


@app.post("/api/accounts/sync", dependencies=auth)
def sync_accounts(body: StatsSyncIn):
    """Read-only stats refresh for the selected accounts or all accounts (one after another, with a delay)."""
    if not body.all and not body.account_ids:
        raise HTTPException(422, "choose accounts or all=true")
    return manager.launch_sync(body.account_ids, all_accounts=body.all)


@app.post("/api/accounts/{id_}/sync", dependencies=auth)
def sync_account(id_: int, s: Session = Depends(get_session)):
    _get_or_404(s, Account, id_)
    res = manager.launch_sync([id_])
    if not res["run_ids"]:
        raise HTTPException(409, res["skipped"][0]["reason"] if res["skipped"] else "could not start refresh")
    return res


@app.post("/api/accounts/swipe", dependencies=auth)
def swipe_accounts(body: SwipeIn):
    """Continue swiping with existing accounts (after a stop). Returns started runs and skipped accounts."""
    try:
        return manager.launch_swipe(body.account_ids)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/api/accounts/{id_}/swipe", dependencies=auth)
def swipe_account(id_: int, s: Session = Depends(get_session)):
    _get_or_404(s, Account, id_)
    try:
        res = manager.launch_swipe([id_])
    except ValueError as e:
        raise HTTPException(422, str(e))
    if not res["run_ids"]:
        raise HTTPException(409, res["skipped"][0]["reason"] if res["skipped"] else "could not start")
    return res


@app.get("/api/accounts/{id_}/runs", dependencies=auth)
def account_runs(id_: int, s: Session = Depends(get_session)):
    rows = s.exec(select(BotRun).where(BotRun.account_id == id_).order_by(BotRun.id.desc())).all()
    return [run_public(r) for r in rows]


@app.get("/api/accounts/{id_}/events", dependencies=auth)
def account_events(id_: int, before_id: Optional[int] = None, limit: int = Query(100, le=1000),
                   s: Session = Depends(get_session)):
    q = select(AccountEvent).where(AccountEvent.account_id == id_)
    if before_id:
        q = q.where(AccountEvent.id < before_id)
    return [event_public(e) for e in s.exec(q.order_by(AccountEvent.id.desc()).limit(limit)).all()]


@app.patch("/api/accounts/{id_}", dependencies=auth)
def patch_account(id_: int, body: AccountPatch, s: Session = Depends(get_session)):
    a = _get_or_404(s, Account, id_)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(a, k, v)
    a.updated_at = utcnow()
    s.add(a)
    s.commit()
    s.refresh(a)
    return _account_public(a, full=True)


@app.delete("/api/accounts/{id_}", dependencies=auth)
def delete_account(id_: int, s: Session = Depends(get_session)):
    a = _get_or_404(s, Account, id_)
    if s.exec(select(BotRun).where(BotRun.account_id == id_, BotRun.status.in_(ACTIVE_STATUSES))).first():
        raise HTTPException(409, "account has an active run")
    s.exec(sa_delete(AccountEvent).where(AccountEvent.account_id == id_))
    s.delete(a)
    s.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# WebSockets
# ---------------------------------------------------------------------------

async def _pump(ws: WebSocket, channel: str):
    if not ws_authenticated(ws):
        await ws.close(code=4401)
        return
    q = hub.subscribe(channel)   # before accept: nothing published after the client sees 'open' is missed
    try:
        await ws.accept()
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=25)
            except asyncio.TimeoutError:
                msg = {"type": "ping"}
            await ws.send_json(msg)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        hub.unsubscribe(channel, q)


@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    await _pump(ws, "events")


@app.websocket("/ws/accounts/{account_id}")
async def ws_account(ws: WebSocket, account_id: int):
    await _pump(ws, f"account:{account_id}")


@app.websocket("/ws/runs/{run_id}")
async def ws_run(ws: WebSocket, run_id: int):
    await _pump(ws, f"run:{run_id}")


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"ok": True, "active": manager.active_count()}


app.mount("/static", StaticFiles(directory=cfg.FRONTEND_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(cfg.FRONTEND_DIR / "index.html", headers={"Cache-Control": "no-cache"})
