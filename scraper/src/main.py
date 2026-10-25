"""Polite scraper for Books to Scrape (a practice sandbox). FlyRank BE-05 / A9.

Pipeline: classify -> fetch (cached) -> extract -> normalize -> validate -> store -> report.
Run from the scraper/ folder:  python src/main.py
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, ValidationError, field_validator

try:
    sys.stdout.reconfigure(encoding="utf-8")  # so the pound sign prints on Windows
except Exception:
    pass

# ---------- Config ----------
BASE_URL = "https://books.toscrape.com/"
START_URL = BASE_URL + "catalogue/page-1.html"
MAX_CATALOGUE_PAGES = 3
USER_AGENT = "FlyRankInternshipA9/1.0 (+https://github.com/saifdevx/flyrank-backend-internship)"
TIMEOUT_SECONDS = 10
MIN_DELAY_SECONDS = 0.6   # the assignment requires at least 0.5s between real requests
RETRY_WAIT_SECONDS = 2

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"
OUTPUT_DIR = ROOT / "output"

FAKE_URL = BASE_URL + "catalogue/this-book-does-not-exist_999/index.html"

stats = {"pages_fetched": 0, "cache_hits": 0, "failed_pages": 0, "failed_urls": []}
_last_request_at = 0.0


class FetchError(Exception):
    pass


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cache_path(url):
    # turn the URL into a safe file name, e.g. catalogue__page-1.html
    return CACHE_DIR / (url.replace(BASE_URL, "").replace("/", "__") or "index.html")


def polite_wait():
    """Make sure at least MIN_DELAY_SECONDS passed since the last real request."""
    wait = MIN_DELAY_SECONDS - (time.monotonic() - _last_request_at)
    if wait > 0:
        time.sleep(wait)


# ---------- Stage 1 + 5: fetch with cache, timeout, status check, one retry ----------
def fetch(url):
    """Return (html, fetched_at, from_cache). Raises FetchError if the page cannot be fetched."""
    global _last_request_at
    path = cache_path(url)
    if path.exists():
        stats["cache_hits"] += 1
        fetched_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"CACHE HIT {url} ({path.stat().st_size} bytes)")
        return path.read_text(encoding="utf-8"), fetched_at, True

    last_error = "unknown error"
    for attempt in (1, 2):
        polite_wait()
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS)
        except (requests.Timeout, requests.ConnectionError) as e:
            last_error = type(e).__name__   # timeouts are worth one retry
        else:
            _last_request_at = time.monotonic()
            if resp.status_code == 200:
                resp.encoding = "utf-8"     # without this the pound sign can turn into garbage
                html = resp.text
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(html, encoding="utf-8")
                stats["pages_fetched"] += 1
                print(f"FETCH {url} ({len(resp.content)} bytes)")
                return html, now_iso(), False
            if resp.status_code >= 500:
                last_error = f"HTTP {resp.status_code}"   # server error: retry once
            else:
                # 404 / 403 / other 4xx: asking again will not help, so never retry
                raise FetchError(f"HTTP {resp.status_code} (not retried)")
        _last_request_at = time.monotonic()
        if attempt == 1:
            time.sleep(RETRY_WAIT_SECONDS)
    raise FetchError(f"{last_error} (gave up after 2 attempts)")


def record_failure(url, error):
    stats["failed_pages"] += 1
    stats["failed_urls"].append({"url": url, "reason": str(error)})
    print(f"FAILED {url}: {error}")


# ---------- Stage 0: robots.txt check (once, result saved) ----------
def check_robots():
    result_file = CACHE_DIR / "robots-result.txt"
    if result_file.exists():
        print("ROBOTS (saved result):", result_file.read_text(encoding="utf-8").strip())
        return
    global _last_request_at
    url = BASE_URL + "robots.txt"
    polite_wait()
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS)
        if resp.status_code == 200:
            result = "robots.txt found (HTTP 200):\n" + resp.text[:500]
        elif resp.status_code == 404:
            result = "no robots file found (HTTP 404)"
        else:
            result = f"robots.txt request returned HTTP {resp.status_code}"
    except requests.RequestException as e:
        result = f"robots.txt request failed: {type(e).__name__}"
    _last_request_at = time.monotonic()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    result_file.write_text(result, encoding="utf-8")
    print("ROBOTS:", result)


# ---------- Stage 2: discover book links across the catalogue ----------
def discover_book_urls():
    sources = {}      # book url -> catalogue page it came from (a dict also removes duplicates)
    discovered = 0
    pages = 0
    page_url = START_URL
    while page_url and pages < MAX_CATALOGUE_PAGES:
        try:
            html, _, _ = fetch(page_url)
        except FetchError as e:
            record_failure(page_url, e)
            break
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select("article.product_pod h3 a"):
            discovered += 1
            url = urljoin(page_url, a["href"])      # relative -> absolute, never string gluing
            sources.setdefault(url, page_url)
        pages += 1
        nxt = soup.select_one("li.next a")           # let the site tell us where the next page is
        page_url = urljoin(page_url, nxt["href"]) if nxt else None
    return pages, discovered, sources


# ---------- Stage 3: extract the eight raw fields ----------
def clean_text(tag):
    return " ".join(tag.get_text().split()) if tag else None


def extract_raw(html, url, source_page, fetched_at):
    soup = BeautifulSoup(html, "html.parser")
    product = soup.select_one("div.product_main")   # aim at the product area, not the whole page
    if product is None:
        raise ValueError("product area not found on page")

    rating_tag = product.select_one("p.star-rating")
    rating = None
    if rating_tag:
        names = [c for c in rating_tag.get("class", []) if c != "star-rating"]
        rating = names[0] if names else None

    description = None
    desc_header = soup.select_one("#product_description")
    if desc_header:
        description = clean_text(desc_header.find_next_sibling("p")) or None   # null, never invented

    return {
        "title": clean_text(product.select_one("h1")),
        "product_url": url,
        "price_text": clean_text(product.select_one("p.price_color")),
        "availability_text": clean_text(product.select_one("p.availability")),
        "rating_text": rating,
        "description": description,
        "source_page": source_page,
        "fetched_at": fetched_at,
    }


# ---------- Stage 4: normalize + schema ----------
def parse_price(price_text):
    m = re.search(r"\d+(?:\.\d+)?", price_text or "")
    return float(m.group()) if m else None


class BookRecord(BaseModel):
    title: str
    product_url: str
    price_text: str
    price_gbp: float
    availability_text: str
    rating_text: str
    description: Optional[str] = None
    source_page: str
    fetched_at: str

    @field_validator("title", "price_text", "availability_text", "rating_text")
    @classmethod
    def not_empty(cls, v):
        if not v.strip():
            raise ValueError("must not be empty")
        return v

    @field_validator("product_url", "source_page")
    @classmethod
    def must_be_https(cls, v):
        if not v.startswith("https://"):
            raise ValueError("must start with https://")
        return v

    @field_validator("price_gbp")
    @classmethod
    def not_negative(cls, v):
        if v < 0:
            raise ValueError("must not be negative")
        return v


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------- Run everything ----------
def main():
    parser = argparse.ArgumentParser(description="Polite scraper for Books to Scrape")
    parser.add_argument("--include-fake", action="store_true",
                        help="add one made-up book URL to prove a bad page does not kill the run")
    args = parser.parse_args()

    started_at = now_iso()
    t0 = time.monotonic()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    check_robots()
    pages, discovered, sources = discover_book_urls()
    urls = list(sources)
    print(f"catalogue_pages={pages} discovered={discovered} unique_urls={len(urls)}")

    if args.include_fake:
        urls.append(FAKE_URL)
        sources[FAKE_URL] = START_URL

    valid = {}          # keyed by canonical product_url, so a duplicate counts once
    errors = []
    detail_pages = 0
    first_raw = None

    for url in urls:
        try:
            html, fetched_at, _ = fetch(url)
            raw = extract_raw(html, url, sources[url], fetched_at)
        except Exception as e:          # one broken page is logged and skipped
            record_failure(url, e)
            continue
        detail_pages += 1
        if first_raw is None:
            first_raw = dict(raw)       # the eight raw keys, before cleaning
        raw["price_gbp"] = parse_price(raw["price_text"])
        try:
            record = BookRecord(**raw)
        except ValidationError as e:
            reason = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())
            errors.append({"url": url, "reason": reason})
            continue
        valid[record.product_url] = record.model_dump()

    print(f"detail_pages={detail_pages}")
    if first_raw:
        print("Sample raw record:")
        print(json.dumps(first_raw, indent=2, ensure_ascii=False))

    # overwrite (never append): a rerun gives the same records, not duplicates
    write_json(OUTPUT_DIR / "books.json", list(valid.values()))
    write_json(OUTPUT_DIR / "errors.json", errors)

    report = {
        "started_at": started_at,
        "duration_seconds": round(time.monotonic() - t0, 2),
        "pages_fetched": stats["pages_fetched"],
        "cache_hits": stats["cache_hits"],
        "valid_records": len(valid),
        "invalid_records": len(errors),
        "failed_pages": stats["failed_pages"],
        "failed_urls": stats["failed_urls"],
    }
    write_json(OUTPUT_DIR / "run-report.json", report)
    print("Run report:")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
