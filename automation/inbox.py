"""Invoice inbox: new files in inbox/ are extracted once, added to the master
Excel file, then moved to done/ (or to failed/, with the reason in the log).

Built to run unattended (e.g. every hour):
- files still being copied, and system/download temp files, are left alone;
- the same invoice is never extracted twice (each file has a fingerprint);
- if Gemini is unavailable the run stops and the rest wait in the inbox."""
import hashlib
import logging
import shutil
import time
from datetime import datetime
from pathlib import Path

from automation.report import summarize_invoices
from core.excel import read_sheet, save_excel
from extractors.invoices import TemporaryError, extract_invoice

log = logging.getLogger(__name__)

IGNORED_NAMES = {"desktop.ini", "thumbs.db"}
PARTIAL_SUFFIXES = {".crdownload", ".part", ".partial", ".tmp", ".download"}
MASTER_NOTE = {"Metric": "Note",
               "Value": "This file is rebuilt on every run - copy it before editing."}


def process_inbox(inbox, done, failed, master_path, extract=extract_invoice, delay=1, min_age=60):
    inbox, done, failed, master_path = Path(inbox), Path(done), Path(failed), Path(master_path)
    for folder in (inbox, done, failed):
        folder.mkdir(parents=True, exist_ok=True)

    files = _ready_files(inbox, min_age)
    if not files:
        log.info("No new invoices in %s", inbox)
        return {"processed": 0, "failed": 0}

    _check_writable(master_path)                   # open in Excel -> stop before paying for Gemini
    invoices, items = _load_master(master_path)
    known = {row["Fingerprint"] for row in invoices if row.get("Fingerprint")}
    good, bad, duplicates, stopped = [], [], [], None
    for number, file in enumerate(files, start=1):
        log.info("[%d/%d] %s", number, len(files), file.name)
        fingerprint = _fingerprint(file)
        if fingerprint in known:
            log.warning("   already in the master file - not extracted again")
            duplicates.append(file)
            continue
        try:
            invoice, lines = extract(file)
        except TemporaryError as error:
            log.error("Stopping: %s. The remaining files stay in the inbox for the next run.", error)
            stopped = error
            break
        except Exception as error:
            log.error("FAILED %s: %s", file.name, error)
            bad.append(file)
        else:
            invoice["Fingerprint"] = fingerprint
            invoices.append(invoice)
            items.extend(lines)
            good.append(file)
            known.add(fingerprint)
            log.info("   %s | %s %s | %s", invoice.get("Supplier", ""), invoice.get("Currency", ""),
                     invoice.get("Total", ""), invoice.get("Status", ""))
        if number < len(files):
            time.sleep(delay)                      # stay under Gemini's rate limit

    if good:
        # Save BEFORE moving files: if saving fails, every file stays in the inbox.
        save_excel({"Summary": summarize_invoices(invoices) + [MASTER_NOTE],
                    "Invoices": invoices, "Line Items": items}, master_path)
        log.info("Master file updated: %s", master_path)
    for file in good + duplicates:
        _move(file, done)
    for file in bad:
        _move(file, failed)
    if stopped:
        raise stopped
    return {"processed": len(good), "failed": len(bad)}


def _ready_files(inbox, min_age):
    """Files that are finished arriving; skips temp/system files and very new files."""
    now = time.time()
    ready = []
    for file in sorted(inbox.iterdir()):
        if (not file.is_file() or file.name.startswith(("~$", "."))
                or file.name.lower() in IGNORED_NAMES or file.suffix.lower() in PARTIAL_SUFFIXES):
            continue
        if now - file.stat().st_mtime < min_age:
            log.info("Waiting for %s - it changed less than %d seconds ago", file.name, min_age)
            continue
        ready.append(file)
    return ready


def _check_writable(path):
    if path.exists():
        try:
            open(path, "r+b").close()
        except PermissionError:
            raise PermissionError(
                f"Cannot update {path.name} - it is probably open in Excel. Close it and run again."
            ) from None


def _fingerprint(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()[:16]


def _load_master(path):
    if not path.exists():
        return [], []
    invoices = [row for row in read_sheet(path, "Invoices") if row.get("File")]
    items = [row for row in read_sheet(path, "Line Items") if row.get("File")]
    return invoices, items


def _move(file, folder):
    target = folder / file.name
    if target.exists():                            # never overwrite an earlier file
        target = folder / f"{file.stem}_{datetime.now():%Y%m%d_%H%M%S}{file.suffix}"
    try:
        shutil.move(str(file), str(target))
    except OSError as error:                       # e.g. open in a PDF viewer
        log.error("Could not move %s to %s/ (%s) - it will be recognised and moved next run",
                  file.name, folder.name, error)
