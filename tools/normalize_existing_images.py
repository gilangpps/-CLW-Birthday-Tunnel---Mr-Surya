"""Normalize existing submission images to TouchDesigner-friendly JPEG files."""

import json
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "submissions.json"
IMAGES_DIR = ROOT / "data" / "images"


def main():
    records = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    changed = 0
    skipped = 0

    for record in records:
        image_name = Path(record.get("image", "")).name
        source = IMAGES_DIR / image_name
        if not source.exists():
            skipped += 1
            continue

        target_name = f"{source.stem}.jpg"
        target = IMAGES_DIR / target_name
        normalized = normalize_image(source)
        target.write_bytes(normalized)

        if target.name != source.name:
            try:
                source.unlink()
            except OSError:
                pass

        record["image"] = target.name
        changed += 1

    DATA_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Normalized {changed} images.")
    print(f"Skipped {skipped} records with missing images.")


def normalize_image(path: Path) -> bytes:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
        image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)

        output = BytesIO()
        image.save(output, format="JPEG", quality=88, optimize=True, progressive=False)
        return output.getvalue()


if __name__ == "__main__":
    main()
