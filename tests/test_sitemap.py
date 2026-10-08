"""sitemap.xml must be well-formed and its dates must be true.

Google uses <lastmod> only while it stays consistently accurate, so a date that
drifts from reality is worse than no date at all.
"""

import xml.etree.ElementTree as ET
from datetime import date

import pytest

from conftest import (
    DOCS, DOMAIN, PAGE_ROUTES, git_is_dirty, git_last_commit_date,
)

NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
SITEMAP = DOCS / "sitemap.xml"
ROBOTS = DOCS / "robots.txt"

# Pages whose rendered content changes when another file changes.
CONTENT_SOURCES = {"gallery.html": ["photos/photos.json"]}


def sitemap_root():
    return ET.parse(SITEMAP).getroot()


def sitemap_entries():
    """[(url path, lastmod or None)] from the sitemap."""
    out = []
    for url in sitemap_root().findall("s:url", NS):
        loc = url.find("s:loc", NS).text
        lastmod = url.find("s:lastmod", NS)
        out.append((loc.replace(DOMAIN, "") or "/", lastmod.text if lastmod is not None else None))
    return out


def expected_date(page):
    """The date the sitemap should claim for a page."""
    sources = [page, *CONTENT_SOURCES.get(page, [])]
    if any(git_is_dirty(s) for s in sources):
        return date.today().isoformat()
    dates = [d for d in (git_last_commit_date(s) for s in sources) if d]
    return max(dates) if dates else None


def test_sitemap_exists():
    assert SITEMAP.is_file(), "docs/sitemap.xml is missing"


def test_sitemap_is_well_formed_xml():
    ET.parse(SITEMAP)


def test_sitemap_uses_the_sitemaps_namespace():
    assert sitemap_root().tag == "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset"


def test_sitemap_lists_every_page():
    listed = {path for path, _ in sitemap_entries()}
    assert listed == set(PAGE_ROUTES.values()), (
        f"sitemap lists {sorted(listed)}, pages are {sorted(PAGE_ROUTES.values())}"
    )


def test_sitemap_has_no_duplicate_urls():
    paths = [path for path, _ in sitemap_entries()]
    dupes = {p for p in paths if paths.count(p) > 1}
    assert not dupes, f"duplicate urls in sitemap: {sorted(dupes)}"


def test_every_sitemap_url_uses_the_canonical_domain():
    bad = [
        url.find("s:loc", NS).text
        for url in sitemap_root().findall("s:url", NS)
        if not url.find("s:loc", NS).text.startswith(DOMAIN)
    ]
    assert not bad, f"urls not on {DOMAIN}: {bad}"


@pytest.mark.parametrize("page,route", sorted(PAGE_ROUTES.items()))
def test_sitemap_lastmod_matches_git(page, route):
    """A lastmod Google cannot verify poisons every date in the file."""
    entries = dict(sitemap_entries())
    assert route in entries, f"{route} missing from sitemap"
    assert entries[route] == expected_date(page), (
        f"{route}: sitemap says {entries[route]}, git says {expected_date(page)} "
        f"— regenerate with scripts/make_sitemap.py"
    )


def test_sitemap_omits_changefreq_and_priority():
    """Google ignores both; carrying them is noise that implies false precision."""
    raw = SITEMAP.read_text()
    assert "<changefreq>" not in raw
    assert "<priority>" not in raw


# ── robots.txt ──────────────────────────────────────────────────────────────

def test_robots_exists():
    assert ROBOTS.is_file(), "docs/robots.txt is missing"


def test_robots_points_at_the_sitemap():
    assert f"Sitemap: {DOMAIN}/sitemap.xml" in ROBOTS.read_text()


def test_robots_does_not_block_the_site():
    """A bare `Disallow: /` would delist the whole site."""
    for line in ROBOTS.read_text().splitlines():
        assert line.strip() != "Disallow: /", "robots.txt blocks the entire site"
