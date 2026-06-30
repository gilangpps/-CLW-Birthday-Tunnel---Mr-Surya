"""Thread-safe local storage for submissions and uploaded photos."""

import json
import logging
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from config import CARDS_DIR, DATA_DIR, IMAGES_DIR, LOGS_DIR, SUBMISSIONS_FILE, TIMEZONE_OFFSET_HOURS, WORDCLOUD_DIR
except ModuleNotFoundError:
    from .config import CARDS_DIR, DATA_DIR, IMAGES_DIR, LOGS_DIR, SUBMISSIONS_FILE, TIMEZONE_OFFSET_HOURS, WORDCLOUD_DIR

LOCK = threading.Lock()
LOCAL_TZ = timezone(timedelta(hours=TIMEZONE_OFFSET_HOURS))


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    WORDCLOUD_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    if not SUBMISSIONS_FILE.exists():
        SUBMISSIONS_FILE.write_text("[]\n", encoding="utf-8")


def build_logger() -> logging.Logger:
    ensure_dirs()
    logger = logging.getLogger("birthday-installation")
    if logger.handlers:
        return logger

    handler = logging.FileHandler(LOGS_DIR / "server.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


logger = build_logger()


def _read_records() -> list[dict[str, Any]]:
    ensure_dirs()
    try:
        return json.loads(SUBMISSIONS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        corrupt = SUBMISSIONS_FILE.with_suffix(".corrupt.json")
        SUBMISSIONS_FILE.replace(corrupt)
        logger.error("Submission JSON was corrupt and moved to %s", corrupt)
        SUBMISSIONS_FILE.write_text("[]\n", encoding="utf-8")
        return []


def _write_records(records: list[dict[str, Any]]) -> None:
    ensure_dirs()
    tmp_path = SUBMISSIONS_FILE.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(SUBMISSIONS_FILE)


def generate_id() -> str:
    return secrets.token_hex(3).upper()


def now_iso() -> str:
    return datetime.now(LOCAL_TZ).isoformat(timespec="seconds")


def filename_stamp() -> str:
    return datetime.now(LOCAL_TZ).strftime("%Y%m%d_%H%M%S")


def safe_image_path(filename: str) -> Path:
    return IMAGES_DIR / Path(filename).name


def safe_card_path(filename: str) -> Path:
    return CARDS_DIR / Path(filename).name


def make_image_filename(submission_id: str, ext: str) -> str:
    return f"{filename_stamp()}_{submission_id}{ext.lower()}"


def make_card_filename(submission_id: str) -> str:
    return f"{filename_stamp()}_{submission_id}_card.jpg"


def append_submission(record: dict[str, Any]) -> dict[str, Any]:
    with LOCK:
        records = _read_records()
        records.append(record)
        _write_records(records)
    logger.info("Submission saved id=%s name=%s", record["id"], record["name"])
    return record


def all_submissions() -> list[dict[str, Any]]:
    with LOCK:
        return _read_records()


def submissions_since(since_id: str | None) -> list[dict[str, Any]]:
    records = all_submissions()
    if not since_id:
        return records

    for index, record in enumerate(records):
        if record.get("id") == since_id:
            return records[index + 1 :]
    return records


def submission_count() -> int:
    return len(all_submissions())


def reset_submissions() -> None:
    with LOCK:
        _write_records([])

    for path in IMAGES_DIR.iterdir():
        if path.is_file() and path.name != ".gitkeep":
            path.unlink()

    for path in CARDS_DIR.iterdir():
        if path.is_file() and path.name != ".gitkeep":
            path.unlink()

    logger.warning("All submissions and images were reset")


def delete_submissions(ids: list[str]) -> list[dict[str, Any]]:
    """Delete selected records and their image files."""
    id_set = {str(item).strip().upper() for item in ids if str(item).strip()}
    if not id_set:
        return []

    with LOCK:
        records = _read_records()
        kept = []
        deleted = []

        for record in records:
            if str(record.get("id", "")).upper() in id_set:
                deleted.append(record)
            else:
                kept.append(record)

        _write_records(kept)

    for record in deleted:
        image = record.get("image", "")
        path = safe_image_path(image)
        if path.exists() and path.is_file():
            path.unlink()

        card = record.get("card", "")
        card_path = safe_card_path(card)
        if card_path.exists() and card_path.is_file():
            card_path.unlink()

    logger.warning("Deleted %s selected submissions", len(deleted))
    return deleted
