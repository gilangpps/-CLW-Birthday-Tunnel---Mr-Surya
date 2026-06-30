"""Create demo submissions for TouchDesigner testing without mobile phones."""

import json
import random
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "submissions.json"
IMAGES_DIR = ROOT / "data" / "images"
LOCAL_TZ = timezone(timedelta(hours=7))

NAMES = [
    "Budi",
    "Maya",
    "Andi",
    "Rara",
    "Dimas",
    "Nadia",
    "Farhan",
    "Sinta",
    "Rizky",
    "Laras",
]

MESSAGES = [
    "Selamat ulang tahun, semoga sehat dan penuh keberkahan.",
    "Panjang umur, sukses selalu, dan terus menginspirasi.",
    "Semoga hari ini menjadi awal tahun yang semakin gemilang.",
    "Doa terbaik untuk kebahagiaan, kesehatan, dan kejayaan.",
    "Selamat ulang tahun. Semoga selalu diberi energi dan cahaya.",
    "Semoga setiap langkah membawa kebaikan untuk banyak orang.",
]

COLORS = [
    (217, 173, 85),
    (240, 213, 137),
    (82, 127, 196),
    (130, 94, 170),
    (230, 120, 92),
]


def main(count=12):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    records = read_records()
    for _ in range(count):
        submission_id = secrets.token_hex(3).upper()
        timestamp = datetime.now(LOCAL_TZ).isoformat(timespec="seconds")
        stamp = datetime.now(LOCAL_TZ).strftime("%Y%m%d_%H%M%S")
        name = random.choice(NAMES)
        message = random.choice(MESSAGES)
        filename = f"{stamp}_{submission_id}.jpg"

        create_demo_image(IMAGES_DIR / filename, name)
        records.append(
            {
                "id": submission_id,
                "timestamp": timestamp,
                "name": name,
                "message": message,
                "image": filename,
                "device": "demo-seed",
            }
        )

    DATA_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Created {count} demo submissions.")
    print(f"Database: {DATA_FILE}")


def read_records():
    if not DATA_FILE.exists():
        return []
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def create_demo_image(path, name):
    bg = random.choice(COLORS)
    img = Image.new("RGB", (720, 720), bg)
    draw = ImageDraw.Draw(img)

    initials = "".join(part[0] for part in name.split()[:2]).upper()
    try:
        font_big = ImageFont.truetype("arial.ttf", 180)
        font_small = ImageFont.truetype("arial.ttf", 42)
    except OSError:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw.ellipse((100, 100, 620, 620), fill=(7, 20, 38), outline=(255, 242, 210), width=8)
    draw_centered(draw, initials, font_big, (360, 330), (240, 213, 137))
    draw_centered(draw, name, font_small, (360, 520), (255, 242, 210))
    img.save(path, quality=92)


def draw_centered(draw, text, font, center, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    draw.text((center[0] - width / 2, center[1] - height / 2), text, font=font, fill=fill)


if __name__ == "__main__":
    main()
