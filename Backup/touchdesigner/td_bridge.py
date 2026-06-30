"""
TouchDesigner bridge for the Coune Labworks birthday installation.

Paste this into a Text DAT, or import it from a project folder.
It has no third-party dependencies and uses polling for robust local operation.

Recommended TouchDesigner network:
- /project1/submission_controller: Base COMP
- /project1/submission_controller/bridge: Text DAT with this script
- /project1/submission_controller/active_table: Table DAT
- /project1/submission_controller/queue_table: Table DAT
- /project1/submission_template: Base COMP template for one visual card
"""

from collections import deque
from dataclasses import dataclass, field
import json
import math
import random
import time
from urllib.parse import urlencode
from urllib.request import urlopen


SERVER_URL = "http://127.0.0.1:8080"
IMAGE_ROOT = "../data/images"

MAX_ACTIVE_ITEMS = 18
ITEM_LIFETIME_SECONDS = 32.0
FADE_IN_SECONDS = 2.0
FADE_OUT_SECONDS = 4.0
POLL_INTERVAL_SECONDS = 1.5
SHUFFLE_INTERVAL_SECONDS = 12.0

TUNNEL_WIDTH = 28.0
TUNNEL_HEIGHT = 12.0
TUNNEL_DEPTH_MIN = -6.0
TUNNEL_DEPTH_MAX = 18.0


@dataclass
class VisualItem:
    id: str
    name: str
    message: str
    image: str
    timestamp: str
    spawned_at: float
    slot: int = 0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    scale: float = 1.0
    opacity: float = 0.0
    target_x: float = 0.0
    target_y: float = 0.0
    target_z: float = 0.0
    target_scale: float = 1.0
    extra: dict = field(default_factory=dict)

    @property
    def age(self):
        return time.time() - self.spawned_at

    def image_path(self):
        return IMAGE_ROOT.rstrip("/\\") + "/" + self.image


