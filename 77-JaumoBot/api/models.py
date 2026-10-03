"""SQLite tables (SQLModel). JSON columns must be re-assigned, not mutated in place."""

from datetime import datetime, timezone
from typing import ClassVar, Optional

from sqlalchemy import JSON, Column, event
from sqlmodel import Field, Session, SQLModel, create_engine

from .settings import DB_PATH


def utcnow():
    return datetime.now(timezone.utc)


def iso(d):
    if not d:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class ApkProfile(SQLModel, table=True):
    """client_id + sign_secret + user_agent must come from the same APK build."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    client_id: str
    sign_secret: str
    user_agent: str
    package_id: str = "com.jaumo"
    os_version: str = "14"
    accept_language: str = "en_US"
    enabled: bool = True             # disabled profiles cannot be launched
    notes: str = ""
    # Health, updated by signup runs at the client-token step.
    last_ok_at: Optional[datetime] = None
    last_fail_at: Optional[datetime] = None
    last_error: str = ""
    fail_streak: int = 0
    ok_count: int = 0
    fail_count: int = 0
    created_at: datetime = Field(default_factory=utcnow)

    # Fields the engine needs; health/meta fields stay out of run snapshots.
    CREDENTIAL_FIELDS: ClassVar[tuple] = ("client_id", "sign_secret", "user_agent", "package_id",
                         "os_version", "accept_language")

    def credentials(self) -> dict:
        return {k: getattr(self, k) for k in self.CREDENTIAL_FIELDS}


class BotConfig(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    apk_profile_id: Optional[int] = Field(default=None, foreign_key="apkprofile.id")
    settings: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Proxy(SQLModel, table=True):
    """
    shared=True  → rotating gateway line, used by any number of bots at once.
    shared=False → dedicated sticky-session line, one bot at a time.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    label: str = ""
    scheme: str = "http"
    host: str
    port: int
    username: str = ""
    password: str = ""
    shared: bool = False
    enabled: bool = True
    use_count: int = 0
    last_used_at: Optional[datetime] = None
    last_test_at: Optional[datetime] = None
    last_test_ok: Optional[bool] = None
    last_test_ip: Optional[str] = None
    last_test_country: Optional[str] = None
    last_test_error: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class BotRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    kind: str = Field(default="signup", index=True)        # signup | message
    status: str = Field(default="queued", index=True)      # queued|running|done|blocked|failed|stopped|interrupted
    reason: str = ""
    step: str = ""
    config_id: Optional[int] = Field(default=None, index=True)
    config_name: str = ""
    config_snapshot: dict = Field(default_factory=dict, sa_column=Column(JSON))
    requested_name: Optional[str] = None
    photo: Optional[str] = None                             # photo filename reserved at launch
    about_text: Optional[str] = None                        # profile text reserved at launch
    rename_to: Optional[str] = None                         # new nickname reserved at launch / for a rename job
    worker: Optional[int] = None                            # worker slot (1..parallel) that ran it
    proxy_id: Optional[int] = None
    proxy_label: str = ""
    account_id: Optional[int] = Field(default=None, index=True)
    swipes: int = 0
    liked: int = 0
    disliked: int = 0
    matches: int = 0
    messages_sent: int = 0
    created_at: datetime = Field(default_factory=utcnow, index=True)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class Account(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: Optional[int] = Field(default=None, index=True)
    config_id: Optional[int] = None
    proxy_id: Optional[int] = None
    worker: Optional[int] = Field(default=None, index=True)   # worker slot that created the account
    jaumo_id: Optional[str] = Field(default=None, index=True)  # user id from /me
    created_at: datetime = Field(default_factory=utcnow, index=True)
    last_activity_at: Optional[datetime] = Field(default=None, index=True)
    name: str = ""
    gender: int = 2
    birthday: str = ""
    looking_for_gender: int = 1
    location: str = Field(default="", index=True)
    latitude: Optional[str] = None      # exact point used at signup (city centre or jittered)
    relationship_search: Optional[str] = None          # values the account was registered with
    dating_relationship_search: Optional[str] = None
    longitude: Optional[str] = None
    photo: Optional[str] = None
    photo_url: Optional[str] = None
    about_me: Optional[str] = None                          # profile text accepted by Jaumo
    token_expires_at: Optional[float] = None                # epoch seconds; login is reused until then
    about_me_error: str = ""
    name_history: list = Field(default_factory=list, sa_column=Column(JSON))   # earlier nicknames, oldest first
    rename_error: str = ""
    photo_error: str = ""                                   # why the photo step failed (shown on the account)
    verify_info: str = ""                                   # what Jaumo said when it required verification
    # signing_up|active|blocked|verification_required|limit_reached|photo_failed|failed|stopped|legacy
    status: str = Field(default="signing_up", index=True)
    photo_uploaded: bool = False
    gallery_count: int = 0
    android_id: str = ""
    device_id: str = ""
    device_info: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    access_token: str = ""
    refresh_token: str = ""
    liked: list = Field(default_factory=list, sa_column=Column(JSON))
    disliked: list = Field(default_factory=list, sa_column=Column(JSON))
    matches: list = Field(default_factory=list, sa_column=Column(JSON))
    messaged: list = Field(default_factory=list, sa_column=Column(JSON))
    liked_count: int = 0
    disliked_count: int = 0
    matches_count: int = 0
    messages_sent: int = 0
    # Filled by an inbox / visitors sync once those endpoints are known from the APK (None = not synced yet).
    messages_received: Optional[int] = None
    profile_visits: Optional[int] = None
    likes_received: Optional[int] = None          # stats sync (UnseenResponse.likes)
    requests_received: Optional[int] = None       # stats sync (UnseenResponse.requests)
    stats_synced_at: Optional[datetime] = None
    stats_sync_error: str = ""
    notes: str = ""
    updated_at: datetime = Field(default_factory=utcnow)


class AccountEvent(SQLModel, table=True):
    """Per-account activity timeline: like, dislike, match, message, message_failed, status, created."""
    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(index=True)
    run_id: Optional[int] = None
    ts: datetime = Field(default_factory=utcnow, index=True)
    kind: str = ""
    user_id: Optional[str] = None
    detail: str = ""


class Photo(SQLModel, table=True):
    """Photo library. Usage is derived from Account.photo / BotRun.photo (filename)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str = Field(index=True, unique=True)
    sha256: str = Field(index=True)
    width: int = 0
    height: int = 0
    size: int = 0
    original_name: str = ""
    created_at: datetime = Field(default_factory=utcnow, index=True)
    rejected_reason: str = ""                  # Jaumo refused this image -> never given to another account
    rejected_at: Optional[datetime] = None


class AppSetting(SQLModel, table=True):
    """Global key/value settings (identity rules, ...)."""
    key: str = Field(primary_key=True)
    value: dict = Field(default_factory=dict, sa_column=Column(JSON))


class RunLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(index=True)
    ts: datetime = Field(default_factory=utcnow)
    level: str = "info"
    msg: str = ""


engine = create_engine(
    f"sqlite:///{DB_PATH.as_posix()}",
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA busy_timeout=30000")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


def _add_missing_columns():
    """
    Tiny forward-only migration: create_all() never alters existing tables, so
    add any model column the SQLite file is missing (with its scalar default).
    """
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            existing = {row[1] for row in conn.exec_driver_sql(f'PRAGMA table_info("{table.name}")')}
            for col in table.columns:
                if col.name in existing:
                    continue
                col_type = col.type.compile(dialect=engine.dialect)
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col_type}'
                default = col.default.arg if col.default is not None and col.default.is_scalar else None
                if isinstance(default, bool):
                    ddl += f" DEFAULT {int(default)}"
                elif isinstance(default, (int, float)):
                    ddl += f" DEFAULT {default}"
                elif isinstance(default, str):
                    ddl += " DEFAULT '" + default.replace("'", "''") + "'"
                conn.exec_driver_sql(ddl)
                print(f"[migrate] added column {table.name}.{col.name}")


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)
    _add_missing_columns()


def get_session():
    with Session(engine) as session:
        yield session
