# Cowabunga Bakes

Static site for [cowabungabakes.com](https://cowabungabakes.com), served by GitHub
Pages from `docs/`.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
git config core.hooksPath scripts/hooks    # run the tests before each commit
```

The `core.hooksPath` setting is per-clone and is not carried in the repo, so it
has to be set once on each machine. Without it the hook simply never runs.

## Running the site locally

```bash
./scripts/start.sh          # serves docs/ at http://localhost:3000
```

## Tests

```bash
.venv/bin/python -m pytest tests -q
```

These check the site's data against itself — the failures they catch are the ones
that are invisible while editing:

| File | Guards against |
| --- | --- |
| `tests/test_structured_data.py` | JSON-LD prices drifting from the visible menu; invented business details |
| `tests/test_photos.py` | Manifest/disk/thumbnail disagreement; non-sRGB photos that break on Safari and iOS |
| `tests/test_sitemap.py` | `lastmod` dates that no longer match git; a `robots.txt` that blocks the site |
| `tests/test_pages.py` | Dead internal links, wrong `og:url`, missing metadata, relative asset paths on the 404 page |

The pre-commit hook runs the whole suite and aborts the commit on any failure.
Bypass it for a work-in-progress commit with `git commit --no-verify`.

## Scripts

| Script | Purpose |
| --- | --- |
| `scripts/sync_photos.py` | Pull new photos from the "Cowabunga website" shared album |
| `scripts/make_thumbs.py` | Build 600px WebP grid thumbnails (`--force` to rebuild all) |
| `scripts/make_sitemap.py` | Regenerate `docs/sitemap.xml` with `lastmod` dates read from git |

`make_thumbs.py` and `make_sitemap.py` are idempotent — run them any time.

## Photos

Photos live in `docs/photos/`, listed in `photos.json`, with grid thumbnails in
`docs/photos/thumbs/`. The gallery finds a thumbnail by filename convention
(`<name>.jpg` → `thumbs/<name>.webp`) and falls back to the full-size original if
one is missing. The lightbox always loads the original.

Both are kept in sync by the `/sync-photos` workflow; the tests verify it.
