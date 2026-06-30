"""Local-first backend for the Surya Paloh birthday installation."""

from io import BytesIO
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image, ImageDraw, ImageFont, ImageOps
import qrcode
from flask import Flask, abort, jsonify, request, send_file, send_from_directory

from config import ADMIN_TOKEN, CARDS_DIR, HOST, IMAGES_DIR, PORT, WEB_DIR, WORDCLOUD_FILE
from osc_notify import notify_submission, osc_status
from storage import (
    all_submissions,
    append_submission,
    delete_submissions,
    ensure_dirs,
    generate_id,
    logger,
    make_card_filename,
    make_image_filename,
    now_iso,
    reset_submissions,
    safe_card_path,
    safe_image_path,
    submission_count,
    submissions_since,
)
from validation import validate_image, validate_message, validate_name
from wordcloud_render import render_wordcloud

app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path="")


@app.route("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/thank-you")
def thank_you():
    return send_from_directory(WEB_DIR, "thank-you.html")


@app.route("/admin")
def admin():
    return send_from_directory(WEB_DIR, "admin.html")


@app.route("/qr")
def qr_display():
    return send_from_directory(WEB_DIR, "qr.html")


@app.route("/css/<path:filename>")
def css(filename):
    return send_from_directory(WEB_DIR / "css", filename)


@app.route("/js/<path:filename>")
def js(filename):
    return send_from_directory(WEB_DIR / "js", filename)


@app.route("/images/<path:filename>")
def image(filename):
    safe_name = filename.replace("\\", "/").split("/")[-1]
    path = safe_image_path(safe_name)
    if not path.exists():
        abort(404)
    return send_from_directory(IMAGES_DIR, safe_name)


@app.route("/cards/<path:filename>")
def card(filename):
    safe_name = filename.replace("\\", "/").split("/")[-1]
    path = safe_card_path(safe_name)
    if not path.exists():
        abort(404)
    return send_from_directory(CARDS_DIR, safe_name)


@app.route("/qr.png")
def qr_png():
    url = request.url_root.rstrip("/") + "/"
    img = qrcode.make(url)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png")


@app.route("/wordcloud.png")
def wordcloud_png():
    if not WORDCLOUD_FILE.exists():
        render_wordcloud(all_submissions())
    return send_file(WORDCLOUD_FILE, mimetype="image/png")


@app.route("/api/submit", methods=["POST"])
def submit():
    name_ok, name, name_error = validate_name(request.form.get("name", ""))
    if not name_ok:
        return jsonify({"ok": False, "error": name_error}), 400

    message_ok, message, message_error = validate_message(request.form.get("message", ""))
    if not message_ok:
        return jsonify({"ok": False, "error": message_error}), 400

    photo = request.files.get("photo")
    photo_bytes = photo.read() if photo else None
    image_ok, extension, image_error = validate_image(
        photo.filename if photo else None,
        photo.content_type if photo else None,
        photo_bytes,
    )
    if not image_ok:
        return jsonify({"ok": False, "error": image_error}), 400

    submission_id = generate_id()
    image_filename = make_image_filename(submission_id, extension)
    card_filename = make_card_filename(submission_id)
    safe_image_path(image_filename).write_bytes(photo_bytes)
    safe_card_path(card_filename).write_bytes(render_submission_card(photo_bytes, name, message))

    record = {
        "id": submission_id,
        "timestamp": now_iso(),
        "name": name,
        "message": message,
        "image": image_filename,
        "card": card_filename,
        "device": (request.form.get("device_info", "") or "")[:200],
    }
    append_submission(record)
    render_wordcloud(all_submissions())
    osc_sent = notify_submission(record)

    return jsonify(
        {
            "ok": True,
            "id": submission_id,
            "count": submission_count(),
            "osc_sent": osc_sent,
            "message": "Ucapan berhasil dikirim.",
        }
    )


@app.route("/api/submissions")
def api_submissions():
    records = all_submissions()
    return jsonify({"ok": True, "count": len(records), "submissions": records})


@app.route("/api/submissions/latest")
def api_latest():
    since = request.args.get("since", "").strip().upper() or None
    records = submissions_since(since)
    return jsonify(
        {
            "ok": True,
            "count": submission_count(),
            "new_count": len(records),
            "submissions": records,
        }
    )


@app.route("/api/stats")
def api_stats():
    return jsonify({"ok": True, "count": submission_count()})


@app.route("/api/health")
def api_health():
    return jsonify({"ok": True, "status": "running", "osc": osc_status()})


@app.route("/api/admin/reset", methods=["POST"])
def api_reset():
    if request.headers.get("X-Admin-Token", "") != ADMIN_TOKEN:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    reset_submissions()
    render_wordcloud([])
    return jsonify({"ok": True, "message": "All submissions cleared."})


@app.route("/api/admin/delete", methods=["POST"])
def api_delete_selected():
    if request.headers.get("X-Admin-Token", "") != ADMIN_TOKEN:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    ids = payload.get("ids", [])
    if not isinstance(ids, list):
        return jsonify({"ok": False, "error": "ids must be a list"}), 400

    deleted = delete_submissions(ids)
    render_wordcloud(all_submissions())
    return jsonify(
        {
            "ok": True,
            "deleted_count": len(deleted),
            "deleted_ids": [record.get("id") for record in deleted],
            "count": submission_count(),
        }
    )


