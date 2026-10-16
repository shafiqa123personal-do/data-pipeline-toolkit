import httpx
import pytest
from google.genai import errors

import config
from extractors import invoices as invoices_module
from extractors.invoices import (Invoice, LineItem, TemporaryError, check_invoice,
                                 extract_invoice, is_temporary, read_invoice, to_rows)


def make_invoice(**changes):
    data = dict(invoice_number="INV-1", invoice_date="2026-10-01", due_date="",
                supplier_name="Brightline Ltd", supplier_address="London, UK",
                customer_name="Acme", currency="GBP", subtotal=100.0, tax=20.0, total=120.0,
                line_items=[LineItem(description="Work", quantity=2, unit_price=50.0, amount=100.0)])
    data.update(changes)
    return Invoice(**data)


def test_check_invoice_ok():
    assert check_invoice(make_invoice()) == "OK"


def test_check_invoice_items_equal_total_is_ok():
    items = [LineItem(description="Work incl. tax", quantity=1, unit_price=120.0, amount=120.0)]
    assert check_invoice(make_invoice(line_items=items)) == "OK"


def test_check_invoice_items_mismatch():
    items = [LineItem(description="Work", quantity=1, unit_price=90.0, amount=90.0)]
    status = check_invoice(make_invoice(line_items=items))
    assert status.startswith("CHECK:")
    assert "items add up to 90.0" in status


def test_check_invoice_tax_mismatch():
    assert "subtotal + tax does not equal total" in check_invoice(make_invoice(total=125.0))


def test_check_invoice_missing_number():
    assert "no invoice number" in check_invoice(make_invoice(invoice_number=""))


def test_to_rows():
    invoice, items = to_rows("a.pdf", make_invoice(), "OK")
    assert invoice == {"File": "a.pdf", "Invoice No": "INV-1", "Invoice Date": "2026-10-01",
                       "Due Date": "", "Supplier": "Brightline Ltd", "Supplier Address": "London, UK",
                       "Customer": "Acme", "Currency": "GBP", "Subtotal": 100.0, "Tax": 20.0,
                       "Total": 120.0, "Status": "OK"}
    assert items == [{"File": "a.pdf", "Invoice No": "INV-1", "Description": "Work",
                      "Quantity": 2.0, "Unit Price": 50.0, "Amount": 100.0}]


def test_extract_invoice_uses_reader(tmp_path):
    path = tmp_path / "inv.PDF"
    path.write_bytes(b"%PDF-1.4")
    invoice, items = extract_invoice(path, reader=lambda p: make_invoice())
    assert invoice["File"] == "inv.PDF"
    assert invoice["Status"] == "OK"
    assert len(items) == 1


def test_extract_invoice_unsupported_type(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("hello")

    def reader_must_not_run(p):
        raise AssertionError("reader should not be called")

    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_invoice(path, reader=reader_must_not_run)


def test_read_invoice_without_key(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    path = tmp_path / "inv.pdf"
    path.write_bytes(b"%PDF-1.4")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        read_invoice(path)


@pytest.mark.live
@pytest.mark.skipif(not config.GEMINI_API_KEY, reason="needs GEMINI_API_KEY in .env")
def test_extract_invoice_live():
    invoice, items = extract_invoice("samples/invoices/invoice_brightline.pdf")
    assert invoice["Currency"] == "GBP"
    assert invoice["Total"] == 303.56
    assert invoice["Status"] == "OK"
    assert items


@pytest.mark.parametrize("code,expected", [(429, True), (500, True), (503, True), (401, True),
                                           (403, True), (400, False), (404, False)])
def test_is_temporary(code, expected):
    assert is_temporary(code) is expected


def fake_client(error):
    class Models:
        def generate_content(self, **kwargs):
            raise error

    class Client:
        def __init__(self, api_key):
            self.models = Models()
    return Client


@pytest.fixture
def pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    path = tmp_path / "inv.pdf"
    path.write_bytes(b"%PDF-1.4")
    return path


def test_read_invoice_quota_error_is_temporary(pdf, monkeypatch):
    quota = errors.APIError(429, {"error": {"message": "quota", "status": "RESOURCE_EXHAUSTED"}})
    monkeypatch.setattr(invoices_module.genai, "Client", fake_client(quota))
    with pytest.raises(TemporaryError):
        read_invoice(pdf)


def test_read_invoice_network_error_is_temporary(pdf, monkeypatch):
    monkeypatch.setattr(invoices_module.genai, "Client", fake_client(httpx.ConnectError("offline")))
    with pytest.raises(TemporaryError):
        read_invoice(pdf)


def test_read_invoice_bad_file_is_not_temporary(pdf, monkeypatch):
    bad = errors.APIError(400, {"error": {"message": "bad document", "status": "INVALID_ARGUMENT"}})
    monkeypatch.setattr(invoices_module.genai, "Client", fake_client(bad))
    with pytest.raises(errors.APIError) as info:
        read_invoice(pdf)
    assert not isinstance(info.value, TemporaryError)
