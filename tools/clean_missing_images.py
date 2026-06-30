"""Remove submission records whose image file no longer exists."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "submissions.json"
IMAGES_DIR = ROOT / "data" / "images"


def main():
    records = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    kept = []
    removed = []

    for record in records:
        image = Path(record.get("image", "")).name
        if image and (IMAGES_DIR / image).exists():
            kept.append(record)
        else:
            removed.append(record)

    DATA_FILE.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Kept {len(kept)} records.")
    print(f"Removed {len(removed)} records with missing images.")
    for record in removed:
        print(f"- {record.get('id')} {record.get('image')}")


if __name__ == "__main__":
    main()
