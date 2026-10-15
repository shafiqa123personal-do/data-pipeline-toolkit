"""Build the public sample files in samples/ - safe to publish:

    python tools/make_samples.py --leads output/leads_report_....xlsx --invoices output/invoices_master.xlsx

Books: scraped live (2 pages). Invoices: the master built from the fictional
sample invoices. Leads: masked - phones hidden, only generic business emails."""
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from automation.report import summarize_books, summarize_leads  # noqa: E402
from core.excel import read_sheet, save_excel                    # noqa: E402
from scrapers.books import scrape_books                          # noqa: E402

SAMPLES = ROOT / "samples"
GENERIC_NAMES = {"info", "hello", "contact", "office", "enquiries", "enquiry", "sales", "admin",
                 "bookings", "support", "mail"}
LEAD_COLUMNS = ["Name", "Category", "Rating", "Phone", "Website", "Address", "Email"]


def mask_phone(phone):
    """Keep the first 3 and last 2 digits: '020 7123 4567' -> '020 •••• ••67'."""
    total = sum(ch.isdigit() for ch in phone)
    seen, masked = 0, []
    for ch in phone:
        if ch.isdigit():
            seen += 1
            masked.append(ch if seen <= 3 or seen > total - 2 else "•")
        else:
            masked.append(ch)
    return "".join(masked)


def generic_emails(text):
    """Keep only role addresses like info@ / hello@ - never a person's email."""
    kept = []
    for email in (part.strip().lower() for part in (text or "").split(",")):
        if "@" in email and email.split("@")[0] in GENERIC_NAMES:
            kept.append(email)
    return ", ".join(kept)


def mask_leads(leads):
    masked = []
    for lead in leads:
        row = {column: lead.get(column, "") for column in LEAD_COLUMNS}
        row["Phone"] = mask_phone(row["Phone"] or "")
        row["Email"] = generic_emails(row["Email"])
        masked.append(row)
    return masked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--leads", type=Path, required=True, help="a leads_report_*.xlsx file")
    parser.add_argument("--invoices", type=Path, required=True, help="output/invoices_master.xlsx")
    args = parser.parse_args()

    leads = mask_leads(read_sheet(args.leads, "Leads"))
    save_excel({"Summary": summarize_leads(leads), "Leads": leads}, SAMPLES / "leads_sample.xlsx")

    books = scrape_books(2)
    save_excel({"Summary": summarize_books(books), "Books": books},
               SAMPLES / "books_report_sample.xlsx")

    shutil.copyfile(args.invoices, SAMPLES / "invoices_sample.xlsx")
    print(f"Saved samples: {len(leads)} leads, {len(books)} books, invoices -> {SAMPLES}")


if __name__ == "__main__":
    main()