def normalize_photo_for_touchdesigner(data: bytes) -> bytes:
    """Convert uploads to baseline RGB JPEG so TouchDesigner can read them."""
    with Image.open(BytesIO(data)) as image:
        image = ImageOps.exif_transpose(image)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        elif image.mode == "L":
            image = image.convert("RGB")

        image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)

        output = BytesIO()
        image.save(
            output,
            format="JPEG",
            quality=88,
            optimize=True,
            progressive=False,
        )
        return output.getvalue()


def render_submission_card(photo_data: bytes, name: str, message: str) -> bytes:
    """Render the final 16:9 entry card that TouchDesigner displays as one image."""
    width, height = 1600, 900
    base = (0, 27, 85)
    accent_yellow = cmyk_to_rgb(0, 30, 100, 0)
    accent_red = cmyk_to_rgb(0, 100, 100, 0)

    canvas = render_gradient_background(width, height, base)
    draw = ImageDraw.Draw(canvas, "RGBA")

    draw.rounded_rectangle((46, 42, width - 46, height - 42), radius=44, outline=(*accent_yellow, 180), width=5)

    title_font = load_font(62, bold=True)
    message_font = fit_font_for_box(draw, message, max_width=690, max_height=380, start_size=58, min_size=34)
    sender_font = load_font(40, bold=False)

    photo = Image.open(BytesIO(photo_data))
    photo = ImageOps.exif_transpose(photo).convert("RGB")
    photo_size = (560, 315)
    photo = contain_image(photo, photo_size)
    photo_x, photo_y = 125, 315
    draw.rounded_rectangle(
        (photo_x - 10, photo_y - 10, photo_x + photo_size[0] + 10, photo_y + photo_size[1] + 10),
        radius=36,
        fill=(*accent_yellow, 255),
    )
    draw.rounded_rectangle(
        (photo_x, photo_y, photo_x + photo_size[0], photo_y + photo_size[1]),
        radius=28,
        fill=(0, 0, 0, 255),
    )
    canvas.paste(photo, (photo_x, photo_y), rounded_mask(photo_size, 28))

    safe_name = name.strip()
    title_text = "Selamat Ulang Tahun!"
    draw.text((116, 84), title_text, fill=(255, 255, 255, 255), font=title_font)
    draw.rectangle((116, 166, 116 + min(620, max(180, text_width(draw, title_text, title_font))), 176), fill=(*accent_yellow, 230))

    text_x, text_y = 770, 240
    draw.rounded_rectangle((735, 190, 1490, 740), radius=36, fill=(0, 12, 48, 132))
    draw_multiline_box(
        draw,
        message,
        (text_x, text_y, 1450, 620),
        message_font,
        fill=(255, 255, 255, 255),
        line_spacing=12,
    )
    draw.text((text_x, 650), safe_name, fill=(255, 255, 255, 230), font=sender_font)
    draw.rectangle((text_x, 702, text_x + 210, 710), fill=(*accent_red, 230))

    output = BytesIO()
    canvas.save(output, format="JPEG", quality=92, optimize=True, progressive=False)
    return output.getvalue()


def render_gradient_background(width: int, height: int, base: tuple[int, int, int]) -> Image.Image:
    small_w, small_h = 96, 54
    canvas = Image.new("RGB", (small_w, small_h), base)
    pixels = canvas.load()
    for y in range(small_h):
        for x in range(small_w):
            horizontal = x / max(1, small_w - 1)
            vertical = y / max(1, small_h - 1)
            factor = 0.72 + (horizontal * 0.22) + ((1.0 - vertical) * 0.12)
            pixels[x, y] = tuple(min(255, int(channel * factor)) for channel in base)
    return canvas.resize((width, height), Image.Resampling.BICUBIC)


def cmyk_to_rgb(c: int, m: int, y: int, k: int) -> tuple[int, int, int]:
    return tuple(round(255 * (1 - value / 100) * (1 - k / 100)) for value in (c, m, y))


def load_font(size: int, bold: bool = False):
    candidates = (
        ("C:/Windows/Fonts/calibrib.ttf", "C:/Windows/Fonts/calibri.ttf")
        if bold
        else ("C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/segoeui.ttf")
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()


def contain_image(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    fitted = ImageOps.contain(image, size, Image.Resampling.LANCZOS)
    framed = Image.new("RGB", size, "black")
    framed.paste(fitted, ((target_w - fitted.width) // 2, (target_h - fitted.height) // 2))
    return framed


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def fit_font_for_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    max_height: int,
    start_size: int,
    min_size: int,
):
    for size in range(start_size, min_size - 1, -2):
        font = load_font(size, bold=False)
        lines = wrap_text(draw, text, font, max_width)
        line_height = text_height(draw, "Ag", font) + 12
        if len(lines) * line_height <= max_height:
            return font
    return load_font(min_size, bold=False)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = (current + " " + word).strip()
        if text_width(draw, candidate, font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_multiline_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    font,
    fill: tuple[int, int, int, int],
    line_spacing: int,
) -> None:
    x1, y1, x2, y2 = box
    y = y1
    line_height = text_height(draw, "Ag", font) + line_spacing
    for line in wrap_text(draw, text, font, x2 - x1):
        if y + line_height > y2:
            break
        draw.text((x1, y), line, fill=fill, font=font)
        y += line_height


def text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def text_height(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


if __name__ == "__main__":
    ensure_dirs()
    render_wordcloud(all_submissions())
    logger.info("Starting server on %s:%s", HOST, PORT)
    print("")
    print(f"Birthday server running on http://localhost:{PORT}")
    print(f"Tablet QR page: http://localhost:{PORT}/qr")
    print(f"Admin page:     http://localhost:{PORT}/admin")
    print("")
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
