#!/usr/bin/env python3
"""Generate WebP grid thumbnails for the gallery.

The gallery grid renders each photo in a tile roughly 300px wide, but the
originals are 2048px. This builds a small WebP alongside each photo so the
grid loads thumbnails and the lightbox keeps using the full-size original.

Thumbnails are matched to their source by filename convention:
    docs/photos/2026-10-03_graffiti_dozen.jpg
 -> docs/photos/thumbs/2026-10-03_graffiti_dozen.webp

so photos.json needs no thumbnail bookkeeping.
"""

import argparse
import sys
from pathlib import Path

from PIL import Image

PHOTOS_DIR = Path(__file__).resolve().parent.parent / "docs" / "photos"
THUMBS_DIR = PHOTOS_DIR / "thumbs"
SOURCE_EXTS = {".jpg", ".jpeg", ".png"}
MAX_EDGE = 600
QUALITY = 82


def source_photos():
    return sorted(
        p for p in PHOTOS_DIR.iterdir()
        if p.is_file()
        and p.suffix.lower() in SOURCE_EXTS
        and not p.name.startswith("_preview_")
    )


def needs_rebuild(src, thumb, force):
    if force or not thumb.exists():
        return True
    return thumb.stat().st_mtime < src.stat().st_mtime


def build_thumb(src, thumb):
    with Image.open(src) as im:
        im = im.convert("RGB")
        im.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
        im.save(thumb, "WEBP", quality=QUALITY, method=6)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true",
        help="regenerate every thumbnail, even if it is already up to date",
    )
    args = parser.parse_args()

    if not PHOTOS_DIR.is_dir():
        sys.exit(f"ERROR: photos directory not found: {PHOTOS_DIR}")

    THUMBS_DIR.mkdir(exist_ok=True)

    photos = source_photos()
    built = skipped = 0
    failed = []

    for src in photos:
        thumb = THUMBS_DIR / (src.stem + ".webp")
        if not needs_rebuild(src, thumb, args.force):
            skipped += 1
            continue
        try:
            build_thumb(src, thumb)
            built += 1
        except Exception as e:
            failed.append((src.name, f"{type(e).__name__}: {e}"))

    # Drop thumbnails whose source photo is gone, so renames don't leave litter.
    expected = {p.stem + ".webp" for p in photos}
    orphans = [t for t in THUMBS_DIR.glob("*.webp") if t.name not in expected]
    for t in orphans:
        t.unlink()

    total = sum(t.stat().st_size for t in THUMBS_DIR.glob("*.webp"))
    print(f"built={built} skipped={skipped} orphans_removed={len(orphans)} "
          f"thumbs={len(list(THUMBS_DIR.glob('*.webp')))} total={total / 1e6:.1f}MB")

    for name, reason in failed:
        print(f"  FAILED {name}: {reason}", file=sys.stderr)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
