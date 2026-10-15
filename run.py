"""Command-line entry point.

    python run.py books --pages 5
    python run.py books --pages 50 --details
"""
import argparse
import logging
import sys

import config
from automation.report import build_report
from core.log import setup_logging
from scrapers.books import MAX_PAGES, scrape_books

log = logging.getLogger("run")


def page_count(text):
    value = int(text)                              # "abc" -> argparse prints "invalid page_count value"
    if not 1 <= value <= MAX_PAGES:
        raise argparse.ArgumentTypeError(f"pages must be between 1 and {MAX_PAGES}")
    return value


def build_parser():
    parser = argparse.ArgumentParser(description="Data Pipeline Toolkit - scrape, extract, automate.")
    jobs = parser.add_subparsers(dest="job", required=True)
    books = jobs.add_parser("books", help="scrape books.toscrape.com into an Excel report")
    books.add_argument("--pages", type=page_count, default=config.DEFAULT_PAGES,
                       help=f"catalogue pages to scrape, 1-{MAX_PAGES} (20 books each)")
    books.add_argument("--details", action="store_true",
                       help="also open every book page for stock, category, description (slower)")
    return parser


def run_books(args, output_dir):
    books = scrape_books(args.pages, details=args.details)
    if not books:
        log.error("No books scraped - check your internet connection and try again.")
        return 1
    path = build_report("books", books, output_dir)
    print(f"\nDONE: {len(books)} books -> {path}")
    return 0


def main(argv=None, output_dir=None, log_dir=None):
    args = build_parser().parse_args(argv)
    setup_logging(log_dir or config.LOG_DIR)
    log.info("Job started: %s", args.job)
    try:
        code = run_books(args, output_dir or config.OUTPUT_DIR)
    except PermissionError as error:               # report open in Excel
        log.error("%s", error)
        code = 1
    except Exception:
        log.exception("Job failed")
        code = 1
    log.info("Job finished with exit code %d", code)
    return code


if __name__ == "__main__":
    sys.exit(main())
