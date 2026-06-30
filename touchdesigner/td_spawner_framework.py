# pyright: reportUndefinedVariable=false
"""
Coune Labworks Birthday Installation - TouchDesigner spawner framework.

Use this script inside a Text DAT named `spawner`.

It does four jobs:
1. Polls the local web server database.
2. Writes database / queue / active / stats Table DATs for visibility.
3. Maintains a bounded queue and active lifecycle.
4. Drives a fixed pool of visual item COMPs for name, message, and photo.

Expected TouchDesigner network inside `/project1/submission_controller`:

- spawner                Text DAT containing this script
- execute_spawner        Execute DAT, Frame Start enabled
- database_table         Table DAT
- queue_table            Table DAT
- active_table           Table DAT
- stats_table            Table DAT
- spawner_pool           Base COMP, holds runtime item copies

Expected template COMP:

- /project1/submission_template

Recommended children inside each spawned item:

- name_text              Text TOP, Text COMP, or any OP with `text` parameter
- message_text           Text TOP, Text COMP, or any OP with `text` parameter
- photo                  Movie File In TOP or any OP with `file` parameter
- opacity                Level TOP, Constant CHOP, or any OP with `opacity` parameter

Call from Execute DAT:

def onFrameStart(frame):
    op("spawner").module.onFrameStart(frame)
    return
"""

from collections import deque
from dataclasses import dataclass
import json
import math
from pathlib import Path
import random
import shutil
import time
from urllib.parse import urlencode
from urllib.request import urlopen


SERVER_URL = "http://127.0.0.1:8080"
IMAGE_ROOT = r"C:\Users\PC\Documents\gilang-stuff\PROJ_TouchDesigner-stuff\HBD-SuRyA-PaLoH\data\images"
CARD_ROOT = r"C:\Users\PC\Documents\gilang-stuff\PROJ_TouchDesigner-stuff\HBD-SuRyA-PaLoH\data\cards"
IMAGE_CACHE_ROOT = r"C:\Users\PC\Documents\IMAGES_CACHING"
OSC_IN_PORT = 9001
OSC_SUBMISSION_ADDRESS = "/birthday/submission"

CONTROLLER_PATH = "/project1/submission_controller"
TEMPLATE_PATH = "/project1/submission_template"
POOL_PARENT_NAME = "spawner_pool"

DATABASE_TABLE = "database_table"
QUEUE_TABLE = "queue_table"
ACTIVE_TABLE = "active_table"
STATS_TABLE = "stats_table"

MAX_ACTIVE_ITEMS = 20
MAX_DATABASE_ROWS = 500
POLL_INTERVAL_SECONDS = 1.25
SHUFFLE_INTERVAL_SECONDS = 60.0
ITEM_LIFETIME_SECONDS = 180.0
FADE_IN_SECONDS = 2.0
FADE_OUT_SECONDS = 4.0

CANVAS_WIDTH = 1920
CANVAS_HEIGHT = 1080
ENTRY_WIDTH = 1600
ENTRY_HEIGHT = 900
CARD_WIDTH = 320
CARD_HEIGHT = 180
NEW_ENTRY_RATIO = 0.75
FLOW_SPEED_PIXELS_PER_SECOND = 25.0
RANDOM_DRIFT_PIXELS = 60.0
TARGET_EASE_PER_SECOND = 0.7
MIN_CARD_SCALE = 0.1
MAX_CARD_SCALE = 0.13


