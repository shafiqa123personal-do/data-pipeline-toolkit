"""Command-line entry point.

    python run.py books --pages 5
    python run.py leads --search "plumbers in london" --max 20 --emails
    python run.py invoices
    add --email to any command to email the finished report
"""
import argparse
import logging
import sys
from pathlib import Path

import config
from automation.inbox import process_inbox
from automation.notify import send_report
from automation.report import build_report
from core.log import setup_logging
from extractors.invoices import TemporaryError
from scrapers.books import MAX_PAGES, scrape_books
from scrapers.emails import add_emails
from scrapers.gmaps import scrape_gmaps

log = logging.getLogger("run")

MAX_LEADS_PER_SEARCH = 200


def page_count(text):
    value = int(text)                              # "abc" -> argparse prints "invalid page_count value"
    if not 1 <= value <= MAX_PAGES:
        raise argparse.ArgumentTypeError(f"pages must be between 1 and {MAX_PAGES}")
    return value


def lead_count(text):
    value = int(text)
    if not 1 <= value <= MAX_LEADS_PER_SEARCH:
        raise argparse.ArgumentTypeError(f"max must be between 1 and {MAX_LEADS_PER_SEARCH}")
    return value


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--email", action="store_true",
                        help="email the finished report (needs Gmail settings in .env)")

    parser = argparse.ArgumentParser(description="Data Pipeline Toolkit - scrape, extract, automate.")
    jobs = parser.add_subparsers(dest="job", required=True)

    books = jobs.add_parser("books", parents=[common],
                            help="scrape books.toscrape.com into an Excel report")
    books.add_argument("--pages", type=page_count, default=config.DEFAULT_PAGES,
                       help=f"catalogue pages to scrape, 1-{MAX_PAGES} (20 books each)")
    books.add_argument("--details", action="store_true",
                       help="also open every book page for stock, category, description (slower)")

    leads = jobs.add_parser("leads", parents=[common],
                            help="Google Maps business leads into an Excel report (needs Chrome)")
    leads.add_argument("--search", action="append", required=True,
                       help='e.g. "plumbers in london" (repeat --search for more)')
    leads.add_argument("--max", type=lead_count, default=20, help="max results per search")
    leads.add_argument("--emails", action="store_true",
                       help="also look for public business emails on each website")

    invoices = jobs.add_parser("invoices", parents=[common],
                               help="extract new invoices from the inbox into the master Excel file")
    invoices.add_argument("--folder", type=Path, default=config.INVOICE_DIR / "inbox",
                          help="inbox folder; done/ and failed/ are created next to it")
    return parser


def run_books(args, output_dir):
    books = scrape_books(args.pages, details=args.details)
    if not books:
        log.error("No books scraped - check your internet connection and try again.")
        return 1, None
    path = build_report("books", books, output_dir)
    print(f"\nDONE: {len(books)} books -> {path}")
    return 0, path


def run_leads(args, output_dir):
    leads = scrape_gmaps(args.search, max_results=args.max)
    if not leads:
        log.error("No leads found - check the search words and your internet connection.")
        return 1, None
    if args.emails:
        add_emails(leads)
    path = build_report("leads", leads, output_dir)
    print(f"\nDONE: {len(leads)} leads -> {path}")
    return 0, path


def run_invoices(args, output_dir):
    if not config.GEMINI_API_KEY:
        log.error("GEMINI_API_KEY is missing - add it to the .env file. No files were touched.")
        return 1, None
    inbox = Path(args.folder)
    master = Path(output_dir) / "invoices_master.xlsx"
    result = process_inbox(inbox, inbox.parent / "done", inbox.parent / "failed", master)
    print(f"\nDONE: {result['processed']} invoices added, {result['failed']} failed -> {master}")
    if result["processed"]:
        return 0, master
    return (1 if result["failed"] else 0), None


JOBS = {"books": run_books, "leads": run_leads, "invoices": run_invoices}


def main(argv=None, output_dir=None, log_dir=None):
    args = build_parser().parse_args(argv)
    setup_logging(log_dir or config.LOG_DIR)
    log.info("Job started: %s", args.job)
    try:
        code, report = JOBS[args.job](args, output_dir or config.OUTPUT_DIR)
        if report is not None and args.email:
            send_report(report, f"{args.job.title()} report - {report.name}")
    except PermissionError as error:               # report open in Excel
        log.error("%s", error)
        code = 1
    except TemporaryError as error:                # Gemini offline / quota - retry next run
        log.error("%s - unprocessed invoices stay in the inbox for the next run.", error)
        code = 1
    except Exception:
        log.exception("Job failed")
        code = 1
    log.info("Job finished with exit code %d", code)
    return code


if __name__ == "__main__":
    sys.exit(main())
