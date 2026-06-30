"""OSC notifications for pushing saved submissions to TouchDesigner."""

import json
from typing import Any

from config import TD_OSC_ADDRESS, TD_OSC_ENABLED, TD_OSC_HOST, TD_OSC_PORT
from storage import logger

try:
    from pythonosc.udp_client import SimpleUDPClient
except Exception:  # pragma: no cover - keeps HTTP fallback alive if dependency is missing.
    SimpleUDPClient = None


_client = None


def osc_status() -> dict[str, Any]:
    return {
        "enabled": TD_OSC_ENABLED,
        "host": TD_OSC_HOST,
        "port": TD_OSC_PORT,
        "address": TD_OSC_ADDRESS,
        "available": SimpleUDPClient is not None,
    }


def notify_submission(record: dict[str, Any]) -> bool:
    """Send a saved submission to TouchDesigner over OSC.

    The JSON database remains the source of truth. Returning False only means
    TouchDesigner should receive the same record through its polling fallback.
    """
    if not TD_OSC_ENABLED:
        return False

    client = osc_client()
    if not client:
        return False

    try:
        client.send_message(TD_OSC_ADDRESS, json.dumps(record, ensure_ascii=False))
        logger.info("OSC submission sent id=%s to %s:%s", record.get("id"), TD_OSC_HOST, TD_OSC_PORT)
        return True
    except Exception as err:
        logger.warning("OSC submission send failed id=%s: %s", record.get("id"), err)
        return False


def osc_client():
    global _client
    if _client:
        return _client

    if SimpleUDPClient is None:
        logger.warning("OSC disabled because python-osc is not installed")
        return None

    try:
        _client = SimpleUDPClient(TD_OSC_HOST, TD_OSC_PORT)
        return _client
    except Exception as err:
        logger.warning("OSC client setup failed for %s:%s: %s", TD_OSC_HOST, TD_OSC_PORT, err)
        return None