@dataclass
class Submission:
    id: str
    timestamp: str
    name: str
    message: str
    image: str
    card: str = ""
    device: str = ""

    @classmethod
    def from_record(cls, record):
        return cls(
            id=str(record.get("id", "")),
            timestamp=str(record.get("timestamp", "")),
            name=str(record.get("name", "")),
            message=str(record.get("message", "")),
            image=str(record.get("image", "")),
            card=str(record.get("card", "")),
            device=str(record.get("device", "")),
        )

    def image_path(self):
        return self.display_image_path()

    def raw_image_path(self):
        return self.cached_local_path(self.image, IMAGE_ROOT)

    def display_image_path(self):
        if self.card:
            return self.cached_local_path(self.card, CARD_ROOT)
        return self.raw_image_path()

    def cached_local_path(self, filename, root):
        source = Path(root) / filename
        cache = Path(IMAGE_CACHE_ROOT) / filename

        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            if source.exists():
                if not cache.exists() or source.stat().st_mtime > cache.stat().st_mtime:
                    shutil.copy2(str(source), str(cache))
                return str(cache).replace("\\", "/")
        except Exception:
            pass

        return str(source).replace("\\", "/")

    def image_url(self):
        return SERVER_URL.rstrip("/") + "/images/" + self.image

    def card_url(self):
        if self.card:
            return SERVER_URL.rstrip("/") + "/cards/" + self.card
        return self.image_url()

    def has_local_image(self):
        filename = self.card or self.image
        root = CARD_ROOT if self.card else IMAGE_ROOT
        source = Path(root) / filename
        cache = Path(IMAGE_CACHE_ROOT) / filename
        return source.exists() or cache.exists()


@dataclass
class ActiveItem:
    submission: Submission
    spawned_at: float
    slot: int
    comp_path: str = ""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    scale: float = 1.0
    opacity: float = 0.0
    target_x: float = 0.0
    target_y: float = 0.0
    target_z: float = 0.0
    target_scale: float = 1.0

    @property
    def id(self):
        return self.submission.id

    @property
    def age(self):
        return time.time() - self.spawned_at


