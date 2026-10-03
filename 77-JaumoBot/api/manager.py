"""
Runs bots in a global thread pool, persists their events and fans them out
to WebSocket subscribers.

Requires a single uvicorn worker: run state, the proxy pool and WebSocket
subscribers live in this process's memory.
"""

import asyncio
import os
import time
import random
import sys
import threading
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import update as sa_update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import Session, select

from bot.engine import (AUTO_FEMALE_NAMES, BotRunner, MessageRunner, RenameRunner, StatsSyncRunner, StopRequested,
                        SwipeRunner)

from .models import (Account, AccountEvent, ApkProfile, AppSetting, BotConfig, BotRun, Photo, Proxy, RunLog,
                     engine, iso, utcnow)
from .photolib import pick_photos
from .proxies import NoProxyAvailable, ProxyPool, proxy_display, proxy_url
from .settings import PHOTOS_DIR

ACTIVE_STATUSES = ("queued", "running")


IDENTITY_DEFAULTS = {"unique_names": True, "unique_photos": True}
BOT_DEFAULTS = {"parallel_accounts": 1, "sync_delay_seconds": 10, "sync_after_session": True,
                "stats_every_swipes": 200, "auto_sync_minutes": 30}
AUTO_SYNC_TICK = float(os.environ.get("AUTO_SYNC_TICK_SECONDS", "30"))          # how often the timer checks
AUTO_SYNC_INTERVAL = float(os.environ.get("AUTO_SYNC_INTERVAL_SECONDS", "0"))   # tests only: overrides the minutes
SYNC_COOLDOWN_SECONDS = 15   # one refresh per account at a time, then wait at least this long
THREAD_CAP = 64
# Mirror bot log lines (info/warning/error, never HTTP bodies) to stdout -> Coolify runtime log.
LOG_TO_STDOUT = os.environ.get("LOG_BOT_TO_STDOUT", "1") != "0"  # internal worker threads; the admin's parallel setting is the real limit


def get_bot_settings(s: Session) -> dict:
    row = s.get(AppSetting, "bot")
    return {**BOT_DEFAULTS, **(row.value if row else {})}


def get_identity(s: Session) -> dict:
    """Global identity rules — apply to every configuration and every launch."""
    row = s.get(AppSetting, "identity")
    return {**IDENTITY_DEFAULTS, **(row.value if row else {})}


def event_public(e: AccountEvent) -> dict:
    return {"id": e.id, "run_id": e.run_id, "ts": iso(e.ts), "kind": e.kind, "user_id": e.user_id, "detail": e.detail}


def _key(name: str) -> str:
    return name.strip().casefold()


def name_usage(s: Session) -> Counter:
    """
    How often each name is taken: every account's name, plus names reserved by
    queued/running signup runs that have not created their account yet.
    """
    usage = Counter()
    for name, history in s.exec(select(Account.name, Account.name_history)).all():
        usage.update(_key(n) for n in [name, *(history or [])] if n)   # current + every earlier nickname
    reserved = s.exec(select(BotRun.requested_name).where(
        BotRun.kind == "signup", BotRun.status.in_(ACTIVE_STATUSES),
        BotRun.account_id.is_(None), BotRun.requested_name.is_not(None))).all()
    usage.update(_key(n) for n in reserved)
    return usage


def rename_usage(s: Session, base: Counter = None) -> Counter:
    """Names taken for a nickname change: every name an account has or had + names reserved by queued changes."""
    usage = Counter(base) if base is not None else name_usage(s)
    reserved = s.exec(select(BotRun.rename_to).where(BotRun.status.in_(ACTIVE_STATUSES),
                                                     BotRun.rename_to.is_not(None))).all()
    usage.update(_key(n) for n in reserved)
    return usage


def rename_pool_for(settings: dict) -> list[str]:
    seen, out = set(), []
    for n in settings.get("rename_pool") or []:
        if n.strip() and _key(n) not in seen:
            seen.add(_key(n))
            out.append(n.strip())
    return out


def pick_rename(usage: Counter, settings: dict, count: int, force: bool = False) -> list:
    """New nicknames from the "Nicknamen ändern" list (least used first); [None] * count when switched off."""
    if not force and not settings.get("rename_after_signup"):
        return [None] * count
    pool = rename_pool_for(settings)
    if not pool:
        raise ValueError("The list of new nicknames is empty — add names on the Nicknamen ändern page")
    unique = settings.get("rename_unique", True)
    picked = []
    for _ in range(count):
        low = min(usage[_key(n)] for n in pool)
        if unique and low > 0:
            raise ValueError(f"Not enough unused new nicknames: only {len(picked)} of {count} could be assigned. "
                             "Add names on the Nicknamen ändern page or allow reuse there.")
        name = random.choice([n for n in pool if usage[_key(n)] == low])
        picked.append(name)
        usage[_key(name)] += 1
    return picked


def about_usage(s: Session) -> Counter:
    """How often each profile text is taken: accounts that have it, plus texts reserved by active signups."""
    usage = Counter(_key(t) for t in s.exec(select(Account.about_me)).all() if t)
    reserved = s.exec(select(BotRun.about_text).where(
        BotRun.kind == "signup", BotRun.status.in_(ACTIVE_STATUSES), BotRun.about_text.is_not(None))).all()
    usage.update(_key(t) for t in reserved)
    return usage


def about_pool_for(settings: dict) -> list[str]:
    seen, out = set(), []
    for t in settings.get("about_pool") or []:
        if t.strip() and _key(t) not in seen:
            seen.add(_key(t))
            out.append(t.strip())
    return out


def pick_about(usage: Counter, settings: dict, count: int) -> list:
    """Least-used profile texts; [None] * count when profile texts are off."""
    if not settings.get("about_enabled"):
        return [None] * count
    pool = about_pool_for(settings)
    if not pool:
        raise ValueError("The profile text list is empty — add texts or turn profile texts off")
    unique = settings.get("about_unique", True)
    picked = []
    for _ in range(count):
        low = min(usage[_key(t)] for t in pool)
        if unique and low > 0:
            raise ValueError(f"Not enough unused profile texts: only {len(picked)} of {count} could be assigned. "
                             "Add texts or allow text reuse (Profiltexte page).")
        text = random.choice([t for t in pool if usage[_key(t)] == low])
        picked.append(text)
        usage[_key(text)] += 1
    return picked


def name_pool_for(settings: dict) -> list[str]:
    if settings.get("name_source", "auto") == "auto":
        pool = AUTO_FEMALE_NAMES
    else:
        pool = settings.get("name_pool") or []
    seen, out = set(), []
    for n in pool:
        if n.strip() and _key(n) not in seen:
            seen.add(_key(n))
            out.append(n.strip())
    return out


