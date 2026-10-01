"""Environment-driven settings. Everything persistent lives under STORAGE_DIR."""

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

STORAGE_DIR = Path(os.environ.get("STORAGE_DIR") or ROOT_DIR / "storage").resolve()
PHOTOS_DIR = STORAGE_DIR / "photos"
DB_PATH = STORAGE_DIR / "db.sqlite"
LEGACY_ACCOUNTS_FILE = STORAGE_DIR / "accounts.txt"
FRONTEND_DIR = ROOT_DIR / "frontend"

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "changeme")
SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
SECRET_KEY_IS_RANDOM = not os.environ.get("SECRET_KEY")
SESSION_DAYS = int(os.environ.get("SESSION_DAYS", "7"))

# Optional seed for the first APK profile (only used when none exist yet).
SEED_CLIENT_ID = os.environ.get("JAUMO_CLIENT_ID", "")
SEED_SIGN_SECRET = os.environ.get("JAUMO_SIGN_SECRET", "")
SEED_USER_AGENT = os.environ.get("JAUMO_USER_AGENT", "")

PROXY_TEST_URL = os.environ.get("PROXY_TEST_URL", "https://ipinfo.io/json")
