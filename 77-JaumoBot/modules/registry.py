"""The one place that lists the bot modules. To add a bot: create modules/<key>/ exposing `module`,
then add "<key>" to AVAILABLE. Set ENABLED_MODULES=telegram,foo in .env to load only some (default: all)."""

import importlib
import os

from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import FileResponse

from api import settings as cfg
from api.auth import require_auth

from .base import BotModule, ModuleContext, call_hook

AVAILABLE = [
    "telegram",
]


def enabled_keys() -> list[str]:
    wanted = [k.strip() for k in os.environ.get("ENABLED_MODULES", "").split(",") if k.strip()]
    unknown = [k for k in wanted if k not in AVAILABLE]
    if unknown:
        raise RuntimeError(f"ENABLED_MODULES names unknown modules: {', '.join(unknown)}")
    return wanted or list(AVAILABLE)


class ModuleRegistry:
    def __init__(self):
        self.modules: dict[str, BotModule] = {}

    def load(self) -> "ModuleRegistry":
        """Import every enabled module. Importing registers its SQLModel tables, so this must run
        before api.models.init_db() creates the schema."""
        for key in enabled_keys():
            mod = importlib.import_module(f"modules.{key}").module
            if mod.key != key:
                raise RuntimeError(f"modules.{key} declares key {mod.key!r}")
            self.modules[key] = mod
        return self

    def mount(self, app: FastAPI):
        """Routes, static assets and the manifest endpoint."""
        manifest = APIRouter()

        @manifest.get("/api/modules")
        def list_modules():
            return [m.manifest() for m in self.modules.values()]

        app.include_router(manifest, dependencies=[Depends(require_auth)])
        for key, m in self.modules.items():
            if m.router is not None:
                app.include_router(m.router, prefix=f"/api/{key}", tags=[key],
                                   dependencies=[Depends(require_auth)])
            if m.panel is not None:
                app.add_api_route(f"/modules-static/{key}/panel.js", self._panel_handler(m.panel),
                                  include_in_schema=False)

    @staticmethod
    def _panel_handler(path):
        def serve():  # no-cache: a deploy never leaves a stale module script in the browser
            return FileResponse(path, media_type="text/javascript", headers={"Cache-Control": "no-cache"})
        return serve

    def context(self, key: str) -> ModuleContext:
        folder = cfg.STORAGE_DIR / key
        folder.mkdir(parents=True, exist_ok=True)
        return ModuleContext(key=key, hub=self.hub, storage_dir=folder)

    async def startup(self, hub):
        self.hub = hub
        for key, m in self.modules.items():
            await call_hook(m.on_startup, self.context(key))

    async def shutdown(self):
        for key, m in reversed(list(self.modules.items())):
            try:
                await call_hook(m.on_shutdown, self.context(key))
            except Exception as e:  # one module failing to stop must not block the others
                print(f"[modules] {key} shutdown failed: {e}")


registry = ModuleRegistry()