class BirthdaySpawner:
    def __init__(self):
        self.server_url = SERVER_URL.rstrip("/")
        self.last_id = ""
        self.last_poll = 0.0
        self.last_shuffle = 0.0
        self.database = []
        self.seen_ids = set()
        self.queue = deque()
        self.active = []
        self.pool = []
        self.comp_to_item = {}
        self.enabled = True
        self.last_error = ""
        self.last_sync_status = "waiting"
        self.last_update_time = time.time()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def update(self):
        if not self.enabled:
            return

        self.ensure_pool()

        now = time.time()
        if now - self.last_poll >= POLL_INTERVAL_SECONDS:
            self.poll_new_submissions()
            self.last_poll = now

        self.recycle_expired_items()
        self.spawn_queued_items()

        if now - self.last_shuffle >= SHUFFLE_INTERVAL_SECONDS:
            self.shuffle_active_items()
            self.last_shuffle = now

        self.update_active_items()
        self.write_tables()

    def manual_refresh(self):
        self.ensure_pool()
        for item in list(self.active):
            self.release_item(item)
        self.active.clear()
        self.queue.clear()
        self.comp_to_item.clear()
        self.seen_ids.clear()
        self.last_id = ""
        self.poll_all_submissions()
        self.seed_weighted_queue()
        self.spawn_queued_items(force_visible=True)
        self.shuffle_active_items()
        self.update_active_items()
        self.write_tables()

    def hard_refresh(self):
        """Full rebuild from backend after admin reset/delete/re-entry."""
        self.reset_runtime()
        self.ensure_pool()
        self.poll_all_submissions()
        self.seed_weighted_queue()
        self.spawn_queued_items(force_visible=True)
        self.shuffle_active_items()
        self.update_active_items()
        self.write_tables()

    def reset_runtime(self):
        for item in list(self.active):
            self.release_item(item)
        self.active.clear()
        self.queue.clear()
        self.comp_to_item.clear()
        self.pool.clear()
        self.database.clear()
        self.seen_ids.clear()
        self.last_id = ""
        self.last_error = ""
        self.last_sync_status = "reset"
        self.last_update_time = time.time()
        self.write_tables()

    def clear_pool_cache(self):
        self.pool.clear()
        self.comp_to_item.clear()

    def seed_weighted_queue(self):
        valid = [submission for submission in self.database if submission.has_local_image()]
        if not valid:
            return

        newest_count = max(1, int(MAX_ACTIVE_ITEMS * NEW_ENTRY_RATIO))
        newest = list(reversed(valid[-newest_count:]))
        newest_ids = {submission.id for submission in newest}
        older = [submission for submission in valid if submission.id not in newest_ids]
        random_count = max(0, MAX_ACTIVE_ITEMS - len(newest))
        random_items = random.sample(older, min(random_count, len(older))) if older else []

        selected = newest + random_items
        self.queue.clear()
        self.queue.extend(selected[:MAX_ACTIVE_ITEMS])
        self.seen_ids.update(submission.id for submission in selected)

    # ------------------------------------------------------------------
    # Server sync
    # ------------------------------------------------------------------

    def poll_all_submissions(self):
        payload = self.fetch_json("/api/submissions")
        if not payload or not payload.get("ok"):
            return

        records = payload.get("submissions", [])
        self.database = [Submission.from_record(record) for record in records][-MAX_DATABASE_ROWS:]
        self.seen_ids = {submission.id for submission in self.database if submission.id}
        self.last_id = self.database[-1].id if self.database else ""

        self.last_sync_status = "full_sync_ok"

    def poll_new_submissions(self):
        query = urlencode({"since": self.last_id}) if self.last_id else ""
        path = "/api/submissions/latest" + (("?" + query) if query else "")
        payload = self.fetch_json(path)
        if not payload or not payload.get("ok"):
            return

        for record in payload.get("submissions", []):
            self.ingest_submission_record(record, source="poll")

        self.last_sync_status = "latest_sync_ok"

    def ingest_submission_record(self, record, source="unknown"):
        submission = Submission.from_record(record)
        if not submission.id or submission.id in self.seen_ids:
            return False

        self.seen_ids.add(submission.id)
        self.database.append(submission)
        self.database = self.database[-MAX_DATABASE_ROWS:]
        if submission.has_local_image():
            self.queue.append(submission)
            self.last_sync_status = "{}_entry_queued".format(source)
        else:
            self.last_error = "Skipped missing image for {}: {}".format(
                submission.id,
                submission.image,
            )
            self.last_sync_status = "{}_missing_image".format(source)
        self.last_id = submission.id
        return True

    def ingest_osc_payload(self, payload):
        try:
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            if isinstance(payload, str):
                record = json.loads(payload)
            elif isinstance(payload, dict):
                record = payload
            else:
                self.last_error = "OSC payload ignored: unsupported type {}".format(type(payload).__name__)
                self.last_sync_status = "osc_ignored"
                return False
        except Exception as err:
            self.last_error = "OSC payload parse failed: {}".format(err)
            self.last_sync_status = "osc_error"
            return False

        accepted = self.ingest_submission_record(record, source="osc")
        if accepted:
            self.ensure_pool()
            self.recycle_expired_items()
            self.spawn_queued_items()
            self.update_active_items()
            self.write_tables()
        return accepted

    def fetch_json(self, path):
        url = self.server_url + path
        try:
            with urlopen(url, timeout=1.0) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as err:
            self.last_error = "{}: {}".format(path, err)
            self.last_sync_status = "error"
            return None

    # ------------------------------------------------------------------
    # Queue, lifecycle, tunnel remap
    # ------------------------------------------------------------------

    def spawn_queued_items(self, force_visible=False):
        while self.queue:
            if len(self.active) >= MAX_ACTIVE_ITEMS:
                oldest = self.active.pop(0)
                self.release_item(oldest)

            submission = self.queue.popleft()
            item = ActiveItem(
                submission=submission,
                spawned_at=time.time() - (FADE_IN_SECONDS if force_visible else 0),
                slot=len(self.active),
            )
            self.assign_tunnel_slot(item, item.slot, hard=True)
            self.bind_item_to_pool_comp(item)
            self.active.append(item)

        self.blank_unused_pool_slots()

    def recycle_expired_items(self):
        if not self.queue:
            return

        free_slots = max(0, MAX_ACTIVE_ITEMS - len(self.active))
        needed_slots = max(0, min(len(self.queue), MAX_ACTIVE_ITEMS) - free_slots)
        if needed_slots <= 0:
            return

        survivors = []
        released = 0
        for item in self.active:
            if item.age >= ITEM_LIFETIME_SECONDS and released < needed_slots:
                self.release_item(item)
                released += 1
            else:
                survivors.append(item)
        self.active = survivors

    def shuffle_active_items(self):
        random.shuffle(self.active)
        for index, item in enumerate(self.active):
            self.assign_tunnel_slot(item, index, hard=False)

    def assign_tunnel_slot(self, item, index, hard=False):
        columns = 5
        rows = 4
        col = index % columns
        row = index // columns
        cell_w = CANVAS_WIDTH / columns
        cell_h = CANVAS_HEIGHT / rows

        base_x = (col + 0.5) * cell_w
        base_y = (row + 0.5) * cell_h

        item.slot = index
        item.target_x = base_x + random.uniform(-cell_w * 0.22, cell_w * 0.22)
        item.target_y = base_y + random.uniform(-cell_h * 0.18, cell_h * 0.18)
        item.target_z = 0
        item.target_scale = random.uniform(MIN_CARD_SCALE, MAX_CARD_SCALE)

        if hard:
            item.x = item.target_x
            item.y = CANVAS_HEIGHT + CARD_HEIGHT + random.uniform(0, 280)
            item.z = item.target_z
            item.scale = item.target_scale

    def update_active_items(self):
        now = time.time()
        dt = max(0.0, min(0.1, now - self.last_update_time))
        self.last_update_time = now
        ease = min(1.0, TARGET_EASE_PER_SECOND * dt)

        for item in self.active:
            age = item.age
            remaining = ITEM_LIFETIME_SECONDS - age
            fade_in = min(1.0, age / FADE_IN_SECONDS)
            fade_out = min(1.0, max(0.0, remaining / FADE_OUT_SECONDS))
            item.opacity = max(0.0, min(1.0, fade_in, fade_out))

            item.x += (item.target_x - item.x) * ease
            item.y -= FLOW_SPEED_PIXELS_PER_SECOND * dt
            item.y += (item.target_y - item.y) * ease
            item.z += (item.target_z - item.z) * ease
            item.scale += (item.target_scale - item.scale) * ease

            if item.y < -CARD_HEIGHT * 0.6:
                item.y = CANVAS_HEIGHT + CARD_HEIGHT
                item.target_y = random.uniform(CARD_HEIGHT, CANVAS_HEIGHT - CARD_HEIGHT)
                item.target_x = random.uniform(CARD_WIDTH, CANVAS_WIDTH - CARD_WIDTH)

            if random.random() < 0.002:
                item.target_x = max(
                    CARD_WIDTH * 0.5,
                    min(
                        CANVAS_WIDTH - CARD_WIDTH * 0.5,
                        item.target_x + random.uniform(-RANDOM_DRIFT_PIXELS, RANDOM_DRIFT_PIXELS),
                    ),
                )

            self.apply_item_to_comp(item)

    # ------------------------------------------------------------------
    # Pool spawner
    # ------------------------------------------------------------------

    def ensure_pool(self):
        if (
            self.pool
            and len(self.pool) >= MAX_ACTIVE_ITEMS
            and all(self.safe_op(comp.path) for comp in self.pool[:MAX_ACTIVE_ITEMS])
        ):
            return

        pool_parent = self.pool_parent()
        template = self.template_comp()
        if not pool_parent or not template:
            return

        active_paths = {item.comp_path for item in self.active if item.comp_path}
        refreshed_pool = []
        for index in range(MAX_ACTIVE_ITEMS):
            name = "submission_{:02d}".format(index + 1)
            comp = pool_parent.op(name)
            if not comp:
                try:
                    comp = pool_parent.copy(template, name=name)
                except Exception as err:
                    self.last_error = "pool copy failed: {}".format(err)
                    return
            if comp.path not in active_paths:
                self.clear_comp(comp)
                self.hide_comp(comp)
            refreshed_pool.append(comp)
        self.pool = refreshed_pool

    def bind_item_to_pool_comp(self, item):
        comp = self.next_free_comp()
        if not comp:
            self.last_error = "No free pool comp for {}".format(item.id)
            return

        item.comp_path = comp.path
        self.comp_to_item[comp.path] = item
        self.show_comp(comp)
        self.apply_static_data(comp, item.submission)
        self.apply_item_to_comp(item)

    def next_free_comp(self):
        active_paths = {item.comp_path for item in self.active if item.comp_path}
        for comp in self.pool:
            if comp.path not in active_paths:
                return comp
        return None

    def release_item(self, item):
        comp = self.safe_op(item.comp_path)
        if comp:
            self.clear_comp(comp)
            self.hide_comp(comp)
        if item.comp_path in self.comp_to_item:
            del self.comp_to_item[item.comp_path]
        item.comp_path = ""

    def blank_unused_pool_slots(self):
        active_paths = {item.comp_path for item in self.active if item.comp_path}
        for comp in self.pool:
            if comp.path not in active_paths:
                self.clear_comp(comp)
                self.hide_comp(comp)

    # ------------------------------------------------------------------
    # Operator writing helpers
    # ------------------------------------------------------------------

    def apply_static_data(self, comp, submission):
        self.configure_display_card_comp(comp)
        self.set_text_child(comp, "name_text", "")
        self.set_text_child(comp, "message_text", "")
        self.set_file_child(comp, "photo", submission.display_image_path())

        self.set_custom_or_param(comp, "Entryid", submission.id)
        self.set_custom_or_param(comp, "Sendername", submission.name)
        self.set_custom_or_param(comp, "Message", submission.message)
        self.set_custom_or_param(comp, "Imagepath", submission.display_image_path())
        self.set_custom_or_param(comp, "Imageurl", submission.card_url())
        self.set_custom_or_param(comp, "Rawimagepath", submission.raw_image_path())
        self.set_custom_or_param(comp, "Rawimageurl", submission.image_url())
        self.set_custom_or_param(comp, "Cardpath", submission.display_image_path())

    def configure_display_card_comp(self, comp):
        for child_name in ("photo", "fit_photo", "level_photo", "photo_layout", "composite_card", "final_level", "out1"):
            child = comp.op(child_name) if comp else None
            if child:
                self.set_resolution(child, ENTRY_WIDTH, ENTRY_HEIGHT)

        fit_photo = comp.op("fit_photo") if comp else None
        if fit_photo:
            self.set_par(fit_photo, "fit", "fit")
            self.set_par(fit_photo, "justifyx", "center")
            self.set_par(fit_photo, "justifyy", "center")

        photo = comp.op("photo_layout") if comp else None
        out1 = comp.op("out1") if comp else None
        if photo and out1:
            self.connect_input(out1, photo, 0)

    def apply_item_to_comp(self, item):
        comp = self.safe_op(item.comp_path)
        if not comp:
            return

        self.set_transform(comp, item)
        self.set_opacity(comp, item.opacity)
        self.set_custom_or_param(comp, "Posx", round(item.x, 3))
        self.set_custom_or_param(comp, "Posy", round(item.y, 3))
        self.set_custom_or_param(comp, "Cardsx", round(item.scale, 4))
        self.set_custom_or_param(comp, "Cardsy", round(item.scale, 4))
        self.set_custom_or_param(comp, "Opacity", item.opacity)
        self.set_custom_or_param(comp, "Age", round(item.age, 3))

    def clear_comp(self, comp):
        self.set_text_child(comp, "name_text", "")
        self.set_text_child(comp, "message_text", "")
        self.set_file_child(comp, "photo", "")
        self.set_opacity(comp, 0)
        self.set_custom_or_param(comp, "Posx", 0)
        self.set_custom_or_param(comp, "Posy", 0)
        self.set_custom_or_param(comp, "Cardsx", 0)
        self.set_custom_or_param(comp, "Cardsy", 0)
        self.set_custom_or_param(comp, "Opacity", 0)

    def set_transform(self, comp, item):
        for par_name, value in (
            ("tx", item.x),
            ("ty", item.y),
            ("tz", item.z),
            ("sx", item.scale),
            ("sy", item.scale),
            ("sz", item.scale),
        ):
            self.set_par(comp, par_name, value)

    def set_text_child(self, comp, child_name, value):
        child = comp.op(child_name) if comp else None
        if child:
            self.set_par(child, "text", value)
            self.set_par(child, "value0", value)
            self.force_cook(child)

    def set_file_child(self, comp, child_name, value):
        child = comp.op(child_name) if comp else None
        if child:
            normalized = str(value).replace("\\", "/")
            self.set_par(child, "file", normalized)
            self.set_par(child, "filename", normalized)
            self.set_par(child, "image", normalized)
            self.pulse_par(child, "reload")
            self.pulse_par(child, "reloadpulse")
            self.pulse_par(child, "cuepulse")
            self.force_cook(child)

    def set_opacity(self, comp, value):
        self.set_par(comp, "opacity", value)
        self.set_par(comp, "alpha", value)

        opacity_child = comp.op("opacity") if comp else None
        if opacity_child:
            self.set_par(opacity_child, "opacity", value)
            self.set_par(opacity_child, "alpha", value)
            self.set_par(opacity_child, "value0", value)

        final_level = comp.op("final_level") if comp else None
        if final_level:
            self.set_par(final_level, "opacity", value)
            self.set_par(final_level, "alpha", value)
            self.force_cook(final_level)

    def set_custom_or_param(self, comp, par_name, value):
        if not comp:
            return
        if self.set_par(comp, par_name, value):
            return

        # Custom parameters are optional. If they don't exist, child operators still receive data.
        try:
            page = comp.appendCustomPage("Submission")
            if isinstance(value, (int, float, bool)):
                page.appendFloat(par_name)
            else:
                page.appendStr(par_name)
            self.set_par(comp, par_name, value)
        except Exception:
            pass

    def set_par(self, target, par_name, value):
        try:
            par = getattr(target.par, par_name)
            par.val = value
            return True
        except Exception:
            return False

    def set_resolution(self, target, width, height):
        for value in ("custom", "Custom", 9, 8, 1):
            if self.set_par(target, "outputresolution", value):
                break

        success = False
        for x_name, y_name in (
            ("resolutionw", "resolutionh"),
            ("resolution1", "resolution2"),
            ("resw", "resh"),
            ("res1", "res2"),
            ("sizex", "sizey"),
            ("w", "h"),
            ("width", "height"),
        ):
            ok_x = self.set_par(target, x_name, width)
            ok_y = self.set_par(target, y_name, height)
            success = success or (ok_x and ok_y)
        return success

    def connect_input(self, target, source, input_index=0):
        try:
            target.setInput(input_index, source)
            return True
        except Exception:
            pass
        try:
            target.inputConnectors[input_index].connect(source)
            return True
        except Exception:
            return False

    def pulse_par(self, target, par_name):
        try:
            getattr(target.par, par_name).pulse()
            return True
        except Exception:
            return False

    def force_cook(self, target):
        try:
            target.cook(force=True)
            return True
        except Exception:
            return False

    def show_comp(self, comp):
        self.set_par(comp, "display", True)
        self.set_par(comp, "render", True)
        self.set_par(comp, "bypass", False)

    def hide_comp(self, comp):
        self.set_par(comp, "display", False)
        self.set_par(comp, "render", False)
        self.set_par(comp, "bypass", True)

    # ------------------------------------------------------------------
    # Table output: database, queue, active, stats
    # ------------------------------------------------------------------

    def write_tables(self):
        self.write_database_table()
        self.write_queue_table()
        self.write_active_table()
        self.write_stats_table()

    def write_database_table(self):
        table = self.safe_op(DATABASE_TABLE)
        if not table:
            return

        table.clear()
        table.appendRow(["id", "timestamp", "name", "message", "image", "raw_image_path", "card", "display_image_path", "device"])
        for submission in self.database:
            table.appendRow(
                [
                    submission.id,
                    submission.timestamp,
                    submission.name,
                    submission.message,
                    submission.image,
                    submission.raw_image_path(),
                    submission.card,
                    submission.display_image_path(),
                    submission.device,
                ]
            )

    def write_queue_table(self):
        table = self.safe_op(QUEUE_TABLE)
        if not table:
            return

        table.clear()
        table.appendRow(["queue_index", "id", "name", "message", "display_image_path", "raw_image_path"])
        for index, submission in enumerate(self.queue):
            table.appendRow([index, submission.id, submission.name, submission.message, submission.display_image_path(), submission.raw_image_path()])

    def write_active_table(self):
        table = self.safe_op(ACTIVE_TABLE)
        if not table:
            return

        table.clear()
        table.appendRow(
            [
                "slot",
                "id",
                "name",
                "message",
                "display_image_path",
                "raw_image_path",
                "comp",
                "age",
                "opacity",
                "x",
                "y",
                "z",
                "scale",
            ]
        )
        for item in self.active:
            table.appendRow(
                [
                    item.slot,
                    item.id,
                    item.submission.name,
                    item.submission.message,
                    item.submission.display_image_path(),
                    item.submission.raw_image_path(),
                    item.comp_path,
                    round(item.age, 3),
                    round(item.opacity, 3),
                    round(item.x, 3),
                    round(item.y, 3),
                    round(item.z, 3),
                    round(item.scale, 3),
                ]
            )

    def write_stats_table(self):
        table = self.safe_op(STATS_TABLE)
        if not table:
            return

        table.clear()
        table.appendRow(["metric", "value"])
        table.appendRow(["enabled", self.enabled])
        table.appendRow(["server_url", self.server_url])
        table.appendRow(["database_count", len(self.database)])
        table.appendRow(["queue_count", len(self.queue)])
        table.appendRow(["active_count", len(self.active)])
        table.appendRow(["pool_count", len(self.pool)])
        table.appendRow(["last_id", self.last_id])
        table.appendRow(["last_sync_status", self.last_sync_status])
        table.appendRow(["last_error", self.last_error])

    # ------------------------------------------------------------------
    # TouchDesigner lookup helpers
    # ------------------------------------------------------------------

    def safe_op(self, path):
        if not path:
            return None
        try:
            found = op(path)
            if found:
                return found
        except Exception:
            pass

        if not str(path).startswith("/"):
            try:
                return op(CONTROLLER_PATH + "/" + str(path))
            except Exception:
                return None

        return None

    def pool_parent(self):
        existing = self.safe_op(POOL_PARENT_NAME)
        if existing:
            return existing

        try:
            owner = self.safe_op(CONTROLLER_PATH) or parent()
            existing = owner.op(POOL_PARENT_NAME)
            if existing:
                return existing
            return owner.create(baseCOMP, POOL_PARENT_NAME)
        except Exception as err:
            self.last_error = "pool parent missing: {}".format(err)
            return None

    def template_comp(self):
        template = self.safe_op(TEMPLATE_PATH)
        if template:
            return template
        template = self.safe_op("../submission_template")
        if template:
            return template
        template = self.safe_op("submission_template")
        if template:
            return template
        self.last_error = "Template not found: {}".format(TEMPLATE_PATH)
        return None


spawner = BirthdaySpawner()


def onFrameStart(frame):
    spawner.update()
    return


def manualRefresh():
    spawner.manual_refresh()


def hardRefresh():
    spawner.hard_refresh()


def resetRuntime():
    spawner.reset_runtime()


def onOscSubmission(payload):
    return spawner.ingest_osc_payload(payload)


def setServerUrl(url):
    spawner.server_url = str(url).rstrip("/")
    spawner.reset_runtime()


def setEnabled(value):
    spawner.enabled = bool(value)
