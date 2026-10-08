"""JSON-LD must agree with what visitors actually see.

Structured data that contradicts the visible page is worse than none: it is
invisible to humans, so nobody notices, while search engines treat it as the
authoritative answer.
"""

import re

import pytest

from conftest import DOMAIN, jsonld_blocks, page_names, read_page, soup_for

MENU = "menu.html"
INDEX = "index.html"


def bakery():
    blocks = [b for b in jsonld_blocks(INDEX) if b.get("@type") == "Bakery"]
    assert len(blocks) == 1, f"expected exactly one Bakery block, found {len(blocks)}"
    return blocks[0]


def offer_catalog():
    blocks = [b for b in jsonld_blocks(MENU) if b.get("@type") == "OfferCatalog"]
    assert len(blocks) == 1, f"expected exactly one OfferCatalog, found {len(blocks)}"
    return blocks[0]


def visible_menu_categories():
    """Map category heading -> [(item name, starting price)], from the page.

    Each category is a `.menu-card` with an <h2> heading and `.menu-row`
    children holding a `.label` and a `.price` of the form "from $N".
    """
    soup = soup_for(MENU)
    categories = {}
    for card in soup.select(".menu-card"):
        heading = card.find("h2")
        if not heading:
            continue
        items = []
        for row in card.select(".menu-row"):
            label = row.select_one(".label")
            price = row.select_one(".price")
            if not (label and price):
                continue
            m = re.search(r"from \$(\d+)", price.get_text(" ", strip=True))
            if m:
                items.append((label.get_text(" ", strip=True), int(m.group(1))))
        if items:
            categories[heading.get_text(" ", strip=True)] = sorted(items)
    return categories


def catalog_categories():
    return {
        c["name"]: sorted(
            (o["name"], o["priceSpecification"]["minPrice"]) for o in c["itemListElement"]
        )
        for c in offer_catalog()["itemListElement"]
    }


# ── Validity ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("page", page_names())
def test_every_jsonld_block_is_valid_json(page):
    """A malformed block is silently ignored by crawlers — catch it here."""
    html = read_page(page)
    raw = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    soup_blocks = jsonld_blocks(page)  # raises JSONDecodeError if malformed
    assert len(soup_blocks) == len(raw)


def test_structured_data_exists_on_homepage_and_menu():
    assert jsonld_blocks(INDEX), "homepage has no JSON-LD"
    assert jsonld_blocks(MENU), "menu has no JSON-LD"


# ── Prices: the drift that matters ──────────────────────────────────────────

def test_every_visible_price_appears_in_structured_data():
    visible = visible_menu_categories()
    structured = catalog_categories()
    assert visible, "scraped no prices from the menu page — the scraper is broken"
    for category, prices in visible.items():
        assert category in structured, f"category {category!r} is on the page but not in JSON-LD"
        assert prices == structured[category], (
            f"{category}:\n  page shows {prices}\n  JSON-LD says {structured[category]}"
        )


def test_structured_data_invents_no_prices():
    visible = visible_menu_categories()
    for category, prices in catalog_categories().items():
        assert category in visible, f"category {category!r} is in JSON-LD but not on the page"
        assert prices == visible[category], (
            f"{category}:\n  JSON-LD says {prices}\n  page shows {visible[category]}"
        )


def test_menu_categories_match_exactly():
    assert set(visible_menu_categories()) == set(catalog_categories())


def test_all_offers_use_minprice_not_fixed_price():
    """Prices are 'from $N'. A fixed `price` would misrepresent them."""
    for category in offer_catalog()["itemListElement"]:
        for offer in category["itemListElement"]:
            spec = offer["priceSpecification"]
            assert "minPrice" in spec, f"{offer['name']}: missing minPrice"
            assert "price" not in spec, f"{offer['name']}: uses fixed price for a 'from' price"
            assert spec["priceCurrency"] == "USD"


# ── The business entity ─────────────────────────────────────────────────────

@pytest.mark.parametrize("field", ["name", "url", "description", "image", "address", "priceRange"])
def test_bakery_has_required_field(field):
    assert bakery().get(field), f"Bakery block is missing {field}"


def test_bakery_address_matches_site_copy():
    address = bakery()["address"]
    assert address["@type"] == "PostalAddress"
    assert address["addressLocality"] == "Potomac"
    assert address["addressRegion"] == "MD"
    assert address["addressCountry"] == "US"


def test_bakery_publishes_no_street_address():
    """Deliberate: it is a home kitchen and the site never states one."""
    assert "streetAddress" not in bakery()["address"]


def test_bakery_claims_no_contact_details_the_site_does_not_publish():
    """Inventing hours or a phone number is how structured data earns a penalty."""
    b = bakery()
    for field in ("telephone", "openingHours", "openingHoursSpecification", "email"):
        assert field not in b, f"Bakery claims {field}, but the site publishes none"


def test_bakery_url_and_image_use_canonical_domain():
    b = bakery()
    assert b["url"].startswith(DOMAIN)
    assert b["image"].startswith(DOMAIN)


def test_bakery_links_to_instagram():
    assert any("instagram.com" in s for s in bakery()["sameAs"])


def test_catalog_is_attributed_to_the_homepage_business():
    """Without a matching @id, crawlers see two unrelated entities."""
    provider = offer_catalog()["provider"]
    assert provider["@id"] == bakery()["@id"], (
        f"catalog provider {provider['@id']!r} does not match Bakery @id {bakery()['@id']!r}"
    )


def test_bakery_image_file_exists():
    from conftest import DOCS
    path = bakery()["image"].replace(DOMAIN, "").lstrip("/")
    assert (DOCS / path).is_file(), f"og/structured image missing from disk: {path}"