def pick_names(usage: Counter, settings: dict, count: int, manual: list[str], unique: bool = True) -> list[str]:
    """Typed names first (in order), then least-used names from the pool."""
    manual = manual[:count]
    if unique:
        taken = [n for n in manual if usage[_key(n)]]
        repeated = [n for n, c in Counter(_key(n) for n in manual).items() if c > 1]
        if taken or repeated:
            parts = []
            if taken:
                parts.append("already used: " + ", ".join(taken))
            if repeated:
                parts.append("typed more than once: " + ", ".join(repeated))
            raise ValueError("Names must be unique (Settings) — " + "; ".join(parts))
    names = []
    for n in manual:
        names.append(n)
        usage[_key(n)] += 1
    pool = name_pool_for(settings)
    for _ in range(count - len(names)):
        if not pool:
            raise ValueError("The name list is empty — add names or switch names to auto")
        low = min(usage[_key(n)] for n in pool)
        if unique and low > 0:
            raise ValueError(
                f"Not enough unused names: only {len(names)} of {count} could be assigned. "
                "Add names to the list, switch to auto names, or allow name reuse in Settings.")
        name = random.choice([n for n in pool if usage[_key(n)] == low])
        names.append(name)
        usage[_key(name)] += 1
    return names


def get_main_config(s: Session):
    """The one Jaumo configuration the panel works with (stored in AppSetting 'main_config_id').
    On a server that still has several, the one used for the latest signup wins, else the oldest."""
    row = s.get(AppSetting, "main_config_id")
    cid = (row.value or {}).get("id") if row and isinstance(row.value, dict) else None
    config = s.get(BotConfig, cid) if cid else None
    if config:
        return config
    last = s.exec(select(BotRun.config_id).where(BotRun.kind == "signup", BotRun.config_id != None)  # noqa: E711
                  .order_by(BotRun.id.desc())).first()
    config = (s.get(BotConfig, last) if last else None) or s.exec(select(BotConfig).order_by(BotConfig.id)).first()
    if config:
        row = row or AppSetting(key="main_config_id")
        row.value = {"id": config.id}
        s.add(row)
        s.commit()
        s.refresh(config)
    return config


def _resolve_config(s: Session, config_id):
    config = s.get(BotConfig, config_id) if config_id else get_main_config(s)
    if not config:
        raise LookupError("config not found")
    return config


def run_public(run: BotRun) -> dict:
    d = run.model_dump(exclude={"config_snapshot"})
    for k in ("created_at", "started_at", "finished_at"):
        if d.get(k):
            d[k] = iso(d[k])
    return d


class Hub:
    """Thread-safe pub/sub into asyncio queues owned by WebSocket handlers."""

    def __init__(self):
        self.loop: asyncio.AbstractEventLoop | None = None
        self.subs: dict[str, set[asyncio.Queue]] = {}

    def subscribe(self, channel: str) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=2000)
        self.subs.setdefault(channel, set()).add(q)
        return q

    def unsubscribe(self, channel: str, q: asyncio.Queue):
        subs = self.subs.get(channel)
        if subs:
            subs.discard(q)
            if not subs:
                self.subs.pop(channel, None)

    def _deliver(self, channel, msg):
        for q in list(self.subs.get(channel, ())):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass  # slow client — drop

    def publish(self, channel: str, msg: dict):
        if self.loop and channel in self.subs:
            self.loop.call_soon_threadsafe(self._deliver, channel, msg)


