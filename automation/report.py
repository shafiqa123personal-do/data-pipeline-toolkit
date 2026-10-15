"""Turn scraped rows into a finished Excel report: Summary + data + Changes."""
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path

from core.excel import read_sheet, save_excel

log = logging.getLogger(__name__)


def summarize_books(books):
    """Key numbers for the Summary sheet."""
    prices = [b["Price"] for b in books if b.get("Price") is not None]
    summary = [
        {"Metric": "Total books", "Value": len(books)},
        {"Metric": "Average price (£)", "Value": round(sum(prices) / len(prices), 2) if prices else ""},
        {"Metric": "Cheapest (£)", "Value": min(prices) if prices else ""},
        {"Metric": "Most expensive (£)", "Value": max(prices) if prices else ""},
    ]
    for stars in range(5, 0, -1):
        count = sum(1 for b in books if b.get("Rating") == stars)
        summary.append({"Metric": f"{stars}-star books", "Value": count})
    categories = Counter(b["Category"] for b in books if b.get("Category"))
    for name, count in categories.most_common():
        summary.append({"Metric": f"Category: {name}", "Value": count})
    return summary


def compare_books(current, previous):
    """What changed since the last run: new books, removed books, price changes."""
    if previous is None:
        return [_change("No previous run")]
    old = {b["Link"]: b for b in previous}
    new = {b["Link"]: b for b in current}
    changes = []
    for link, b in new.items():
        if link not in old:
            changes.append(_change("New", b, new_price=b["Price"]))
        elif old[link]["Price"] != b["Price"]:
            changes.append(_change("Price changed", b, old[link]["Price"], b["Price"]))
    for link, b in old.items():
        if link not in new:
            changes.append(_change("Removed", b, old_price=b["Price"]))
    return changes or [_change("No changes")]


def find_previous_report(output_dir, kind, exclude=None):
    """Most recent '<kind>_report_*.xlsx' in output_dir (other than `exclude`)."""
    files = sorted(Path(output_dir).glob(f"{kind}_report_*.xlsx"))
    if exclude is not None:
        files = [f for f in files if f.resolve() != Path(exclude).resolve()]
    return files[-1] if files else None


def build_report(kind, rows, output_dir, now=None):
    """Write the full report and return its path."""
    if kind != "books":
        raise ValueError(f"Unknown report kind: {kind}")
    now = now or datetime.now()
    output_dir = Path(output_dir)
    path = output_dir / f"{kind}_report_{now:%Y-%m-%d_%H%M}.xlsx"

    previous = _load_previous(find_previous_report(output_dir, kind, exclude=path))
    save_excel({
        "Summary": summarize_books(rows),
        "Books": rows,
        "Changes": compare_books(rows, previous),
    }, path)
    log.info("Report saved: %s", path)
    return path


def _load_previous(path):
    if path is None:
        return None
    try:
        rows = [row for row in read_sheet(path, "Books") if row.get("Link")]
    except Exception as error:                     # corrupted or unreadable file
        log.warning("Could not read previous report %s: %s", path.name, error)
        return None
    log.info("Comparing with previous report %s", path.name)
    return rows or None


def _change(kind, book=None, old_price=None, new_price=None):
    book = book or {}
    return {
        "Change": kind,
        "Title": book.get("Title", ""),
        "Old price": old_price if old_price is not None else "",
        "New price": new_price if new_price is not None else "",
        "Link": book.get("Link", ""),
    }
