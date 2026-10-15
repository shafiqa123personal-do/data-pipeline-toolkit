"""Invoice inbox: new files in inbox/ are extracted once, added to the master
Excel file, then moved to done/ (or to failed/, with the reason in the log)."""
import logging
import shutil
import time
from datetime import datetime
from pathlib import Path

from automation.report import summarize_invoices
from core.excel import read_sheet, save_excel
from extractors.invoices import extract_invoice

log = logging.getLogger(__name__)


def process_inbox(inbox, done, failed, master_path, extract=extract_invoice, delay=1):
    inbox, done, failed, master_path = Path(inbox), Path(done), Path(failed), Path(master_path)
    for folder in (inbox, done, failed):
        folder.mkdir(parents=True, exist_ok=True)

    files = sorted(f for f in inbox.iterdir() if f.is_file() and not f.name.startswith("~$"))
    if not files:
        log.info("No new invoices in %s", inbox)
        return {"processed": 0, "failed": 0}

    invoices, items = _load_master(master_path)
    good, bad = [], []
    for number, file in enumerate(files, start=1):
        log.info("[%d/%d] %s", number, len(files), file.name)
        try:
            invoice, lines = extract(file)
        except Exception as error:
            log.error("FAILED %s: %s", file.name, error)
            bad.append(file)
        else:
            invoices.append(invoice)
            items.extend(lines)
            good.append(file)
            log.info("   %s | %s %s | %s", invoice.get("Supplier", ""), invoice.get("Currency", ""),
                     invoice.get("Total", ""), invoice.get("Status", ""))
        if number < len(files):
            time.sleep(delay)                      # stay under Gemini's rate limit

    if good:
        # Save BEFORE moving files: if the master is open in Excel this raises,
        # and every file stays in the inbox to be retried next time.
        save_excel({"Summary": summarize_invoices(invoices), "Invoices": invoices,
                    "Line Items": items}, master_path)
        log.info("Master file updated: %s", master_path)
    for file in good:
        _move(file, done)
    for file in bad:
        _move(file, failed)
    return {"processed": len(good), "failed": len(bad)}


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
    shutil.move(str(file), str(target))
