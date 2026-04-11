#!/usr/bin/env python3.12
"""
sync_photos.py — Sync new photos from the "Cowabunga website" Photos album to docs/photos/

Usage: python scripts/sync_photos.py

For each new photo found in the album (not yet synced), it will:
  1. Open the photo so you can see it
  2. Prompt you for a short description
  3. Name it YYYY-MM-DD_your_description.jpg and copy it to docs/photos/
  4. Update photos.json (manifest + UUID tracking)
  5. Commit and push photos + manifest together
"""

import json
import os
import re
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

ALBUM_NAME = "Cowabunga website"
REPO_DIR = Path(__file__).parent.parent
PHOTOS_DIR = REPO_DIR / "docs" / "photos"
MANIFEST_FILE = PHOTOS_DIR / "photos.json"


def load_manifest():
    """Returns (filename_to_uuid dict, processed_uuid set)."""
    filename_to_uuid = {}
    processed_uuids = set()
    if MANIFEST_FILE.exists():
        data = json.loads(MANIFEST_FILE.read_text())
        photos = data.get("photos", data) if isinstance(data, dict) else data
        for entry in photos:
            fn = entry.get("filename")
            uuid = entry.get("uuid")
            if fn:
                filename_to_uuid[fn] = uuid
            if uuid:
                processed_uuids.add(uuid)
    return filename_to_uuid, processed_uuids


def write_manifest(filename_to_uuid):
    """Rebuild photos.json from current filesystem state, preserving UUIDs."""
    image_files = sorted(
        [f.name for f in PHOTOS_DIR.iterdir() if f.suffix.lower() in {".jpg", ".jpeg", ".png"}],
        reverse=True,
    )
    photos = []
    for fn in image_files:
        entry = {"filename": fn}
        uuid = filename_to_uuid.get(fn)
        if uuid:
            entry["uuid"] = uuid
        photos.append(entry)
    MANIFEST_FILE.write_text(json.dumps({"photos": photos}, indent=2) + "\n")
    print(f"Updated manifest: {len(photos)} photos → docs/photos/photos.json")


def slugify(text):
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9 ]", "", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text


def git_commit_and_push(filenames, oldest_date):
    count = len(filenames)
    date_str = oldest_date.strftime("%Y-%m-%d")
    commit_msg = f"adding {count} photo{'s' if count != 1 else ''} created after {date_str}"
    print(f'\nCommitting: "{commit_msg}"')
    for filename in filenames:
        subprocess.run(["git", "-C", str(REPO_DIR), "add", f"docs/photos/{filename}"], check=True)
    subprocess.run(["git", "-C", str(REPO_DIR), "add", "docs/photos/photos.json"], check=True)
    subprocess.run(["git", "-C", str(REPO_DIR), "commit", "-m", commit_msg], check=True)
    subprocess.run(["git", "-C", str(REPO_DIR), "push"], check=True)
    print("Pushed.")


def main():
    try:
        import osxphotos
    except ImportError:
        print("osxphotos is not installed. Run: pip install osxphotos")
        sys.exit(1)

    print("Opening Photos library...")
    db = osxphotos.PhotosDB()

    album = next((a for a in db.album_info_shared if a.title == ALBUM_NAME), None)
    if album is None:
        print(f'Album "{ALBUM_NAME}" not found.')
        sys.exit(1)

    filename_to_uuid, processed_uuids = load_manifest()
    new_photos = [p for p in album.photos if p.uuid not in processed_uuids]
    new_photos.sort(key=lambda p: p.date or datetime.min)

    if not new_photos:
        print("No new photos found. You're all caught up!")
        return

    print(f"Found {len(new_photos)} new photo(s) to process.\n")

    added_filenames = []
    added_dates = []

    for i, photo in enumerate(new_photos, 1):
        print(f"--- Photo {i} of {len(new_photos)} ---")

        photo_date = photo.date or datetime.now()
        date_str = photo_date.strftime("%Y-%m-%d")

        # Export to a temp file first so we can open a preview before prompting
        tmp_name = f"_preview_{photo.uuid}.jpg"
        tmp_path = PHOTOS_DIR / tmp_name
        src_path = photo.path
        if src_path and os.path.exists(src_path):
            shutil.copy2(src_path, tmp_path)
        else:
            result = photo.export(str(PHOTOS_DIR), tmp_name)
            if not result:
                print("  Warning: could not export photo. Try opening Photos and letting it sync first.")
                continue

        subprocess.run(["open", str(tmp_path)], check=False)
        print(f"Date: {date_str}")

        while True:
            description = input("Describe this photo (e.g. 'sully monsters inc cake'): ").strip()
            if description:
                break
            print("Please enter a description.")

        slug = slugify(description)
        filename = f"{date_str}_{slug}.jpg"
        dest = PHOTOS_DIR / filename

        if dest.exists():
            print(f"  File already exists: {filename} — marking as synced and skipping.")
            tmp_path.unlink(missing_ok=True)
            filename_to_uuid[filename] = photo.uuid
            continue

        tmp_path.rename(dest)
        print(f"  Saved: docs/photos/{filename}")

        filename_to_uuid[filename] = photo.uuid
        added_filenames.append(filename)
        added_dates.append(photo_date)
        print()

    if not added_filenames:
        print("No photos were added.")
        return

    print("Photos added to docs/photos/:")
    for f in added_filenames:
        print(f"  {f}")

    write_manifest(filename_to_uuid)
    git_commit_and_push(added_filenames, min(added_dates))


if __name__ == "__main__":
    main()