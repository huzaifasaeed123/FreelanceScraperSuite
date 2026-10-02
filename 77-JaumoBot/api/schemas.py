"""Pydantic request/response shapes."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from bot.engine import DEFAULT_SETTINGS

_D = DEFAULT_SETTINGS


class Location(BaseModel):
    label: str
    lat: str
    lon: str
    radius_km: Optional[float] = Field(None, ge=0, le=100)   # overrides the config's default radius


class Device(BaseModel):
    manufacturer: str
    model: str
    brand: str


def _range(key):
    return Field(default_factory=lambda: list(_D["delays"][key]))


class Delays(BaseModel):
    after_signup: list[float] = _range("after_signup")
    after_location: list[float] = _range("after_location")
    after_refresh: list[float] = _range("after_refresh")
    after_profile: list[float] = _range("after_profile")
    before_photo: list[float] = _range("before_photo")
    after_photo: list[float] = _range("after_photo")
    between_swipes: list[float] = _range("between_swipes")
    between_batches: list[float] = _range("between_batches")
    before_message: list[float] = _range("before_message")

    @model_validator(mode="after")
    def _check(self):
        for key, value in self.__dict__.items():
            if len(value) != 2 or value[0] < 0 or value[1] < value[0]:
                raise ValueError(f"delay '{key}' must be [min, max] with 0 <= min <= max")
        return self


class ConfigSettings(BaseModel):
    request_timeout: int = Field(_D["request_timeout"], ge=5, le=300)
    delays: Delays = Field(default_factory=Delays)
    like_ratio: float = Field(_D["like_ratio"], ge=0, le=1)
    location_radius_km: float = Field(_D["location_radius_km"], ge=0, le=100)
    max_swipes: int = Field(_D["max_swipes"], ge=0)
    block_threshold: int = Field(_D["block_threshold"], ge=1, le=100)
    max_empty_batches: int = Field(_D["max_empty_batches"], ge=1, le=100)
    age_min: int = Field(_D["age_min"], ge=18, le=99)
    age_max: int = Field(_D["age_max"], ge=18, le=99)
    name_source: Literal["auto", "custom"] = _D["name_source"]
    messaging_enabled: bool = _D["messaging_enabled"]
    looking_for_gender: Literal[1, 2] = _D["looking_for_gender"]
    relationship_search: Literal["FLIRT", "FRIENDSHIP"] = _D["relationship_search"]
    dating_relationship_search: Literal["FLIRT", "FRIENDSHIP"] = _D["dating_relationship_search"]
    allow_in_all_brands: bool = _D["allow_in_all_brands"]
    name_pool: list[str] = Field(default_factory=lambda: list(_D["name_pool"]))
    photo_pool: list[str] = Field(default_factory=list)
    locations: list[Location] = Field(default_factory=lambda: [Location(**l) for l in _D["locations"]])
    devices: list[Device] = Field(default_factory=lambda: [Device(**d) for d in _D["devices"]])
    message_templates: list[str] = Field(default_factory=lambda: list(_D["message_templates"]))
    require_proxy: bool = True
    about_enabled: bool = _D["about_enabled"]
    about_pool: list[str] = Field(default_factory=list)
    about_unique: bool = _D["about_unique"]

    @field_validator("name_pool", "photo_pool", "message_templates", "about_pool")
    @classmethod
    def _strip(cls, v):
        return [s.strip() for s in v if s and s.strip()]

    @model_validator(mode="after")
    def _check(self):
        if self.age_max < self.age_min:
            raise ValueError("age_max must be >= age_min")
        if self.name_source == "custom" and not self.name_pool:
            raise ValueError("custom name list cannot be empty (or switch names to auto)")
        if self.about_enabled and not self.about_pool:
            raise ValueError("profile text list cannot be empty (or turn profile texts off)")
        if not self.locations:
            raise ValueError("locations cannot be empty")
        if not self.devices:
            raise ValueError("devices cannot be empty")
        return self


class ConfigPatch(BaseModel):
    """Part of the main configuration's settings; keys not sent keep their value."""
    settings: dict = Field(default_factory=dict)


class ConfigIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    apk_profile_id: Optional[int] = None
    settings: ConfigSettings = Field(default_factory=ConfigSettings)


class ApkProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    client_id: str = Field(min_length=1)
    sign_secret: str = ""          # empty on update = keep existing
    user_agent: str = Field(min_length=1)
    package_id: str = "com.jaumo"
    os_version: str = "14"
    accept_language: str = "en_US"
    enabled: bool = True
    notes: str = ""


class ApkPatch(BaseModel):
    enabled: Optional[bool] = None
    notes: Optional[str] = None


class ApkMoveConfigs(BaseModel):
    to_apk_profile_id: int


class ProxyIn(BaseModel):
    line: Optional[str] = None     # "host:port:user:pass" etc. — overrides fields
    label: str = ""
    scheme: str = "http"
    host: Optional[str] = None
    port: Optional[int] = None
    username: str = ""
    password: str = ""
    shared: bool = False
    enabled: bool = True


class ProxyUpdate(BaseModel):
    label: Optional[str] = None
    scheme: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    shared: Optional[bool] = None
    enabled: Optional[bool] = None


class ProxyBulkIn(BaseModel):
    text: str
    shared: bool = False
    label: str = ""
    replace: bool = False          # delete all existing proxies first


class ProxyBulkAction(BaseModel):
    ids: list[int]
    action: str                    # enable | disable | delete | test | shared | dedicated


class RunLaunch(BaseModel):
    config_id: Optional[int] = None    # None = the main Jaumo configuration
    count: int = Field(1, ge=1, le=500)
    names: list[str] = Field(default_factory=list)   # optional manual names, one per bot


class MessageLaunch(BaseModel):
    config_id: Optional[int] = None    # None = the main Jaumo configuration
    account_ids: list[int] = Field(default_factory=list)  # empty = all eligible accounts


class AccountPatch(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class LoginIn(BaseModel):
    username: str
    password: str


class IdentitySettings(BaseModel):
    unique_names: bool = True
    unique_photos: bool = True


class BotSettings(BaseModel):
    parallel_accounts: int = Field(1, ge=1, le=20)
    sync_delay_seconds: float = Field(10, ge=2, le=600)   # pause between accounts in "refresh all"
    sync_after_session: bool = True                       # refresh an account's stats when its session ends
    auto_sync_minutes: int = Field(30, ge=0, le=1440)     # refresh all accounts every N minutes (0 = off)

    @model_validator(mode="after")
    def _check(self):
        if 0 < self.auto_sync_minutes < 5:
            raise ValueError("auto_sync_minutes must be 0 (off) or at least 5")
        return self


class SwipeIn(BaseModel):
    account_ids: list[int] = Field(min_length=1, max_length=500)


class StatsSyncIn(BaseModel):
    account_ids: list[int] = Field(default_factory=list)
    all: bool = False


class SettingsIn(BaseModel):
    identity: Optional[IdentitySettings] = None
    bot: Optional[BotSettings] = None


class PhotoBulkDelete(BaseModel):
    names: list[str]


class CleanupIn(BaseModel):
    days: int = Field(7, ge=0)
    delete_runs: bool = False