class BirthdayTDController:
    def __init__(self, server_url=SERVER_URL):
        self.server_url = server_url.rstrip("/")
        self.max_active = MAX_ACTIVE_ITEMS
        self.poll_interval = POLL_INTERVAL_SECONDS
        self.shuffle_interval = SHUFFLE_INTERVAL_SECONDS
        self.item_lifetime = ITEM_LIFETIME_SECONDS
        self.last_id = ""
        self.last_poll = 0.0
        self.last_shuffle = 0.0
        self.active = []
        self.queue = deque()
        self.seen_ids = set()
        self.enabled = True

    # ------------------------------------------------------------------
    # Public update loop
    # ------------------------------------------------------------------

    def update(self):
        """Call this every frame from an Execute DAT."""
        if not self.enabled:
            return

        now = time.time()
        if now - self.last_poll >= self.poll_interval:
            self.poll()
            self.last_poll = now

        self.recycle_expired()
        self.spawn_from_queue()

        if now - self.last_shuffle >= self.shuffle_interval:
            self.shuffle_active()
            self.last_shuffle = now

        self.update_lifecycle()
        self.write_debug_tables()

    def manual_refresh(self):
        self.poll(force=True)
        self.spawn_from_queue()
        self.shuffle_active()

    def reset_runtime(self):
        for item in list(self.active):
            self.on_remove(item)
        self.active = []
        self.queue.clear()
        self.seen_ids.clear()
        self.last_id = ""
        self.last_poll = 0.0
        self.last_shuffle = 0.0
        self.write_debug_tables()

    # ------------------------------------------------------------------
    # Data sync
    # ------------------------------------------------------------------

    def poll(self, force=False):
        endpoint = "/api/submissions/latest"
        query = urlencode({"since": self.last_id}) if self.last_id and not force else ""
        url = self.server_url + endpoint + (("?" + query) if query else "")

        try:
            with urlopen(url, timeout=1.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as err:
            self.on_error("poll_failed", err)
            return

        if not payload.get("ok"):
            return

        for record in payload.get("submissions", []):
            if record.get("id") in self.seen_ids:
                continue
            self.seen_ids.add(record.get("id"))
            self.last_id = record.get("id", self.last_id)
            self.queue.append(record)

    # ------------------------------------------------------------------
    # Population control
    # ------------------------------------------------------------------

    def spawn_from_queue(self):
        while self.queue and len(self.active) < self.max_active:
            record = self.queue.popleft()
            item = VisualItem(
                id=record.get("id", ""),
                name=record.get("name", ""),
                message=record.get("message", ""),
                image=record.get("image", ""),
                timestamp=record.get("timestamp", ""),
                spawned_at=time.time(),
            )
            self.assign_slot(item, len(self.active))
            self.active.append(item)
            self.on_spawn(item)

    def recycle_expired(self):
        survivors = []
        for item in self.active:
            if item.age >= self.item_lifetime:
                self.on_remove(item)
            else:
                survivors.append(item)
        self.active = survivors

    def shuffle_active(self):
        random.shuffle(self.active)
        for index, item in enumerate(self.active):
            self.assign_slot(item, index)
            self.on_shuffle(item)

    def assign_slot(self, item, index):
        angle = (index / max(1, self.max_active)) * math.tau
        ring = 0.5 + random.random() * 0.5
        depth = random.uniform(TUNNEL_DEPTH_MIN, TUNNEL_DEPTH_MAX)

        item.slot = index
        item.target_x = math.cos(angle) * TUNNEL_WIDTH * 0.5 * ring
        item.target_y = math.sin(angle) * TUNNEL_HEIGHT * 0.5 * ring
        item.target_z = depth
        item.target_scale = max(0.55, 1.25 - depth * 0.03)

        if item.age < 0.1:
            item.x = item.target_x
            item.y = item.target_y
            item.z = item.target_z
            item.scale = item.target_scale

    def update_lifecycle(self):
        now = time.time()
        for item in self.active:
            age = now - item.spawned_at
            remaining = self.item_lifetime - age

            fade_in = min(1.0, age / FADE_IN_SECONDS)
            fade_out = min(1.0, max(0.0, remaining / FADE_OUT_SECONDS))
            item.opacity = max(0.0, min(1.0, fade_in, fade_out))

            # Smooth remap instead of hard teleporting when shuffled.
            item.x += (item.target_x - item.x) * 0.045
            item.y += (item.target_y - item.y) * 0.045
            item.z += (item.target_z - item.z) * 0.045
            item.scale += (item.target_scale - item.scale) * 0.045

            self.on_update(item)

    # ------------------------------------------------------------------
    # TouchDesigner integration hooks
    # ------------------------------------------------------------------

    def on_spawn(self, item):
        """
        Replace this with project-specific instancing logic.

        Suggested:
        - copy /project1/submission_template into /project1/submissions
        - set custom pars: Name, Message, Imagepath, Entryid
        - set initial transform from item.x/y/z/scale
        """
        pass

    def on_update(self, item):
        """
        Update COMP transform, opacity, and text/photo parameters.
        This runs every frame for every active item.
        """
        pass

    def on_shuffle(self, item):
        """Optional hook for triggering small animation accents on remap."""
        pass

    def on_remove(self, item):
        """Destroy or recycle the item's TouchDesigner COMP."""
        pass

    def on_error(self, label, err):
        print("BirthdayTDController", label, err)

    # ------------------------------------------------------------------
    # Debug tables
    # ------------------------------------------------------------------

    def write_debug_tables(self):
        """If active_table and queue_table exist beside this DAT, keep them updated."""
        try:
            active_table = op("active_table")
            if active_table:
                active_table.clear()
                active_table.appendRow(["id", "name", "message", "image", "opacity", "x", "y", "z", "scale"])
                for item in self.active:
                    active_table.appendRow(
                        [
                            item.id,
                            item.name,
                            item.message,
                            item.image_path(),
                            round(item.opacity, 3),
                            round(item.x, 3),
                            round(item.y, 3),
                            round(item.z, 3),
                            round(item.scale, 3),
                        ]
                    )

            queue_table = op("queue_table")
            if queue_table:
                queue_table.clear()
                queue_table.appendRow(["id", "name", "message", "image"])
                for record in list(self.queue):
                    queue_table.appendRow(
                        [
                            record.get("id", ""),
                            record.get("name", ""),
                            record.get("message", ""),
                            record.get("image", ""),
                        ]
                    )
        except Exception:
            pass


controller = BirthdayTDController()


def onFrameStart(frame):
    """Use this from an Execute DAT Frame Start callback."""
    controller.update()
    return


def manualRefresh():
    controller.manual_refresh()


def resetRuntime():
    controller.reset_runtime()
