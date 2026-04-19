"""
Phase 4.0 — Scraping Service
ingest/scraper/scrape.py

Rules (from architecture):
  - groww.in URLs  → Playwright (headless Chromium, networkidle, inner_text("body"))
  - all other URLs → requests (User-Agent: MF-FAQ-Bot/1.0), HTML stripped with regex
  - Save plain text → data/raw/<slug>.txt
  - slug = URL path with "/" replaced by "_" (leading "_" stripped)
  - Sleep 1 s between every URL (politeness)
  - Log SKIP <url> status=<code> for non-200 responses
  - Update data/scrape_manifest.json after every URL
  - Append all log lines to logs/scheduler.log with timestamps
  - NEVER store or log user queries
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

# ---------------------------------------------------------------------------
# Corpus — 20 URLs from architecture
# ---------------------------------------------------------------------------

CORPUS: list[str] = [
    # Groww (Playwright)
    "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-focused-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth",
    "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
    "https://groww.in/p/mutual-funds/capital-gains-statement",
    "https://groww.in/p/mutual-funds/how-to-invest-in-mutual-funds",
    # HDFC AMC (requests)
    "https://www.hdfcfund.com/investor-services/service-request/download-account-statement",
    # AMFI (requests)
    "https://www.amfiindia.com/investor-corner/knowledge-center/sip.html",
    "https://www.amfiindia.com/investor-corner/knowledge-center/elss.html",
    "https://www.amfiindia.com/investor-corner/knowledge-center/expense-ratio.html",
    "https://www.amfiindia.com/investor-corner/knowledge-center/exit-load.html",
    "https://www.amfiindia.com/investor-corner/knowledge-center/riskometer.html",
    "https://www.amfiindia.com/investor-corner/knowledge-center/benchmark.html",
    "https://www.amfiindia.com/investor-corner/knowledge-center/mutual-fund-factsheet.html",
    # CAMS / KFintech / MF Central (requests)
    "https://www.camsonline.com/Investors/Statements/ConsolidatedAccountStatement",
    "https://www.kfintech.com/investor-services/account-statement/",
    "https://mfcentral.com/statement",
    # SEBI (requests)
    "https://www.sebi.gov.in/legal/circulars/sep-2021/categorization-of-mutual-fund-schemes_52823.html",
    "https://www.sebi.gov.in/legal/circulars/oct-2020/product-labeling-in-mutual-fund-schemes_48101.html",
]

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[2]          # project root
RAW_DIR = ROOT_DIR / "data" / "raw"
LOGS_DIR = ROOT_DIR / "logs"
MANIFEST_PATH = ROOT_DIR / "data" / "scrape_manifest.json"

RAW_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HEADERS = {"User-Agent": "MF-FAQ-Bot/1.0"}
HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s{2,}")


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _log(message: str) -> None:
    """Append a timestamped line to logs/scheduler.log and print to stdout."""
    line = f"[{_now_iso()}] {message}"
    print(line)
    with open(LOGS_DIR / "scheduler.log", "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _url_to_slug(url: str) -> str:
    """
    Convert a URL to a filesystem-safe slug.
    Uses the URL path portion; replaces '/' with '_'; strips leading '_'.

    Examples:
      https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth
        → mutual-funds_hdfc-mid-cap-fund-direct-growth

      https://www.amfiindia.com/investor-corner/knowledge-center/sip.html
        → investor-corner_knowledge-center_sip.html
    """
    path = urlparse(url).path          # e.g. /mutual-funds/hdfc-mid-cap-...
    slug = path.replace("/", "_").strip("_")
    # Collapse any double underscores that may arise from trailing slashes
    slug = re.sub(r"_+", "_", slug)
    return slug or "index"


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = HTML_TAG_RE.sub(" ", html)
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def _load_manifest() -> list[dict]:
    """Load existing manifest or return empty list."""
    if MANIFEST_PATH.exists():
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_manifest(entries: list[dict]) -> None:
    """Write manifest list to disk (pretty-printed JSON)."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(entries, fh, indent=2, ensure_ascii=False)


