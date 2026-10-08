"""Shared fixtures for the site consistency tests.

These tests read the real site files in docs/ — there are no mocks, because the
thing under test *is* the published data.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
PHOTOS = DOCS / "photos"
THUMBS = PHOTOS / "thumbs"
DOMAIN = "https://cowabungabakes.com"

# page file -> the public URL path it is served at
PAGE_ROUTES = {
    "index.html": "/",
    "story.html": "/story",
    "menu.html": "/menu",
    "gallery.html": "/gallery",
    "contact.html": "/contact",
}

PHOTO_EXTS = {".jpg", ".jpeg", ".png"}
PHOTO_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_[a-z0-9_]+\.(jpg|jpeg|png)$")


def page_names():
    """Page filenames, for parametrising tests."""
    return sorted(PAGE_ROUTES)


def read_page(name):
    return (DOCS / name).read_text()


def soup_for(name):
    return BeautifulSoup(read_page(name), "html.parser")


def jsonld_blocks(name):
    """Parsed JSON-LD blocks in a page, in document order."""
    return [
        json.loads(tag.string)
        for tag in soup_for(name).find_all("script", type="application/ld+json")
    ]


def git_last_commit_date(relpath):
    """YYYY-MM-DD of the last commit touching docs/<relpath>, or None."""
    out = subprocess.run(
        ["git", "log", "-1", "--format=%cs", "--", f"docs/{relpath}"],
        cwd=REPO, capture_output=True, text=True,
    ).stdout.strip()
    return out or None


def git_is_dirty(relpath):
    out = subprocess.run(
        ["git", "status", "--porcelain", "--", f"docs/{relpath}"],
        cwd=REPO, capture_output=True, text=True,
    ).stdout.strip()
    return bool(out)


@pytest.fixture(scope="session")
def manifest():
    return json.loads((PHOTOS / "photos.json").read_text())


@pytest.fixture(scope="session")
def manifest_photos(manifest):
    return manifest["photos"]


@pytest.fixture(scope="session")
def photos_on_disk():
    return sorted(
        p.name for p in PHOTOS.iterdir()
        if p.is_file() and p.suffix.lower() in PHOTO_EXTS
    )


@pytest.fixture(scope="session")
def thumbs_on_disk():
    if not THUMBS.is_dir():
        return []
    return sorted(p.name for p in THUMBS.glob("*.webp"))