class RunManager:
    """
    One bot with a FIFO queue of account sessions (signup runs and messaging runs).
    `parallel` (admin setting) is how many accounts it works on at the same time.
    """

    def __init__(self, hub: Hub):
        self.hub = hub
        self.parallel = BOT_DEFAULTS["parallel_accounts"]
        self.executor = ThreadPoolExecutor(max_workers=THREAD_CAP, thread_name_prefix="bot")
        # Stats syncs run on their own single thread: one account at a time, never taking a worker
        # away from account creation.
        self.sync_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sync")
        self.labels: dict[int, str] = {}     # run id -> "session 12 · Worker-01 · Sabrina" for stdout lines
        self.closing = False
        self.auto_sync_stop = threading.Event()
        self.gate = threading.Condition()
        self.waiting: deque[int] = deque()   # run ids in launch order
        self.working = 0
        self.slots: dict[int, int] = {}      # worker slot -> run id
        self.pool = ProxyPool()
        self.stop_events: dict[int, threading.Event] = {}
        self.lock = threading.Lock()
        self.name_lock = threading.Lock()  # name pick + reserve must be atomic across launches

    # --- startup / shutdown -----------------------------------------------

    def mark_interrupted(self):
        with Session(engine) as s:
            for run in s.exec(select(BotRun).where(BotRun.status.in_(ACTIVE_STATUSES))).all():
                run.status = "interrupted"
                run.reason = "server restarted while run was active"
                run.finished_at = run.finished_at or utcnow()
                s.add(run)
                if run.account_id:
                    acc = s.get(Account, run.account_id)
                    if acc and acc.status in ("signing_up",):
                        acc.status = "failed"
                        s.add(acc)
            s.commit()

    def set_parallel(self, n: int):
        with self.gate:
            self.parallel = max(1, int(n))
            self.gate.notify_all()

    def _wait_turn(self, run_id: int, ev: threading.Event) -> bool:
        """Block until it is this run's turn (FIFO) and a parallel slot is free."""
        with self.gate:
            while True:
                if ev.is_set():
                    return False
                if self.working < self.parallel and self.waiting and self.waiting[0] == run_id:
                    self.waiting.popleft()
                    self.working += 1
                    slot = next(i for i in range(1, len(self.slots) + 2) if i not in self.slots)
                    self.slots[slot] = run_id
                    return True
                self.gate.wait(1)

    def _leave(self, run_id: int, had_slot: bool):
        with self.gate:
            try:
                self.waiting.remove(run_id)
            except ValueError:
                pass
            if had_slot:
                self.working -= 1
                for k in [k for k, v in self.slots.items() if v == run_id]:
                    del self.slots[k]
            self.gate.notify_all()

    def shutdown(self):
        self.closing = True
        self.auto_sync_stop.set()
        for ev in list(self.stop_events.values()):
            ev.set()
        self.pool.notify()
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.sync_executor.shutdown(wait=False, cancel_futures=True)

    # --- launching ---------------------------------------------------------

    def _snapshot(self, s: Session, config: BotConfig) -> dict:
        apk = s.get(ApkProfile, config.apk_profile_id) if config.apk_profile_id else None
        if not apk:
            raise ValueError("config has no APK profile — set one before launching")
        if not apk.enabled:
            raise ValueError(f"APK profile '{apk.name}' is disabled — switch the config to another APK profile")
        return {
            "settings": dict(config.settings),
            "apk": apk.credentials(),
            "apk_profile_id": apk.id,
            "apk_profile_name": apk.name,
        }

    def _submit(self, run_id: int, fn):
        ev = threading.Event()
        with self.lock:
            self.stop_events[run_id] = ev
        with self.gate:
            self.waiting.append(run_id)
        self.executor.submit(self._guard, run_id, fn, ev)

    def check_signup(self, config_id, count: int, names: list[str]) -> list[dict]:
        """Dry run of launch_signup: every reason it would be refused, each with the page that fixes it."""
        names = [n.strip() for n in names if n and n.strip()]
        problems = []
        with Session(engine) as s:
            config = _resolve_config(s, config_id)
            settings = dict(config.settings)
            rules = get_identity(s)
            checks = (("apk", "configs", lambda: self._snapshot(s, config)),
                      ("photos", "photos", lambda: pick_photos(s, settings, count, rules["unique_photos"])),
                      ("names", "names", lambda: pick_names(name_usage(s), settings, count, names,
                                                                rules["unique_names"])),
                      ("about", "about", lambda: pick_about(about_usage(s), settings, count)),
                      ("rename", "rename", lambda: pick_rename(rename_usage(s), settings, count)))
            for code, page, fn in checks:
                try:
                    fn()
                except ValueError as e:
                    problems.append({"code": code, "page": page, "message": str(e)})
            if settings.get("require_proxy", True) and not s.exec(
                    select(Proxy.id).where(Proxy.enabled == True)).first():  # noqa: E712
                problems.append({"code": "proxy", "page": "proxies",
                                 "message": "No enabled proxy — the configuration requires one (Proxies page)"})
        return problems

    def launch_signup(self, config_id, count: int, names: list[str]) -> list[int]:
        names = [n.strip() for n in names if n and n.strip()]
        with self.name_lock, Session(engine) as s:
            config = _resolve_config(s, config_id)
            snap = self._snapshot(s, config)
            rules = get_identity(s)
            usage = name_usage(s)
            assigned = pick_names(usage, snap["settings"], count, names, rules["unique_names"])
            renames = pick_rename(rename_usage(s, usage), snap["settings"], count)
            photos = pick_photos(s, snap["settings"], count, rules["unique_photos"])
            abouts = pick_about(about_usage(s), snap["settings"], count)
            runs = []
            for name, photo, about, rename in zip(assigned, photos, abouts, renames):
                run = BotRun(kind="signup", config_id=config.id, config_name=config.name, config_snapshot=snap,
                             requested_name=name, photo=photo, about_text=about, rename_to=rename)
                s.add(run)
                runs.append(run)
            s.commit()
            ids = [r.id for r in runs]
            payloads = [run_public(r) for r in runs]
        for rid, p in zip(ids, payloads):
            self.hub.publish("events", {"type": "run", "run": p})
            self._submit(rid, self._signup_worker)
        return ids

    def launch_messages(self, config_id, account_ids: list[int]) -> list[int]:
        with Session(engine) as s:
            config = _resolve_config(s, config_id)
            if not (config.settings or {}).get("messaging_enabled", False):
                raise ValueError(f"Messaging is turned off in configuration '{config.name}' — "
                                 "enable it under Configurations → Messaging")
            snap = self._snapshot(s, config)
            q = select(Account).where(Account.status.in_(("active", "legacy")))
            if account_ids:
                q = select(Account).where(Account.id.in_(account_ids))
            accounts = s.exec(q).all()
            busy = set(s.exec(select(BotRun.account_id).where(BotRun.status.in_(ACTIVE_STATUSES),
                                                              BotRun.kind != "sync")).all())
            runs = []
            for acc in accounts:
                if acc.id in busy or not (acc.refresh_token or acc.access_token):
                    continue
                pending = set(map(str, acc.matches or [])) - set(map(str, acc.messaged or []))
                if not pending:
                    continue
                run = BotRun(kind="message", config_id=config.id, config_name=config.name,
                             config_snapshot=snap, account_id=acc.id, requested_name=acc.name)
                s.add(run)
                runs.append(run)
            s.commit()
            ids = [r.id for r in runs]
            payloads = [run_public(r) for r in runs]
        self._cancel_syncs([p["account_id"] for p in payloads])
        for rid, p in zip(ids, payloads):
            self.hub.publish("events", {"type": "run", "run": p})
            self._submit(rid, self._message_worker)
        return ids

    SWIPE_STATUSES = ("active", "legacy", "stopped")   # set up accounts (stopped = stopped by admin)

    def launch_swipe(self, account_ids: list[int]) -> dict:
        """Continue swiping with existing accounts (same worker queue as account creation)."""
        with Session(engine) as s:
            config = get_main_config(s)
            if not config:
                raise LookupError("config not found")
            snap = self._snapshot(s, config)
            accounts = s.exec(select(Account).where(Account.id.in_(account_ids)).order_by(Account.id)).all()
            busy = set(s.exec(select(BotRun.account_id).where(BotRun.status.in_(ACTIVE_STATUSES),
                                                              BotRun.kind != "sync")).all())
            runs, skipped = [], []
            for acc in accounts:
                reason = ("already working" if acc.id in busy
                          else "blocked by Jaumo" if acc.status == "blocked"
                          else "account was never fully set up (no photo)" if acc.status not in self.SWIPE_STATUSES
                          else "no login token stored" if not (acc.refresh_token or acc.access_token) else "")
                if reason:
                    skipped.append({"id": acc.id, "name": acc.name, "reason": reason})
                    continue
                run = BotRun(kind="swipe", config_id=config.id, config_name=config.name,
                             config_snapshot=snap, account_id=acc.id, requested_name=acc.name)
                s.add(run)
                runs.append(run)
            s.commit()
            ids = [r.id for r in runs]
            payloads = [run_public(r) for r in runs]
        self._cancel_syncs([p["account_id"] for p in payloads])
        for rid, p in zip(ids, payloads):
            self.hub.publish("events", {"type": "run", "run": p})
            self._submit(rid, self._swipe_worker)
        return {"run_ids": ids, "skipped": skipped}

    def _swipe_worker(self, run_id: int, ev: threading.Event):
        with Session(engine) as s:
            account_id = s.get(BotRun, run_id).account_id
        try:
            self._wait_for_sync(run_id, account_id, ev)
        except StopRequested:
            return self._finish(run_id, {"status": "stopped", "reason": "stopped by admin"})
        with Session(engine) as s:
            run = s.get(BotRun, run_id)
            snap = run.config_snapshot
            acc = s.get(Account, run.account_id)
            if not acc:
                return self._finish(run_id, {"status": "failed", "reason": "account not found"})
            account = acc.model_dump()
        settings = self._session_settings(snap["settings"])

        try:
            proxy = self._acquire_proxy(run_id, ev, settings)
        except StopRequested:
            return self._finish(run_id, {"status": "stopped", "reason": "stopped while waiting for proxy"})
        except NoProxyAvailable as e:
            self._log(run_id, "error", f"[PROXY] {e}")
            return self._finish(run_id, {"status": "failed", "reason": str(e)})

        def emit(kind, data):
            if kind == "log":
                self._log(run_id, data.get("level", "info"), data.get("msg", ""))
            elif kind == "step":
                self._update_run(run_id, step=data["step"])
            elif kind == "account_update":
                self._update_account(account["id"], data, run_id)
            elif kind == "swipe":
                self._on_swipe(run_id, account["id"], data)
            elif kind == "stats":
                self._on_stats(run_id, account["id"], data)
            elif kind == "verification":
                self._on_verification(run_id, account["id"], data)

        try:
            runner = SwipeRunner(settings, snap["apk"], account,
                                 proxy_url=proxy_url(proxy) if proxy else None,
                                 emit=emit, stop_event=ev)
            result = runner.run()
        finally:
            self.pool.release(proxy.id if proxy else None)
        self._finish(run_id, result)

    def stop(self, run_id: int) -> bool:
        with self.lock:
            ev = self.stop_events.get(run_id)
        if ev:
            ev.set()
            self.pool.notify()
            with self.gate:
                self.gate.notify_all()
            return True
        return False

    def stop_all(self) -> int:
        with self.lock:
            events = list(self.stop_events.values())
        for ev in events:
            ev.set()
        self.pool.notify()
        with self.gate:
            self.gate.notify_all()
        return len(events)

    def active_count(self) -> int:
        with self.lock:
            return len(self.stop_events)

    # --- run state helpers -------------------------------------------------

    def _update_run(self, run_id: int, **fields) -> dict:
        with Session(engine) as s:
            run = s.get(BotRun, run_id)
            for k, v in fields.items():
                setattr(run, k, v)
            s.add(run)
            s.commit()
            s.refresh(run)
            payload = run_public(run)
        parts = [f"session {run_id}", {"message": "messaging", "sync": "stats refresh"}.get(payload["kind"], "")]
        if payload.get("worker"):
            parts.append(f"Worker-{payload['worker']:02d}")
        if payload.get("requested_name"):
            parts.append(payload["requested_name"])
        self.labels[run_id] = " · ".join(p for p in parts if p)
        self.hub.publish("events", {"type": "run", "run": payload})
        self.hub.publish(f"run:{run_id}", {"type": "run", "run": payload})
        return payload

    def _log(self, run_id: int, level: str, msg: str):
        with Session(engine) as s:
            entry = RunLog(run_id=run_id, level=level, msg=msg)
            s.add(entry)
            s.commit()
            s.refresh(entry)
            data = {"type": "log", "id": entry.id, "ts": iso(entry.ts), "level": level, "msg": msg}
        self.hub.publish(f"run:{run_id}", data)
        if LOG_TO_STDOUT and level != "debug":
            first = msg.strip().splitlines()[0] if msg.strip() else ""
            extra = msg.count("\n")
            print(f"[{self.labels.get(run_id, f'session {run_id}')}] {level.upper():7} {first}"
                  + (f"  (+{extra} lines)" if extra else ""), file=sys.stdout, flush=True)

    def _guard(self, run_id: int, fn, ev: threading.Event):
        had_slot = False
        try:
            with Session(engine) as s:
                run = s.get(BotRun, run_id)
                if not run or run.status != "queued":
                    return
            had_slot = self._wait_turn(run_id, ev)
            if not had_slot:
                self._update_run(run_id, status="stopped", reason="stopped before start", finished_at=utcnow())
                return
            with self.gate:
                worker = next((k for k, v in self.slots.items() if v == run_id), None)
            self._update_run(run_id, status="running", started_at=utcnow(), step="starting", worker=worker)
            fn(run_id, ev)
        except Exception as e:  # last-resort guard: never leave a run "running"
            self._log(run_id, "error", f"[MANAGER] {type(e).__name__}: {e}")
            self._update_run(run_id, status="failed", reason=f"{type(e).__name__}: {e}", finished_at=utcnow())
        finally:
            self._leave(run_id, had_slot)
            with self.lock:
                self.stop_events.pop(run_id, None)
            self.labels.pop(run_id, None)

    def _acquire_proxy(self, run_id, ev, settings):
        def on_wait():
            self._update_run(run_id, step="waiting_proxy")
            self._log(run_id, "warning", "[PROXY] All dedicated proxies busy — waiting for a free one")

        proxy = self.pool.acquire(ev, require=settings.get("require_proxy", True), on_wait=on_wait)
        if proxy:
            self._update_run(run_id, proxy_id=proxy.id, proxy_label=proxy_display(proxy))
        return proxy

    def _finish(self, run_id, result):
        self._update_run(run_id, status=result["status"], reason=result.get("reason", ""),
                         finished_at=utcnow())
        if LOG_TO_STDOUT:
            print(f"[{self.labels.get(run_id, f'session {run_id}')}] RESULT  {result['status']}: {result.get('reason', '')}",
                  file=sys.stdout, flush=True)
        self.labels.pop(run_id, None)

    # --- signup worker -----------------------------------------------------

    def _signup_worker(self, run_id: int, ev: threading.Event):
        with Session(engine) as s:
            run = s.get(BotRun, run_id)
            snap = run.config_snapshot
            config_id = run.config_id
            name = run.requested_name
            photo_name = run.photo
            about = run.about_text
            rename_to = run.rename_to
            worker = run.worker
        settings = self._session_settings(snap["settings"])

        photo = PHOTOS_DIR / photo_name if photo_name else None
        if not photo or not photo.is_file():
            self._log(run_id, "error", f"[PHOTO] Reserved photo is missing: {photo_name}")
            return self._finish(run_id, {"status": "failed", "reason": "reserved photo missing from library"})

        try:
            proxy = self._acquire_proxy(run_id, ev, settings)
        except StopRequested:
            return self._finish(run_id, {"status": "stopped", "reason": "stopped while waiting for proxy"})
        except NoProxyAvailable as e:
            self._log(run_id, "error", f"[PROXY] {e}")
            return self._finish(run_id, {"status": "failed", "reason": str(e)})

        ctx = {"account_id": None, "proxy_id": proxy.id if proxy else None, "config_id": config_id,
               "apk_profile_id": snap.get("apk_profile_id"), "worker": worker}
        try:
            runner = BotRunner(
                settings, snap["apk"], str(photo),
                proxy_url=proxy_url(proxy) if proxy else None, name=name,
                emit=lambda kind, data: self._on_signup_event(run_id, ctx, kind, data),
                stop_event=ev, about=about, rename_to=rename_to,
            )
            result = runner.run()
        finally:
            self.pool.release(proxy.id if proxy else None)
        self._finish(run_id, result)

    def _on_signup_event(self, run_id, ctx, kind, data):
        if kind == "log":
            self._log(run_id, data.get("level", "info"), data.get("msg", ""))
        elif kind == "step":
            self._update_run(run_id, step=data["step"])
        elif kind == "account_created":
            a = data["account"]
            with Session(engine) as s:
                acc = Account(
                    run_id=run_id, config_id=ctx["config_id"], proxy_id=ctx["proxy_id"], worker=ctx["worker"],
                    last_activity_at=utcnow(),
                    name=a["name"], gender=a["gender"], birthday=a["birthday"],
                    looking_for_gender=a["looking_for_gender"], location=a["location"],
                    latitude=a.get("latitude"), longitude=a.get("longitude"),
                    relationship_search=a.get("relationship_search"),
                    dating_relationship_search=a.get("dating_relationship_search"),
                    photo=a.get("photo"), photo_url=a.get("photo_url"), status=a.get("status", "signing_up"),
                    android_id=a["android_id"], device_id=a["device_id"], device_info=a.get("device_info"),
                    access_token=a["access_token"] or "", refresh_token=a["refresh_token"] or "",
                )
                s.add(acc)
                s.commit()
                ctx["account_id"] = acc.id
            self._update_run(run_id, account_id=ctx["account_id"], requested_name=a["name"])
            self._account_event(ctx["account_id"], run_id, "created",
                                detail=f"Signed up as {a['name']} · {a['location']} · photo {a.get('photo')}")
            self.hub.publish("events", {"type": "account", "account_id": ctx["account_id"]})
        elif kind == "account_update":
            self._update_account(ctx.get("account_id"), data, run_id)
        elif kind == "swipe":
            self._on_swipe(run_id, ctx.get("account_id"), data)
        elif kind == "stats":
            self._on_stats(run_id, ctx.get("account_id"), data)
        elif kind == "renamed":
            self._on_renamed(run_id, ctx.get("account_id"), data)
        elif kind == "photo_problem":
            self._on_photo_problem(run_id, ctx.get("account_id"), data)
        elif kind == "verification":
            self._on_verification(run_id, ctx.get("account_id"), data)
        elif kind == "signup_defaults":
            self._save_signup_defaults(data.get("data"))
        elif kind == "apk_check":
            self._on_apk_check(ctx.get("apk_profile_id"), data)

    def _save_signup_defaults(self, data):
        """Latest signup/defaults response from Jaumo (shown next to the signup dropdowns)."""
        if not isinstance(data, dict):
            return
        value = {"received_at": iso(utcnow()), "data": data}
        # upsert: parallel workers may report at the same moment
        stmt = sqlite_insert(AppSetting).values(key="signup_defaults", value=value)
        with Session(engine) as s:
            s.exec(stmt.on_conflict_do_update(index_elements=["key"], set_={"value": value}))
            s.commit()

    def _on_apk_check(self, apk_id, data):
        if not apk_id:
            return
        # Atomic UPDATE: several bots report at the same moment.
        if data.get("ok"):
            values = {"last_ok_at": utcnow(), "ok_count": ApkProfile.ok_count + 1, "fail_streak": 0}
        else:
            values = {"last_fail_at": utcnow(), "fail_count": ApkProfile.fail_count + 1,
                      "fail_streak": ApkProfile.fail_streak + 1,
                      "last_error": (data.get("error") or "")[:300]}
        with Session(engine) as s:
            s.exec(sa_update(ApkProfile).where(ApkProfile.id == apk_id).values(**values))
            s.commit()
            apk = s.get(ApkProfile, apk_id)
            if not apk:
                return
            streak = apk.fail_streak
        self.hub.publish("events", {"type": "apk", "apk_profile_id": apk_id, "fail_streak": streak})

    def _publish_counters(self, account_id, delta=None):
        """Push an account's current numbers so open pages update without reloading."""
        with Session(engine) as s:
            a = s.get(Account, account_id)
            if not a:
                return
            msg = {"type": "counters", "account_id": account_id, "delta": delta or {},
                   "liked_count": a.liked_count, "disliked_count": a.disliked_count, "matches_count": a.matches_count,
                   "messages_sent": a.messages_sent, "actions": a.liked_count + a.disliked_count + a.messages_sent,
                   "likes_received": a.likes_received, "profile_visits": a.profile_visits,
                   "messages_received": a.messages_received, "pending_messages":
                       len(set(map(str, a.matches or [])) - set(map(str, a.messaged or []))),
                   "last_activity_at": iso(a.last_activity_at), "stats_synced_at": iso(a.stats_synced_at)}
        self.hub.publish("events", msg)

    def _account_event(self, account_id, run_id, kind, user_id=None, detail=""):
        with Session(engine) as s:
            ev = AccountEvent(account_id=account_id, run_id=run_id, kind=kind, user_id=user_id, detail=detail)
            s.add(ev)
            s.exec(sa_update(Account).where(Account.id == account_id).values(last_activity_at=ev.ts))
            s.commit()
            s.refresh(ev)
            payload = event_public(ev)
        self.hub.publish(f"account:{account_id}", {"type": "activity", "event": payload})

    def _update_account(self, account_id, fields, run_id=None):
        if not account_id:
            return
        old_status = None
        with Session(engine) as s:
            acc = s.get(Account, account_id)
            if not acc:
                return
            old_status = acc.status
            for k, v in fields.items():
                if hasattr(acc, k):
                    setattr(acc, k, v if v is not None else getattr(acc, k))
            acc.updated_at = utcnow()
            s.add(acc)
            s.commit()
        if "status" in fields:
            if fields["status"] and fields["status"] != old_status:
                self._account_event(account_id, run_id, "status", detail=f"{old_status} → {fields['status']}")
            self.hub.publish("events", {"type": "account", "account_id": account_id})
        self.hub.publish(f"account:{account_id}", {"type": "changed"})

    def _on_swipe(self, run_id, account_id, data):
        uid, action, matched = data["user_id"], data["action"], data.get("matched")
        with Session(engine) as s:
            run = s.get(BotRun, run_id)
            run.swipes += 1
            if action == "like":
                run.liked += 1
                run.matches += 1 if matched else 0
            else:
                run.disliked += 1
            s.add(run)
            if account_id:
                acc = s.get(Account, account_id)
                if action == "like":
                    acc.liked = [*acc.liked, uid]
                    acc.liked_count = len(acc.liked)
                    if matched:
                        acc.matches = [*acc.matches, uid]
                        acc.matches_count = len(acc.matches)
                else:
                    acc.disliked = [*acc.disliked, uid]
                    acc.disliked_count = len(acc.disliked)
                acc.updated_at = utcnow()
                s.add(acc)
            s.commit()
            s.refresh(run)
            payload = run_public(run)
        self.hub.publish("events", {"type": "run", "run": payload})
        self.hub.publish(f"run:{run_id}", {"type": "run", "run": payload})
        if account_id:
            self._account_event(account_id, run_id, "match" if matched else action, user_id=uid)
            self.hub.publish(f"account:{account_id}", {"type": "changed"})
            self._publish_counters(account_id, {"liked": int(action == "like"), "disliked": int(action != "like"),
                                                "matches": int(bool(matched))})

    # --- message worker ----------------------------------------------------

    def _message_worker(self, run_id: int, ev: threading.Event):
        with Session(engine) as s:
            account_id = s.get(BotRun, run_id).account_id
        try:
            self._wait_for_sync(run_id, account_id, ev)
        except StopRequested:
            return self._finish(run_id, {"status": "stopped", "reason": "stopped by admin"})
        with Session(engine) as s:
            run = s.get(BotRun, run_id)
            snap = run.config_snapshot
            acc = s.get(Account, run.account_id)
            if not acc:
                return self._finish(run_id, {"status": "failed", "reason": "account not found"})
            account = acc.model_dump()
        settings = self._session_settings(snap["settings"])

        try:
            proxy = self._acquire_proxy(run_id, ev, settings)
        except StopRequested:
            return self._finish(run_id, {"status": "stopped", "reason": "stopped while waiting for proxy"})
        except NoProxyAvailable as e:
            self._log(run_id, "error", f"[PROXY] {e}")
            return self._finish(run_id, {"status": "failed", "reason": str(e)})

        def emit(kind, data):
            if kind == "log":
                self._log(run_id, data.get("level", "info"), data.get("msg", ""))
            elif kind == "step":
                self._update_run(run_id, step=data["step"])
            elif kind == "account_update":
                self._update_account(account["id"], data, run_id)
            elif kind == "message":
                self._on_message(run_id, account["id"], data)
            elif kind == "stats":
                self._on_stats(run_id, account["id"], data)

        try:
            runner = MessageRunner(settings, snap["apk"], account,
                                   proxy_url=proxy_url(proxy) if proxy else None,
                                   emit=emit, stop_event=ev)
            result = runner.run()
        finally:
            self.pool.release(proxy.id if proxy else None)
        self._finish(run_id, result)

    def _on_message(self, run_id, account_id, data):
        with Session(engine) as s:
            run = s.get(BotRun, run_id)
            acc = s.get(Account, account_id)
            if data.get("ok"):
                run.messages_sent += 1
                acc.messaged = [*acc.messaged, data["user_id"]]
                acc.messages_sent += 1
                acc.updated_at = utcnow()
                s.add(acc)
            s.add(run)
            s.commit()
            s.refresh(run)
            payload = run_public(run)
        self.hub.publish("events", {"type": "run", "run": payload})
        self._account_event(account_id, run_id, "message" if data.get("ok") else "message_failed",
                            user_id=str(data["user_id"]), detail=data.get("text", ""))
        self.hub.publish(f"account:{account_id}", {"type": "changed"})
        if data.get("ok"):
            self._publish_counters(account_id, {"messages": 1})

    # --- stats sync (read-only, admin-triggered) ---------------------------

    # --- automatic stats refresh -----------------------------------------------

    def start_auto_sync(self):
        """Background timer: refresh all accounts every `auto_sync_minutes` (first sweep one interval after start)."""
        threading.Thread(target=self._auto_sync_loop, name="auto-sync", daemon=True).start()

    def _auto_sync_loop(self):
        last = time.monotonic()
        while not self.auto_sync_stop.wait(AUTO_SYNC_TICK):
            try:
                with Session(engine) as s:
                    minutes = int(get_bot_settings(s).get("auto_sync_minutes") or 0)
                interval = AUTO_SYNC_INTERVAL or minutes * 60
                if not interval or time.monotonic() - last < interval:
                    continue
                last = time.monotonic()
                res = self.launch_sync([], all_accounts=True, min_age_seconds=interval / 2)
                print(f"[auto-sync] every {minutes} min: {len(res['run_ids'])} queued, {len(res['skipped'])} skipped",
                      file=sys.stdout, flush=True)
            except Exception as e:  # the timer must keep running
                print(f"[auto-sync] {type(e).__name__}: {e}", file=sys.stdout, flush=True)

    def _cancel_syncs(self, account_ids):
        """A session has priority over a stats refresh of the same account: queued refreshes are removed,
        a running one is stopped (a refresh logs in again and must not swap tokens under the session)."""
        if not account_ids:
            return
        with Session(engine) as s:
            ids = s.exec(select(BotRun.id).where(BotRun.kind == "sync", BotRun.account_id.in_(list(account_ids)),
                                                 BotRun.status.in_(ACTIVE_STATUSES))).all()
        for rid in ids:
            self.stop(rid)

    def _wait_for_sync(self, run_id, account_id, ev, timeout=60):
        """Before a session reads the account's tokens, let a refresh that is already running finish."""
        end = time.monotonic() + timeout
        noted = False
        while time.monotonic() < end:
            with Session(engine) as s:
                busy = s.exec(select(BotRun.id).where(BotRun.kind == "sync", BotRun.account_id == account_id,
                                                      BotRun.status == "running")).first()
            if not busy:
                return
            if not noted:
                self._log(run_id, "info", "[STATS] Waiting for the running stats refresh of this account to finish")
                noted = True
            if ev.wait(0.5):
                raise StopRequested()

    @staticmethod
    def _session_settings(settings: dict) -> dict:
        """Config settings + the stats options of the panel: the session reads its own stats with its login."""
        with Session(engine) as s:
            bot = get_bot_settings(s)
        return {**settings, "stats_every_swipes": int(bot.get("stats_every_swipes") or 0),
                "stats_at_end": bool(bot.get("sync_after_session", True))}

    def launch_sync(self, account_ids: list[int], all_accounts: bool = False, min_age_seconds: float = 0) -> dict:
        """
        Queue read-only stats syncs. One refresh per account at a time with a cooldown;
        "refresh all" runs one account after another with a delay in between.
        Accounts that are working or queued are skipped: a refresh logs in again and must not
        swap the tokens of a running session (they get a refresh when their session ends).
        Returns {"run_ids": [...], "skipped": [{"id", "reason"}]}.
        """
        with Session(engine) as s:
            if all_accounts:
                accs = s.exec(select(Account).where(Account.status.in_(("active", "legacy", "blocked")))
                              .order_by(Account.id)).all()
            else:
                accs = s.exec(select(Account).where(Account.id.in_(account_ids or [-1]))).all()
            busy_sync = set(s.exec(select(BotRun.account_id).where(BotRun.kind == "sync",
                                                                   BotRun.status.in_(ACTIVE_STATUSES))).all())
            working = set(s.exec(select(BotRun.account_id).where(BotRun.kind != "sync",
                                                                 BotRun.status.in_(ACTIVE_STATUSES))).all())
            configs = {c.id: c for c in s.exec(select(BotConfig)).all()}
            fallback = next((c for c in configs.values() if c.apk_profile_id), None)
            delay = float(get_bot_settings(s)["sync_delay_seconds"])
            bulk = len(accs) > 1
            now = utcnow()
            runs, skipped = [], []
            for acc in accs:
                reason = None
                if acc.id in busy_sync:
                    reason = "a refresh for this account is already queued or running"
                elif acc.id in working:
                    reason = "account is working — its stats are refreshed when the session ends"
                elif min_age_seconds and acc.stats_synced_at and \
                        (now - acc.stats_synced_at).total_seconds() < min_age_seconds:
                    reason = "refreshed recently"
                elif not (acc.refresh_token or acc.access_token):
                    reason = "no login token stored"
                elif acc.stats_synced_at and (now - acc.stats_synced_at).total_seconds() < SYNC_COOLDOWN_SECONDS:
                    wait = SYNC_COOLDOWN_SECONDS - int((now - acc.stats_synced_at).total_seconds())
                    reason = f"refreshed a moment ago — wait {wait}s"
                if reason:
                    skipped.append({"id": acc.id, "name": acc.name, "reason": reason})
                    continue
                config = configs.get(acc.config_id) if acc.config_id in configs and configs[acc.config_id].apk_profile_id else fallback
                if not config:
                    skipped.append({"id": acc.id, "name": acc.name, "reason": "no configuration with an APK profile"})
                    continue
                try:
                    snap = self._snapshot(s, config)
                except ValueError as e:
                    skipped.append({"id": acc.id, "name": acc.name, "reason": str(e)})
                    continue
                snap["sync_delay"] = delay if bulk else 0
                run = BotRun(kind="sync", config_id=config.id, config_name=config.name, config_snapshot=snap,
                             account_id=acc.id, requested_name=acc.name)
                s.add(run)
                runs.append(run)
            s.commit()
            ids = [r.id for r in runs]
            payloads = [run_public(r) for r in runs]
        for rid, payload in zip(ids, payloads):
            self.hub.publish("events", {"type": "run", "run": payload})
            ev = threading.Event()
            with self.lock:
                self.stop_events[rid] = ev
            self.sync_executor.submit(self._sync_guard, rid, ev)
        return {"run_ids": ids, "skipped": skipped}

    def _sync_guard(self, run_id: int, ev: threading.Event):
        delay = 0
        try:
            with Session(engine) as s:
                run = s.get(BotRun, run_id)
                if not run or run.status != "queued":
                    return
                kind = run.kind
                delay = float(run.config_snapshot.get("sync_delay") or 0)
            if ev.is_set():
                self._update_run(run_id, status="stopped", reason="stopped before start", finished_at=utcnow())
                return
            self._update_run(run_id, status="running", started_at=utcnow(), step="starting")
            (self._rename_worker if kind == "rename" else self._sync_worker)(run_id, ev)
        except Exception as e:  # never leave a run "running"
            self._log(run_id, "error", f"[MANAGER] {type(e).__name__}: {e}")
            self._update_run(run_id, status="failed", reason=f"{type(e).__name__}: {e}", finished_at=utcnow())
        finally:
            with self.lock:
                self.stop_events.pop(run_id, None)
            self.labels.pop(run_id, None)
            if delay:
                ev.wait(delay)   # pause before the next account of a "refresh all"

    def _sync_worker(self, run_id: int, ev: threading.Event):
        with Session(engine) as s:
            run = s.get(BotRun, run_id)
            snap = run.config_snapshot
            acc = s.get(Account, run.account_id)
            if not acc:
                return self._finish(run_id, {"status": "failed", "reason": "account not found"})
            account = acc.model_dump()
        settings = snap["settings"]
        try:
            proxy = self._acquire_proxy(run_id, ev, settings)
        except StopRequested:
            return self._finish(run_id, {"status": "stopped", "reason": "stopped while waiting for proxy"})
        except NoProxyAvailable as e:
            self._log(run_id, "error", f"[PROXY] {e}")
            self._store_sync_error(account["id"], str(e))
            return self._finish(run_id, {"status": "failed", "reason": str(e)})

        def emit(kind, data):
            if kind == "log":
                self._log(run_id, data.get("level", "info"), data.get("msg", ""))
            elif kind == "step":
                self._update_run(run_id, step=data["step"])
            elif kind == "account_update":
                self._update_account(account["id"], data, run_id)
            elif kind == "stats":
                self._on_stats(run_id, account["id"], data)

        try:
            runner = StatsSyncRunner(settings, snap["apk"], account, proxy_url=proxy_url(proxy) if proxy else None,
                                     emit=emit, stop_event=ev)
            result = runner.run()
        finally:
            self.pool.release(proxy.id if proxy else None)
        if result["status"] != "done":
            self._store_sync_error(account["id"], result.get("reason", "failed"))
        self._finish(run_id, result)

    # --- nickname change (later, for existing accounts) ----------------------------

    RENAME_STATUSES = ("active", "legacy", "stopped")

    def launch_rename(self, account_ids: list[int]) -> dict:
        """Give the selected accounts the next free names of the "Nicknamen ändern" list (one short job each)."""
        with Session(engine) as s:
            config = get_main_config(s)
            if not config:
                raise LookupError("config not found")
            snap = self._snapshot(s, config)
            accounts = s.exec(select(Account).where(Account.id.in_(account_ids)).order_by(Account.id)).all()
            busy = set(s.exec(select(BotRun.account_id).where(BotRun.status.in_(ACTIVE_STATUSES),
                                                              BotRun.kind != "sync")).all())
            eligible, skipped = [], []
            for acc in accounts:
                reason = ("already working" if acc.id in busy
                          else "blocked by Jaumo" if acc.status == "blocked"
                          else "account was never fully set up" if acc.status not in self.RENAME_STATUSES
                          else "no login token stored" if not (acc.refresh_token or acc.access_token) else "")
                if reason:
                    skipped.append({"id": acc.id, "name": acc.name, "reason": reason})
                else:
                    eligible.append(acc)
            names = pick_rename(rename_usage(s), snap["settings"], len(eligible), force=True) if eligible else []
            runs = []
            for acc, new in zip(eligible, names):
                run = BotRun(kind="rename", config_id=config.id, config_name=config.name, config_snapshot=snap,
                             account_id=acc.id, requested_name=acc.name, rename_to=new)
                s.add(run)
                runs.append(run)
            s.commit()
            ids = [r.id for r in runs]
            payloads = [run_public(r) for r in runs]
        self._cancel_syncs([p["account_id"] for p in payloads])
        for rid, payload in zip(ids, payloads):
            self.hub.publish("events", {"type": "run", "run": payload})
            ev = threading.Event()
            with self.lock:
                self.stop_events[rid] = ev
            self.sync_executor.submit(self._sync_guard, rid, ev)
        return {"run_ids": ids, "skipped": skipped}

    def _rename_worker(self, run_id: int, ev: threading.Event):
        with Session(engine) as s:
            run = s.get(BotRun, run_id)
            snap, new_name = run.config_snapshot, run.rename_to
            acc = s.get(Account, run.account_id)
            if not acc:
                return self._finish(run_id, {"status": "failed", "reason": "account not found"})
            account = acc.model_dump()
        settings = snap["settings"]
        try:
            proxy = self._acquire_proxy(run_id, ev, settings)
        except StopRequested:
            return self._finish(run_id, {"status": "stopped", "reason": "stopped while waiting for proxy"})
        except NoProxyAvailable as e:
            self._log(run_id, "error", f"[PROXY] {e}")
            return self._finish(run_id, {"status": "failed", "reason": str(e)})

        def emit(kind, data):
            if kind == "log":
                self._log(run_id, data.get("level", "info"), data.get("msg", ""))
            elif kind == "step":
                self._update_run(run_id, step=data["step"])
            elif kind == "account_update":
                self._update_account(account["id"], data, run_id)
            elif kind == "renamed":
                self._on_renamed(run_id, account["id"], data)

        try:
            runner = RenameRunner(settings, snap["apk"], account, new_name,
                                  proxy_url=proxy_url(proxy) if proxy else None, emit=emit, stop_event=ev)
            result = runner.run()
        finally:
            self.pool.release(proxy.id if proxy else None)
        self._finish(run_id, result)

    def _on_verification(self, run_id, account_id, data):
        """Jaumo requires profile verification before liking — store the message and note it in the history."""
        msg = (data.get("message") or "").strip()
        if not account_id:
            return
        with Session(engine) as s:
            acc = s.get(Account, account_id)
            if acc:
                acc.verify_info = msg
                s.add(acc)
                s.commit()
        self._account_event(account_id, run_id, "verification", detail=msg)
        self.hub.publish(f"account:{account_id}", {"type": "changed"})

    def _on_photo_problem(self, run_id, account_id, data):
        """Store why the photo failed; a photo Jaumo refused is marked so no other account gets it."""
        reason, rejected = (data.get("reason") or "").strip(), bool(data.get("rejected"))
        with Session(engine) as s:
            run = s.get(BotRun, run_id)
            filename = run.photo if run else None
            if account_id:
                acc = s.get(Account, account_id)
                if acc:
                    acc.photo_error = reason
                    s.add(acc)
            if rejected and filename:
                photo = s.exec(select(Photo).where(Photo.filename == filename)).first()
                if photo:
                    photo.rejected_reason = reason or "rejected by Jaumo"
                    photo.rejected_at = utcnow()
                    s.add(photo)
            s.commit()
        if account_id:
            self._account_event(account_id, run_id, "photo_rejected" if rejected else "photo_failed",
                                detail=f"{filename or ''}: {reason}".strip(": "))
            self.hub.publish(f"account:{account_id}", {"type": "changed"})

    def _on_renamed(self, run_id, account_id, data):
        old, new = (data.get("old") or "").strip(), (data.get("new") or "").strip()
        if not account_id or not new:
            return
        with Session(engine) as s:
            acc = s.get(Account, account_id)
            if not acc:
                return
            old = old or acc.name
            if old and _key(old) != _key(new):
                acc.name_history = [*(acc.name_history or []), old]
            acc.name = new
            acc.rename_error = ""
            acc.updated_at = utcnow()
            s.add(acc)
            s.commit()
        self._account_event(account_id, run_id, "renamed", detail=f"{old} → {new}")
        self.hub.publish("events", {"type": "account", "account_id": account_id})
        self.hub.publish(f"account:{account_id}", {"type": "changed"})

    def _store_sync_error(self, account_id, reason):
        with Session(engine) as s:
            acc = s.get(Account, account_id)
            if acc:
                acc.stats_sync_error = reason[:300]
                acc.stats_synced_at = utcnow()   # cooldown also applies after a failed refresh
                s.add(acc)
                s.commit()
        self.hub.publish(f"account:{account_id}", {"type": "changed"})

    def _on_stats(self, run_id, account_id, data):
        c = data.get("counters") or {}
        with Session(engine) as s:
            acc = s.get(Account, account_id)
            if not acc:
                return
            acc.likes_received = c.get("likes", 0)
            acc.profile_visits = c.get("visits", 0)
            acc.messages_received = c.get("conversations", 0)
            acc.requests_received = c.get("requests", 0)
            new_matches = []
            if data.get("match_ids") is not None:
                known = [str(m) for m in (acc.matches or [])]
                new_matches = [m for m in dict.fromkeys(data["match_ids"]) if m not in set(known)]
                acc.matches = known + new_matches
            acc.matches_count = max(len(acc.matches or []), int(c.get("matches", 0)))
            acc.stats_synced_at = utcnow()
            acc.stats_sync_error = ""
            acc.updated_at = utcnow()
            s.add(acc)
            s.commit()
        self._account_event(account_id, run_id, "sync",
                            detail=(f"likes {c.get('likes', 0)} · visitors {c.get('visits', 0)} · "
                                    f"messages {c.get('conversations', 0)} · matches {c.get('matches', 0)}"
                                    + (f" · {len(new_matches)} new match ids" if new_matches else "")))
        self.hub.publish("events", {"type": "account", "account_id": account_id})
        self.hub.publish(f"account:{account_id}", {"type": "changed"})
        self._publish_counters(account_id, {"synced": 1})
