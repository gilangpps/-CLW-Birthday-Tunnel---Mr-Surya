"""Generate final card images for existing submissions."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from app import render_submission_card  # noqa: E402
from storage import safe_card_path, safe_image_path  # noqa: E402

DATA_FILE = ROOT / "data" / "submissions.json"


def main():
    records = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    generated = 0
    skipped = 0

    for record in records:
        image_path = safe_image_path(record.get("image", ""))
        if not image_path.exists():
            skipped += 1
            continue

        card_name = record.get("card") or f"{image_path.stem}.jpg"
        card_bytes = render_submission_card(
            image_path.read_bytes(),
            record.get("name", ""),
            record.get("message", ""),
        )
        safe_card_path(card_name).write_bytes(card_bytes)
        record["card"] = card_name
        generated += 1

    DATA_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated {generated} cards.")
    print(f"Skipped {skipped} records with missing images.")


if __name__ == "__main__":
    main()
