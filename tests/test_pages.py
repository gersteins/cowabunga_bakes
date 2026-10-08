"""Every page carries the metadata it needs, and every internal link resolves.

These are the failures that are invisible while editing — a dead nav link or a
stale og:url looks fine in the browser you happen to be testing.
"""

import pytest

from conftest import (
    DOCS, DOMAIN, PAGE_ROUTES, page_names, read_page, soup_for,
)

NOT_FOUND = "404.html"
ALL_HTML = page_names() + [NOT_FOUND]

# URL path -> file that serves it, including extensionless routes
ROUTE_TO_FILE = {route: page for page, route in PAGE_ROUTES.items()}


def meta_content(soup, *, name=None, prop=None):
    tag = soup.find("meta", attrs={"name": name} if name else {"property": prop})
    return tag["content"] if tag and tag.has_attr("content") else None


def internal_links(soup):
    """Internal hrefs, excluding external links, anchors, and mailto/tel."""
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith(("http://", "https://", "mailto:", "tel:", "#")):
            continue
        out.append(href.split("#")[0].split("?")[0])
    return [h for h in out if h]


def resolves(href):
    """True if an internal href maps to a file that exists."""
    if href in ROUTE_TO_FILE:
        return (DOCS / ROUTE_TO_FILE[href]).is_file()
    path = href.lstrip("/")
    if not path:
        return (DOCS / "index.html").is_file()
    if (DOCS / path).exists():
        return True
    return (DOCS / f"{path}.html").is_file()


# ── Metadata every page needs ───────────────────────────────────────────────

@pytest.mark.parametrize("page", ALL_HTML)
def test_page_has_a_title(page):
    title = soup_for(page).find("title")
    assert title and title.get_text(strip=True), f"{page} has no <title>"


@pytest.mark.parametrize("page", ALL_HTML)
def test_page_has_a_meta_description(page):
    assert meta_content(soup_for(page), name="description"), f"{page} has no meta description"


@pytest.mark.parametrize("page", ALL_HTML)
def test_page_has_a_viewport(page):
    assert meta_content(soup_for(page), name="viewport"), f"{page} has no viewport meta"


@pytest.mark.parametrize("page", ALL_HTML)
def test_page_declares_a_charset(page):
    assert soup_for(page).find("meta", attrs={"charset": True}), f"{page} declares no charset"


@pytest.mark.parametrize("page", page_names())
def test_page_has_open_graph_tags(page):
    soup = soup_for(page)
    for prop in ("og:title", "og:description", "og:image", "og:url", "og:type"):
        assert meta_content(soup, prop=prop), f"{page} is missing {prop}"


@pytest.mark.parametrize("page,route", sorted(PAGE_ROUTES.items()))
def test_og_url_matches_the_pages_real_route(page, route):
    """A copy-pasted og:url makes every share link point at the wrong page."""
    expected = DOMAIN + ("/" if route == "/" else route)
    assert meta_content(soup_for(page), prop="og:url") == expected


@pytest.mark.parametrize("page", page_names())
def test_og_image_exists_on_disk(page):
    url = meta_content(soup_for(page), prop="og:image")
    assert url.startswith(DOMAIN), f"{page} og:image is not on {DOMAIN}"
    assert (DOCS / url.replace(DOMAIN, "").lstrip("/")).is_file(), (
        f"{page} og:image points at a missing file: {url}"
    )


@pytest.mark.parametrize("page", page_names())
def test_meta_description_claims_no_photo_count(page):
    """A hard-coded count goes stale every time a cake is added."""
    import re
    desc = meta_content(soup_for(page), name="description")
    assert not re.search(r"\b\d+\s+(custom\s+)?cake", desc), (
        f"{page} description hard-codes a count: {desc!r}"
    )


# ── Links ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("page", ALL_HTML)
def test_all_internal_links_resolve(page):
    broken = [h for h in internal_links(soup_for(page)) if not resolves(h)]
    assert not broken, f"{page} has dead internal links: {sorted(set(broken))}"


@pytest.mark.parametrize("page", ALL_HTML)
def test_every_page_links_to_every_other_page(page):
    """The nav is on every page; a missing entry strands visitors."""
    links = set(internal_links(soup_for(page)))
    missing = [r for r in PAGE_ROUTES.values() if r not in links]
    assert not missing, f"{page} does not link to {missing}"


# ── The 404 page ────────────────────────────────────────────────────────────

def test_404_page_exists():
    assert (DOCS / NOT_FOUND).is_file(), "docs/404.html is missing"


def test_404_is_noindex():
    assert meta_content(soup_for(NOT_FOUND), name="robots") == "noindex"


def test_404_asset_paths_are_root_absolute():
    """404.html is served for arbitrary URLs, where a relative path breaks.

    A request for /old/deep/link resolves "css/styles.css" against /old/deep/,
    so the page would render unstyled.
    """
    soup = soup_for(NOT_FOUND)
    relative = []
    for tag, attr in (("link", "href"), ("script", "src"), ("img", "src")):
        for el in soup.find_all(tag):
            val = el.get(attr)
            if not val or val.startswith(("http://", "https://", "data:")):
                continue
            if not val.startswith("/"):
                relative.append(val)
    assert not relative, (
        f"404.html uses relative asset paths that break on deep URLs: {relative}"
    )


# ── Domain consistency ──────────────────────────────────────────────────────

def test_cname_matches_the_canonical_domain():
    cname = (DOCS / "CNAME").read_text().strip()
    assert DOMAIN == f"https://{cname}", (
        f"CNAME is {cname!r} but pages and sitemap use {DOMAIN}"
    )
