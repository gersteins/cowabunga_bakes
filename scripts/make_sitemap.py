#!/usr/bin/env python3
"""Generate docs/sitemap.xml with lastmod dates read from git.

Google uses <lastmod> only when it is consistently accurate, so the dates are
derived from commit history rather than maintained by hand.

One wrinkle: adding photos changes photos.json, not gallery.html. A date taken
from gallery.html alone would understate when the gallery's content actually
changed, so that page takes the later of its own commit and photos.json's.

<changefreq> and <priority> are deliberately omitted — Google ignores both.
"""

import subprocess
import sys
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
BASE = "https://cowabungabakes.com"

# page file -> (public URL path, extra files whose changes also change this page)
PAGES = [
    ("index.html",   "/",        []),
    ("story.html",   "/story",   []),
    ("menu.html",    "/menu",    []),
    ("gallery.html", "/gallery", ["photos/photos.json"]),
    ("contact.html", "/contact", []),
]


def is_dirty(relpath):
    """True if relpath has staged or unstaged changes not yet committed."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", f"docs/{relpath}"],
        cwd=REPO, capture_output=True, text=True,
    )
    return bool(result.stdout.strip())


def last_commit_date(relpath):
    """Return YYYY-MM-DD for relpath's most recent change, or None.

    A file with uncommitted changes is about to be committed, so it reports
    today rather than the date of the commit it is superseding.
    """
    if is_dirty(relpath):
        return date.today().isoformat()
    result = subprocess.run(
        ["git", "log", "-1", "--format=%cs", "--", f"docs/{relpath}"],
        cwd=REPO, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def main():
    entries = []
    missing = []

    for filename, url_path, companions in PAGES:
        if not (DOCS / filename).is_file():
            missing.append(filename)
            continue
        dates = [d for d in (last_commit_date(f) for f in [filename, *companions]) if d]
        entries.append((url_path, max(dates) if dates else None))

    if missing:
        sys.exit(f"ERROR: page(s) listed in PAGES not found in docs/: {', '.join(missing)}")

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url_path, lastmod in entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(BASE + url_path)}</loc>")
        if lastmod:
            lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")

    out = DOCS / "sitemap.xml"
    out.write_text("\n".join(lines) + "\n")

    print(f"wrote {out.relative_to(REPO)} ({len(entries)} urls)")
    for url_path, lastmod in entries:
        print(f"  {lastmod or '(no date)'}  {url_path}")


if __name__ == "__main__":
    main()
