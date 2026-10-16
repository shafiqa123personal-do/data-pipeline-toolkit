"""What the live demo page does behind the buttons: cached runs and a simple
per-visitor rate limit, so visitors can't burn the Gemini quota or the server."""
import logging
import math
import re
import time
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path

from automation.report import summarize_books
from core.excel import read_sheet, save_excel
from core.http import get_page
from extractors.invoices import extract_invoice
from scrapers.books import scrape_books

log = logging.getLogger(__name__)

DEMO_INVOICES = {
    "brightline": {"file": "invoice_brightline.pdf", "label": "Brightline Office Supplies (PDF)"},
    "greenleaf": {"file": "invoice_greenleaf.pdf", "label": "Greenleaf Cleaning Services (PDF)"},
    "pioneer": {"file": "scanned_receipt_pioneer.jpg", "label": "Pioneer Hardware (scanned photo)"},
}
MAX_DEMO_PAGES = 5
BOOKS_PER_PAGE = 20
WAIT_SECONDS = 30
PREVIEW_ROWS = 10
KEEP_SECONDS = 2 * 24 * 3600
CACHE_NAME = re.compile(r"^(books-(\d+)-\d{8}-\d{2}(-partial)?|invoice-[a-z]+-\d{8})\.xlsx$")
FAILURE_COOLDOWN = timedelta(minutes=5)   # after a failure, don't retry for every visitor
MAX_LIVE_RUNS_PER_HOUR = 30               # protects the shared server and the Gemini quota
UNAVAILABLE = {
    "books": "The live scrape is unavailable right now - download the sample report instead.",
    "invoices": "AI extraction is unavailable right now - download the sample result instead.",
}


class DemoError(Exception):
    """A friendly message for the visitor."""


def demo_scrape(pages, delay):
    """Fail fast on the shared web server: one try and a short timeout per page."""
    return scrape_books(pages, delay=delay, fetch=partial(get_page, retries=1, timeout=8))


class RateLimiter:
    def __init__(self, wait=WAIT_SECONDS, clock=time.monotonic):
        self.wait = wait
        self.clock = clock
        self.last_run = {}

    def check(self, key):
        """0 = allowed (and recorded); otherwise whole seconds left to wait."""
        now = self.clock()
        self.last_run = {k: t for k, t in self.last_run.items() if now - t < self.wait}  # forget old visitors
        last = self.last_run.get(key)
        if last is not None and now - last < self.wait:
            return math.ceil(self.wait - (now - last))
        self.last_run[key] = now
        return 0


class DemoRunner:
    def __init__(self, cache_dir, samples_dir, scrape=demo_scrape, extract=extract_invoice,
                 now=datetime.now, max_live_runs=MAX_LIVE_RUNS_PER_HOUR):
        self.cache_dir = Path(cache_dir)
        self.samples_dir = Path(samples_dir)
        self.scrape = scrape
        self.extract = extract
        self.now = now
        self.max_live_runs = max_live_runs
        self.failed_until = {}
        self.live_runs = {}

    def books(self, pages):
        if pages not in range(1, MAX_DEMO_PAGES + 1):
            raise DemoError(f"Choose between 1 and {MAX_DEMO_PAGES} pages.")
        name = f"books-{pages}-{self.now():%Y%m%d-%H}.xlsx"           # cached for the hour
        path = self.cache_dir / name
        partial = False
        if not path.exists():
            self._start_live_run("books")
            try:
                books = self.scrape(pages, delay=0.3)
                if not books:
                    raise ValueError("no books scraped")
                partial = len(books) < pages * BOOKS_PER_PAGE
                if partial:                                       # not kept: next visitor retries
                    name = name.replace(".xlsx", "-partial.xlsx")
                    path = self.cache_dir / name
                scraped_at = {"Metric": "Scraped at", "Value": f"{self.now():%Y-%m-%d %H:%M}"}
                save_excel({"Summary": [scraped_at] + summarize_books(books), "Books": books}, path)
            except Exception as error:
                log.error("Demo scrape failed: %s", error)
                raise self._unavailable("books") from error
            self._clean_old_files()
        books = read_sheet(path, "Books")
        summary = read_sheet(path, "Summary")
        return {"file": name, "count": len(books), "summary": summary,
                "preview": books[:PREVIEW_ROWS], "partial": partial,
                "minutes_ago": self._minutes_since(summary)}

    def invoice(self, key):
        if key not in DEMO_INVOICES:
            raise DemoError("Please choose one of the sample invoices.")
        name = f"invoice-{key}-{self.now():%Y%m%d}.xlsx"              # cached for the day
        path = self.cache_dir / name
        if not path.exists():
            self._start_live_run("invoices")
            try:
                invoice, items = self.extract(self.samples_dir / "invoices" / DEMO_INVOICES[key]["file"])
                save_excel({"Invoice": [invoice], "Line Items": items}, path)
            except Exception as error:
                log.error("Demo extraction failed for %s: %s", key, error)
                raise self._unavailable("invoices") from error
            self._clean_old_files()
        items = [row for row in read_sheet(path, "Line Items") if row.get("File")]
        return {"file": name, "invoice": read_sheet(path, "Invoice")[0], "items": items}

    def file_path(self, name):
        """Only files this runner created - never anything else on disk."""
        match = CACHE_NAME.match(name)
        if not match or (match.group(2) and not 1 <= int(match.group(2)) <= MAX_DEMO_PAGES):
            return None
        path = self.cache_dir / name
        return path if path.exists() else None

    def _start_live_run(self, card):
        """Refuse quickly while a recent failure cools down or the hourly cap is reached."""
        now = self.now()
        if self.failed_until.get(card, datetime.min) > now:
            raise DemoError(UNAVAILABLE[card])
        hour = f"{now:%Y%m%d%H}"
        if self.live_runs.get(hour, 0) >= self.max_live_runs:
            raise DemoError("The demo is busy right now - please try again later, "
                            "or download the sample.")
        self.live_runs = {hour: self.live_runs.get(hour, 0) + 1}   # only the current hour

    def _unavailable(self, card):
        self.failed_until[card] = self.now() + FAILURE_COOLDOWN
        return DemoError(UNAVAILABLE[card])

    def _minutes_since(self, summary):
        scraped_at = next((row["Value"] for row in summary if row.get("Metric") == "Scraped at"), None)
        if not scraped_at:
            return 0
        age = self.now() - datetime.strptime(scraped_at, "%Y-%m-%d %H:%M")
        return max(0, int(age.total_seconds() // 60))

    def _clean_old_files(self):
        cutoff = time.time() - KEEP_SECONDS
        for file in self.cache_dir.glob("*.xlsx*"):               # reports and leftover .tmp files
            if file.stat().st_mtime < cutoff:
                file.unlink(missing_ok=True)
