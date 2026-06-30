"""Render a Python word cloud image from saved birthday messages."""

from collections import Counter
import re
from typing import Any

from PIL import Image, ImageDraw, ImageFont

try:
    from config import WORDCLOUD_FILE
    from storage import logger
except ModuleNotFoundError:
    from .config import WORDCLOUD_FILE
    from .storage import logger

try:
    from wordcloud import WordCloud
except Exception:  # pragma: no cover - fallback keeps event server usable.
    WordCloud = None


WIDTH = 1920
HEIGHT = 1080
BACKGROUND = (0, 27, 85)
ACCENT_YELLOW = (255, 178, 0)
ACCENT_RED = (255, 0, 0)
TEXT_WHITE = (255, 255, 255)
STOPWORDS = {
    "yang",
    "dan",
    "dari",
    "untuk",
    "dengan",
    "semoga",
    "selamat",
    "ulang",
    "tahun",
    "bapak",
    "pak",
    "ibu",
    "the",
    "and",
    "for",
    "you",
    "your",
    "wish",
    "wishes",
}


def render_wordcloud(records: list[dict[str, Any]]) -> bool:
    frequencies = message_frequencies(records)
    try:
        if WordCloud and frequencies:
            image = render_with_wordcloud(frequencies)
        else:
            image = render_fallback(frequencies)
        WORDCLOUD_FILE.parent.mkdir(parents=True, exist_ok=True)
        image.save(WORDCLOUD_FILE, format="PNG")
        logger.info("Word cloud rendered to %s", WORDCLOUD_FILE)
        return True
    except Exception as err:
        logger.warning("Word cloud render failed: %s", err)
        return False


def message_frequencies(records: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for record in records:
        message = str(record.get("message", "")).lower()
        for word in re.findall(r"[A-Za-zÀ-ÿ0-9]+", message):
            if len(word) < 4 or word in STOPWORDS:
                continue
            counts[word] += 1
    return counts


def render_with_wordcloud(frequencies: Counter[str]) -> Image.Image:
    font_path = "C:/Windows/Fonts/calibrib.ttf"
    cloud = WordCloud(
        width=WIDTH,
        height=HEIGHT,
        background_color=None,
        mode="RGBA",
        font_path=font_path,
        max_words=120,
        prefer_horizontal=0.88,
        color_func=word_color,
        collocations=True,
        contour_width=0,
        relative_scaling=0.55,
        random_state=2026,
    ).generate_from_frequencies(frequencies)

    image = render_background()
    image.alpha_composite(cloud.to_image())
    draw_title(image)
    return image.convert("RGB")


def render_fallback(frequencies: Counter[str]) -> Image.Image:
    image = render_background()
    draw_title(image)
    draw = ImageDraw.Draw(image, "RGBA")
    font_sizes = [104, 88, 76, 64, 56, 48, 42, 38]
    positions = [
        (260, 320),
        (980, 300),
        (610, 515),
        (1240, 570),
        (310, 710),
        (850, 760),
        (1320, 770),
        (520, 875),
    ]
    for index, (word, count) in enumerate(frequencies.most_common(len(positions))):
        font = load_font(font_sizes[min(index, len(font_sizes) - 1)])
        color = ACCENT_YELLOW if index % 3 == 0 else TEXT_WHITE
        draw.text(positions[index], word, fill=(*color, 235), font=font)

    if not frequencies:
        font = load_font(82)
        draw.text((590, 500), "Menunggu entry...", fill=(*TEXT_WHITE, 220), font=font)
    return image.convert("RGB")


def render_background() -> Image.Image:
    image = Image.new("RGBA", (WIDTH, HEIGHT), (*BACKGROUND, 255))
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rounded_rectangle((90, 90, WIDTH - 90, HEIGHT - 90), radius=56, outline=(*ACCENT_YELLOW, 180), width=5)
    draw.rectangle((120, 160, WIDTH - 120, 170), fill=(*ACCENT_RED, 200))
    return image


def draw_title(image: Image.Image) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    font = load_font(72)
    draw.text((140, 110), "TOP UCAPAN", fill=(*TEXT_WHITE, 255), font=font)


def word_color(*args, **kwargs) -> str:
    palette = ["#ffffff", "#ffb200", "#ff3a2f", "#f7d36a", "#d9e6ff"]
    word = str(args[0]) if args else ""
    return palette[sum(ord(char) for char in word) % len(palette)]


def load_font(size: int):
    for candidate in ("C:/Windows/Fonts/calibrib.ttf", "C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/segoeui.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()