def _upsert_manifest(
    entries: list[dict],
    url: str,
    slug: str,
    status: str,
) -> list[dict]:
    """Insert or update the manifest entry for a given URL."""
    record = {
        "url": url,
        "slug": slug,
        "scraped_at": _now_iso(),
        "status": status,
    }
    # Replace existing entry for same URL, or append
    updated = [e for e in entries if e.get("url") != url]
    updated.append(record)
    return updated


# ---------------------------------------------------------------------------
# Scraper — requests (non-Groww)
# ---------------------------------------------------------------------------

def _scrape_with_requests(url: str) -> tuple[str, int]:
    """
    Fetch a non-Groww URL with requests.
    Returns (plain_text, http_status_code).
    Strips HTML tags. Returns ("", status) on non-200.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            return "", resp.status_code
        text = _strip_html(resp.text)
        return text, 200
    except requests.RequestException as exc:
        _log(f"ERROR requests {url} → {exc}")
        return "", 0


# ---------------------------------------------------------------------------
# Scraper — Playwright (Groww)
# ---------------------------------------------------------------------------

def _scrape_with_playwright(url: str) -> tuple[str, int]:
    """
    Fetch a Groww URL using Playwright headless Chromium.
    Waits for networkidle before extracting page.inner_text("body").
    Returns (plain_text, 200) on success, ("", 0) on error.
    """
    # Import here so non-Playwright environments don't fail at module load
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeoutError

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="MF-FAQ-Bot/1.0 (Playwright)",
                java_script_enabled=True,
            )
            page.goto(url, wait_until="networkidle", timeout=60_000)
            text = page.inner_text("body")
            browser.close()
        return text.strip(), 200
    except PwTimeoutError:
        _log(f"TIMEOUT playwright {url}")
        return "", 0
    except Exception as exc:
        _log(f"ERROR playwright {url} → {exc}")
        return "", 0


# ---------------------------------------------------------------------------
# Routing — choose scraper by domain
# ---------------------------------------------------------------------------

def _is_groww(url: str) -> bool:
    """Return True iff the URL's netloc contains 'groww.in'."""
    return "groww.in" in urlparse(url).netloc


def scrape_url(url: str) -> tuple[str, int]:
    """Dispatch to the correct scraper based on the URL domain."""
    if _is_groww(url):
        return _scrape_with_playwright(url)
    return _scrape_with_requests(url)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run() -> None:
    """
    Full scrape pipeline over all 20 corpus URLs.
    Saves plain-text files to data/raw/ and updates scrape_manifest.json.
    """
    _log("=== scrape.py START ===")
    manifest = _load_manifest()

    done_count = 0
    skip_count = 0

    for i, url in enumerate(CORPUS, start=1):
        slug = _url_to_slug(url)
        scraper_label = "playwright" if _is_groww(url) else "requests"
        _log(f"[{i:02d}/20] {scraper_label} -> {url}")

        text, status = scrape_url(url)

        if not text or status != 200:
            _log(f"SKIP {url} status={status}")
            manifest = _upsert_manifest(manifest, url, slug, "skip")
            skip_count += 1
        else:
            # Write raw text file
            out_path = RAW_DIR / f"{slug}.txt"
            out_path.write_text(text, encoding="utf-8")
            _log(f"  -> saved {out_path.name} ({len(text):,} chars)")
            manifest = _upsert_manifest(manifest, url, slug, "done")
            done_count += 1

        # Persist manifest after every URL so partial runs are recoverable
        _save_manifest(manifest)

        # Politeness sleep (1 s between every URL)
        if i < len(CORPUS):
            time.sleep(1)

    _log(
        f"=== scrape.py DONE — {done_count} scraped, "
        f"{skip_count} skipped, {len(CORPUS)} total ==="
    )


if __name__ == "__main__":
    run()
