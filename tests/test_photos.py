"""The photo manifest, the files on disk, and the thumbnails must agree.

The gallery reads photos.json and derives thumbnail paths by convention, so a
disagreement between any two of the three shows up as a broken or needlessly
heavy image for visitors.
"""

import pytest
from PIL import Image

from conftest import PHOTO_NAME_RE, PHOTOS, THUMBS

MAX_THUMB_EDGE = 600


def thumb_name(photo_filename):
    return photo_filename.rsplit(".", 1)[0] + ".webp"


# ── Manifest internals ──────────────────────────────────────────────────────

def test_manifest_has_photos(manifest_photos):
    assert manifest_photos, "photos.json lists no photos"


def test_manifest_filenames_are_unique(manifest_photos):
    names = [p["filename"] for p in manifest_photos]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"duplicate filenames in photos.json: {sorted(dupes)}"


def test_manifest_uuids_are_unique(manifest_photos):
    uuids = [p["uuid"] for p in manifest_photos if p.get("uuid")]
    dupes = {u for u in uuids if uuids.count(u) > 1}
    assert not dupes, f"duplicate uuids in photos.json: {sorted(dupes)}"


def test_manifest_is_sorted_newest_first(manifest_photos):
    """The gallery renders in manifest order, so this is the display order."""
    names = [p["filename"] for p in manifest_photos]
    assert names == sorted(names, reverse=True), "photos.json is not sorted newest-first"


def test_every_manifest_entry_has_a_filename(manifest_photos):
    missing = [p for p in manifest_photos if not p.get("filename")]
    assert not missing, f"{len(missing)} manifest entries have no filename"


def test_photo_filenames_follow_date_slug_convention(manifest_photos):
    bad = [p["filename"] for p in manifest_photos if not PHOTO_NAME_RE.match(p["filename"])]
    assert not bad, f"filenames not matching YYYY-MM-DD_slug.ext: {bad}"


# ── Manifest vs. disk ───────────────────────────────────────────────────────

def test_every_manifest_photo_exists_on_disk(manifest_photos):
    missing = [p["filename"] for p in manifest_photos if not (PHOTOS / p["filename"]).is_file()]
    assert not missing, f"listed in photos.json but missing from disk: {missing}"


def test_every_photo_on_disk_is_in_the_manifest(manifest_photos, photos_on_disk):
    listed = {p["filename"] for p in manifest_photos}
    orphans = [f for f in photos_on_disk if f not in listed]
    assert not orphans, f"on disk but absent from photos.json (invisible in gallery): {orphans}"


def test_no_leftover_preview_files(photos_on_disk):
    """sync-photos writes _preview_<uuid>.jpg temporaries; none should survive."""
    leftovers = [f for f in photos_on_disk if f.startswith("_preview_")]
    assert not leftovers, f"leftover sync temporaries: {leftovers}"


# ── Thumbnails ──────────────────────────────────────────────────────────────

def test_every_photo_has_a_thumbnail(manifest_photos):
    missing = [
        p["filename"] for p in manifest_photos
        if not (THUMBS / thumb_name(p["filename"])).is_file()
    ]
    assert not missing, (
        f"{len(missing)} photos have no thumbnail (gallery falls back to full-size): {missing[:5]}"
    )


def test_no_orphan_thumbnails(manifest_photos, thumbs_on_disk):
    expected = {thumb_name(p["filename"]) for p in manifest_photos}
    orphans = [t for t in thumbs_on_disk if t not in expected]
    assert not orphans, f"thumbnails with no source photo: {orphans}"


def test_thumbnails_are_webp_and_within_size_limit(thumbs_on_disk):
    bad = []
    for name in thumbs_on_disk:
        with Image.open(THUMBS / name) as im:
            if im.format != "WEBP" or max(im.size) > MAX_THUMB_EDGE:
                bad.append((name, im.format, im.size))
    assert not bad, f"thumbnails wrong format or oversized: {bad}"


def test_thumbnails_are_smaller_than_their_source(manifest_photos):
    """A thumbnail no smaller than the original defeats the point."""
    offenders = []
    for p in manifest_photos:
        src = PHOTOS / p["filename"]
        thumb = THUMBS / thumb_name(p["filename"])
        if src.is_file() and thumb.is_file() and thumb.stat().st_size >= src.stat().st_size:
            offenders.append(p["filename"])
    assert not offenders, f"thumbnail not smaller than original: {offenders}"


# ── Colour profile (Safari / iOS rendering) ─────────────────────────────────

@pytest.mark.parametrize("ext", [".jpg", ".jpeg"])
def test_photos_are_srgb(photos_on_disk, ext):
    """Non-sRGB profiles render wrong or broken on Safari and iOS."""
    import subprocess

    offenders = []
    for name in photos_on_disk:
        if not name.lower().endswith(ext):
            continue
        out = subprocess.run(
            ["sips", "-g", "profile", str(PHOTOS / name)],
            capture_output=True, text=True,
        ).stdout
        if "sRGB IEC61966-2.1" not in out:
            profile = out.strip().splitlines()[-1].strip() if out.strip() else "unknown"
            offenders.append((name, profile))
    assert not offenders, f"photos not in sRGB: {offenders}"
