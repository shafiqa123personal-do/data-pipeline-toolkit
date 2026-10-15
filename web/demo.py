"""What the live demo page does behind the buttons: cached runs and a simple
per-visitor rate limit, so visitors can't burn the Gemini quota or the server."""
import logging
import math
import re
import time
from datetime import datetime
from pathlib import Path

from automation.report import summarize_books
from core.excel import read_sheet, save_excel
from extractors.invoices import extract_invoice
from scrapers.books import scrape_books

log = logging.getLogger(__name__)

DEMO_INVOICES = {
    "brightline": {"file": "invoice_brightline.pdf", "label": "Brightline Office Supplies (PDF)"},
    "greenleaf": {"file": "invoice_greenleaf.pdf", "label": "Greenleaf Cleaning Services (PDF)"},
    "pioneer": {"file": "scanned_receipt_pioneer.jpg", "label": "Pioneer Hardware (scanned photo)"},
}
MAX_DEMO_PAGES = 5
WAIT_SECONDS = 30
PREVIEW_ROWS = 10
KEEP_SECONDS = 2 * 24 * 3600
CACHE_NAME = re.compile(r"^(books-[1-5]-\d{8}-\d{2}|invoice-[a-z]+-\d{8})\.xlsx$")


class DemoError(Exception):
    """A friendly message for the visitor."""


class RateLimiter:
    def __init__(self, wait=WAIT_SECONDS, clock=time.monotonic):
        self.wait = wait
        self.clock = clock
        self.last_run = {}

    def check(self, key):
        """0 = allowed (and recorded); otherwise whole seconds left to wait."""
        now = self.clock()
        last = self.last_run.get(key)
        if last is not None and now - last < self.wait:
            return math.ceil(self.wait - (now - last))
        self.last_run[key] = now
        return 0


class DemoRunner:
    def __init__(self, cache_dir, samples_dir, scrape=scrape_books, extract=extract_invoice,
                 now=datetime.now):
        self.cache_dir = Path(cache_dir)
        self.samples_dir = Path(samples_dir)
        self.scrape = scrape
        self.extract = extract
        self.now = now

    def books(self, pages):
        if pages not in range(1, MAX_DEMO_PAGES + 1):
            raise DemoError(f"Choose between 1 and {MAX_DEMO_PAGES} pages.")
        name = f"books-{pages}-{self.now():%Y%m%d-%H}.xlsx"           # cached for the hour
        path = self.cache_dir / name
        if not path.exists():
            books = self.scrape(pages, delay=0.3)
            if not books:
                raise DemoError("The live scrape is unavailable right now - "
                                "download the sample report instead.")
            save_excel({"Summary": summarize_books(books), "Books": books}, path)
            self._clean_old_files()
        books = read_sheet(path, "Books")
        return {"file": name, "count": len(books), "summary": read_sheet(path, "Summary"),
                "preview": books[:PREVIEW_ROWS]}

    def invoice(self, key):
        if key not in DEMO_INVOICES:
            raise DemoError("Please choose one of the sample invoices.")
        name = f"invoice-{key}-{self.now():%Y%m%d}.xlsx"              # cached for the day
        path = self.cache_dir / name
        if not path.exists():
            try:
                invoice, items = self.extract(self.samples_dir / "invoices" / DEMO_INVOICES[key]["file"])
            except Exception as error:
                log.error("Demo extraction failed for %s: %s", key, error)
                raise DemoError("AI extraction is unavailable right now - "
                                "download the sample result instead.") from error
            save_excel({"Invoice": [invoice], "Line Items": items}, path)
            self._clean_old_files()
        items = [row for row in read_sheet(path, "Line Items") if row.get("File")]
        return {"file": name, "invoice": read_sheet(path, "Invoice")[0], "items": items}

    def file_path(self, name):
        """Only files this runner created - never anything else on disk."""
        if not CACHE_NAME.match(name):
            return None
        path = self.cache_dir / name
        return path if path.exists() else None

    def _clean_old_files(self):
        cutoff = time.time() - KEEP_SECONDS
        for file in self.cache_dir.glob("*.xlsx"):
            if file.stat().st_mtime < cutoff:
                file.unlink(missing_ok=True)
