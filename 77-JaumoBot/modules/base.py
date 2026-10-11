"""Contract every bot module implements. A module is a package under modules/<key>/ that exposes
`module = BotModule(...)` in its __init__.py and is listed once in modules/registry.py."""

import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import APIRouter


@dataclass
class ModuleContext:
    """What the panel hands to a module at startup."""
    key: str
    hub: Any                 # api.manager.Hub — publish(f"{key}:events", {...}) reaches /ws/modules/{key}
    storage_dir: Path        # private folder for this module's files (media, exports, ...)


@dataclass
class BotModule:
    key: str                                   # url/table/storage prefix: "telegram" -> /api/telegram, storage/telegram/
    title: str                                 # shown in the sidebar
    icon: str = "bot"
    # FastAPI router; mounted at /api/{key} behind the panel login. Do not add auth yourself.
    router: Optional[APIRouter] = None
    # Sidebar entries: [{"tab": "telegram-chats", "label": "Chats", "icon": "users"}, ...]
    nav: list = field(default_factory=list)
    # The module's whole UI as ONE script file (a built bundle or plain JS), served at
    # /modules-static/{key}/panel.js and loaded by the panel when the module's tab is opened.
    panel: Optional[Path] = None
    # Lifecycle hooks, sync or async. on_startup runs after the DB exists; on_shutdown on server stop.
    on_startup: Optional[Callable[[ModuleContext], Any]] = None
    on_shutdown: Optional[Callable[[ModuleContext], Any]] = None
    # The card of this bot on the main dashboard: a function returning
    #   {"status": "active" | "offline" | "error", "metrics": [{"label": {"de": ..., "en": ...}, "value": 24}, ...]}
    # (three metrics fit the card). The panel adds the title, icon and the link to the bot's own dashboard.
    summary: Optional[Callable[[], dict]] = None
    color: str = ""        # accent colour of the card, e.g. "#229ED9"

    def manifest(self) -> dict:
        """What the panel needs to render this module (sent by GET /api/modules)."""
        return {"key": self.key, "title": self.title, "icon": self.icon, "nav": self.nav, "color": self.color,
                "panel": f"/modules-static/{self.key}/panel.js" if self.panel else None}


async def call_hook(hook: Optional[Callable], ctx: ModuleContext):
    if hook is None:
        return
    result = hook(ctx)
    if inspect.isawaitable(result):
        await result
