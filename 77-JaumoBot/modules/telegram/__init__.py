"""Telegram bot module: link Telegram accounts, capture chats, send workflows chat by chat.
  api.py     tables + routes        engine.py  bot logic        panel.js  the UI"""

from pathlib import Path

from modules.base import BotModule

from .api import router
from .engine import tg

module = BotModule(
    key="telegram", title="Telegram", icon="send", router=router,
    panel=Path(__file__).with_name("panel.js"),
    on_startup=tg.startup, on_shutdown=tg.shutdown,
    # the first entry is the group header's page; the rest form the sub-menu
    nav=[
        {"tab": "dashboard", "label": {"de": "Dashboard", "en": "Dashboard"}, "icon": "activity"},
        {"tab": "accounts", "label": {"de": "Konten", "en": "Accounts"}, "icon": "users"},
        {"tab": "chats", "label": {"de": "Chats", "en": "Chats"}, "icon": "message"},
        {"tab": "workflows", "label": {"de": "Abläufe", "en": "Workflows"}, "icon": "sliders"},
        {"tab": "runs", "label": {"de": "Versand", "en": "Sending"}, "icon": "play"},
        {"tab": "history", "label": {"de": "Verlauf", "en": "History"}, "icon": "clock"},
    ],
)
