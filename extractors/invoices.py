"""Read invoices (PDF or photo) with Gemini AI and check that the numbers add up."""
import logging
from pathlib import Path

import httpx                                       # installed with google-genai
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

import config

log = logging.getLogger(__name__)


class TemporaryError(Exception):
    """Gemini can't be used right now (offline, quota, outage, bad key) - not the file's fault."""


def is_temporary(code):
    """HTTP codes that mean 'try again later' rather than 'this file is bad'."""
    return code in (401, 403, 408, 429) or code >= 500

FILE_TYPES = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
              ".png": "image/png", ".webp": "image/webp", ".heic": "image/heic"}


class LineItem(BaseModel):
    description: str
    quantity: float
    unit_price: float
    amount: float


class Invoice(BaseModel):
    invoice_number: str
    invoice_date: str            # always YYYY-MM-DD
    due_date: str
    supplier_name: str
    supplier_address: str
    customer_name: str
    currency: str                # GBP, USD, EUR...
    subtotal: float
    tax: float
    total: float
    line_items: list[LineItem]


PROMPT = """Extract the data from this invoice.
- Write dates as YYYY-MM-DD.
- For dates like 10/02/2026, look at the supplier's address: USA = month/day/year,
  most other countries (UK, Europe, Asia) = day/month/year.
- Currency as a 3-letter code (GBP, USD, EUR...).
- Numbers only for money (no symbols or commas). Use 0 if there is no tax.
- invoice_number: only the number itself, without labels or symbols like "No", "n°" or "#".
- supplier_name: the company that issued the invoice. If a full legal name is shown
  (often in the footer, e.g. "... Ltd", "... SAS", "... Pvt. Ltd."), use that.
- Never guess: if a field is not printed on the invoice (for example no due date), use an empty string."""


def read_invoice(path):
    """Send one file to Gemini and get back an Invoice."""
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing - add it to the .env file")
    path = Path(path)
    file_part = types.Part.from_bytes(data=path.read_bytes(), mime_type=FILE_TYPES[path.suffix.lower()])
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    try:
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=[file_part, PROMPT],
            config=types.GenerateContentConfig(response_mime_type="application/json",
                                               response_schema=Invoice),
        )
    except errors.APIError as error:
        if is_temporary(error.code):
            raise TemporaryError(f"Gemini unavailable ({error.code}): {error.message}") from error
        raise
    except (httpx.HTTPError, OSError) as error:
        raise TemporaryError(f"Cannot reach Gemini: {error}") from error
    if response.parsed is None:
        raise ValueError("Gemini returned no invoice data")
    return response.parsed


def check_invoice(inv):
    """Catch mistakes before the client sees them."""
    problems = []
    items_sum = round(sum(item.amount for item in inv.line_items), 2)
    # some invoices show line amounts before tax (= subtotal), others after tax (= total)
    if abs(items_sum - inv.subtotal) > 0.02 and abs(items_sum - inv.total) > 0.02:
        problems.append(f"items add up to {items_sum}, not {inv.subtotal} or {inv.total}")
    if abs(inv.subtotal + inv.tax - inv.total) > 0.02:
        problems.append("subtotal + tax does not equal total")
    if not inv.invoice_number:
        problems.append("no invoice number")
    return "OK" if not problems else "CHECK: " + "; ".join(problems)


def to_rows(file_name, inv, status):
    """Invoice -> one row for the Invoices sheet + rows for the Line Items sheet."""
    invoice = {
        "File": file_name, "Invoice No": inv.invoice_number, "Invoice Date": inv.invoice_date,
        "Due Date": inv.due_date, "Supplier": inv.supplier_name,
        "Supplier Address": inv.supplier_address, "Customer": inv.customer_name,
        "Currency": inv.currency, "Subtotal": inv.subtotal, "Tax": inv.tax, "Total": inv.total,
        "Status": status,
    }
    items = [{"File": file_name, "Invoice No": inv.invoice_number, "Description": item.description,
              "Quantity": item.quantity, "Unit Price": item.unit_price, "Amount": item.amount}
             for item in inv.line_items]
    return invoice, items


def extract_invoice(path, reader=read_invoice):
    """One file -> (invoice row, line item rows). Raises on unsupported or unreadable files."""
    path = Path(path)
    if path.suffix.lower() not in FILE_TYPES:
        raise ValueError(f"Unsupported file type: {path.suffix or '(none)'}")
    inv = reader(path)
    return to_rows(path.name, inv, check_invoice(inv))
