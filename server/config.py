"""Configuration for the Coune Labworks birthday installation."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
IMAGES_DIR = DATA_DIR / "images"
CARDS_DIR = DATA_DIR / "cards"
LOGS_DIR = DATA_DIR / "logs"
SUBMISSIONS_FILE = DATA_DIR / "submissions.json"

WEB_DIR = PROJECT_ROOT / "web"

HOST = os.environ.get("BIRTHDAY_HOST", "0.0.0.0")
PORT = int(os.environ.get("BIRTHDAY_PORT", "8080"))

TD_OSC_ENABLED = os.environ.get("BIRTHDAY_TD_OSC_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}
TD_OSC_HOST = os.environ.get("BIRTHDAY_TD_OSC_HOST", "127.0.0.1")
TD_OSC_PORT = int(os.environ.get("BIRTHDAY_TD_OSC_PORT", "9001"))
TD_OSC_ADDRESS = os.environ.get("BIRTHDAY_TD_OSC_ADDRESS", "/birthday/submission")

MAX_NAME_LENGTH = 80
MAX_MESSAGE_LENGTH = 280
MAX_IMAGE_BYTES = 8 * 1024 * 1024

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}

ADMIN_TOKEN = os.environ.get("BIRTHDAY_ADMIN_TOKEN", "coune-labworks-2026")
TIMEZONE_OFFSET_HOURS = 7
