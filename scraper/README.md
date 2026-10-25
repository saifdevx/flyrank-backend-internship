# Polite Scraper — FlyRank BE-05 (Week 5)

A small, polite scraping pipeline built with **Python** (Requests, Beautiful Soup, Pydantic). It downloads the first three catalogue pages of [Books to Scrape](https://books.toscrape.com/), visits all 60 book pages, turns messy HTML into clean, schema-checked JSON, survives a broken page without crashing, and ends every run with a report.

Pipeline: classify → fetch (cached) → extract → normalize → validate → store → report.

Built as part of the FlyRank Backend AI Engineering Internship — July 2026 cohort.

## Target classification

- **Site:** https://books.toscrape.com/
- **Why it is appropriate:** toscrape.com states that its sites are sandboxes built so people can practise scraping on them. That statement is the permission.
- **How much:** the first 3 catalogue pages only, plus the 60 book pages they link to.
- **What I collect:** title, product URL, price, availability, star rating, and description for each book.
- **robots.txt result:** `<PASTE what the script printed after "ROBOTS:" on your first run>`

I will not reuse this code on another site without checking its rules and terms first.

## Install and run

Python 3.10+ is required. From inside the `scraper` folder:

```bash
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src/main.py
```

This writes `output/books.json`, `output/errors.json` and `output/run-report.json`. Downloaded pages are cached in `cache/` (git-ignored), so reruns read from disk instead of the site.

To prove one bad page does not kill the run, add a made-up book URL on purpose:

```bash
python src/main.py --include-fake
```

## Record schema

Validated with Pydantic before storage. A record that fails goes to `errors.json` with the reason and never reaches `books.json`.

| Field | Type | Notes |
|-------|------|-------|
| `title` | string | required, not empty |
| `product_url` | string | absolute URL starting with `https://`, used as the record's identity |
| `price_text` | string | original text, e.g. `£51.77` |
| `price_gbp` | number | cleaned value, e.g. `51.77` |
| `availability_text` | string | e.g. `In stock (22 available)` |
| `rating_text` | string | e.g. `Three` |
| `description` | string or null | `null` when the page has none, never invented |
| `source_page` | string | catalogue page the book was found on (provenance) |
| `fetched_at` | string | UTC time the page was fetched (provenance) |

## Politeness rules

- **Honest user-agent** that names the project and links to the repo.
- **Delay:** at least 0.6 seconds between real requests. Cached pages need no delay.
- **Timeout:** 10 seconds per request.
- **Status check:** only HTTP 200 counts as a page. Anything else is a failed fetch.
- **Cache:** pages are saved once and reused during development.
- **Retries:** one retry after a timeout or a 5xx error. A 404 or 403 is never retried.
- **Scope:** the first 3 catalogue pages only. No hardcoded book links, since the script follows the site's own "next" link.

## Idempotency

`books.json` is overwritten on every run and records are keyed by their canonical product URL, so a rerun produces the same 60 records, not 120.

## Run report

`<PASTE your real output/run-report.json here after running the scraper>`

## Why no browser was needed

The data is already in the HTML the server sends, so a browser would only add cost.

## Limitation

`<WRITE one honest limitation in your own words, e.g. the selectors depend on this site's current HTML structure and would break if the site's layout changes>`

## Ethics note

`<REWRITE in your own words: use an official API when one exists, never bypass logins, paywalls or blocks, and collect only what you need.>`
