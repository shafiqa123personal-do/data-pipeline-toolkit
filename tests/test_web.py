from datetime import datetime

from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.test import Client

from web.app import create_app
from web.demo import DemoRunner, RateLimiter


def scrape(pages, delay):
    return [{"Title": f"<b>Book {i}</b>", "Price": 9.5, "Rating": 4, "Link": f"https://b/{i}",
             "Page": 1} for i in range(pages * 20)]


def extract(path):
    return ({"File": path.name, "Supplier": "Brightline", "Invoice No": "INV-1", "Currency": "GBP",
             "Total": 303.56, "Status": "OK"},
            [{"File": path.name, "Description": "Paper", "Quantity": 2, "Amount": 303.56}])


def make_client(tmp_path, scrape=scrape, extract=extract, wait=30):
    runner = DemoRunner(tmp_path / "cache", "samples", scrape=scrape, extract=extract,
                        now=lambda: datetime(2026, 10, 15, 9, 30))
    app = create_app(runner=runner, limiter=RateLimiter(wait=wait))
    return app.test_client()


def test_page_shows_three_cards(tmp_path):
    html = make_client(tmp_path).get("/").get_data(as_text=True)
    for text in ("Web Scraping", "Data Extraction", "Lead Generation",
                 "https://www.fiverr.com/systemsyncai", "Pioneer Hardware (scanned photo)"):
        assert text in html


def test_page_shows_masked_leads_sample(tmp_path):
    html = make_client(tmp_path).get("/").get_data(as_text=True)
    assert "•" in html


def test_books_run_and_download(tmp_path):
    client = make_client(tmp_path)
    data = client.post("/books", data={"pages": "2"}).get_json()
    assert data["count"] == 40
    assert len(data["preview"]) == 10
    download = client.get(data["download"])
    assert download.status_code == 200
    assert download.data[:2] == b"PK"                       # an .xlsx is a zip file


def test_second_run_is_rate_limited(tmp_path):
    client = make_client(tmp_path)
    client.post("/books", data={"pages": "1"})
    response = client.post("/books", data={"pages": "1"})
    assert response.status_code == 429
    assert "wait" in response.get_json()["error"]


def test_bad_pages_rejected_without_using_slot(tmp_path):
    client = make_client(tmp_path)
    assert client.post("/books", data={"pages": "9"}).status_code == 400
    assert client.post("/books", data={"pages": "abc"}).status_code == 400
    assert client.post("/books", data={"pages": "1"}).status_code == 200


def test_books_unavailable_offers_sample(tmp_path):
    response = make_client(tmp_path, scrape=lambda pages, delay: []).post("/books", data={"pages": "1"})
    assert response.status_code == 503
    assert response.get_json()["sample"].endswith("/samples/books_report_sample.xlsx")


def test_invoice_run(tmp_path):
    data = make_client(tmp_path).post("/invoices", data={"invoice": "brightline"}).get_json()
    assert data["invoice"]["Total"] == 303.56
    assert data["items"][0]["Description"] == "Paper"
    assert "download" in data


def test_invoice_unknown_choice(tmp_path):
    assert make_client(tmp_path).post("/invoices", data={"invoice": "nope"}).status_code == 400


def test_invoice_unavailable_offers_sample(tmp_path):
    def broken(path):
        raise RuntimeError("Gemini down")

    response = make_client(tmp_path, extract=broken).post("/invoices", data={"invoice": "pioneer"})
    assert response.status_code == 503
    assert response.get_json()["sample"].endswith("/samples/invoices_sample.xlsx")


def test_download_unknown_file_is_404(tmp_path):
    client = make_client(tmp_path)
    assert client.get("/download/secret.xlsx").status_code == 404
    assert client.get("/samples/config.py").status_code == 404
    assert client.get("/invoice-file/nope").status_code == 404


def test_samples_and_original_invoices_are_served(tmp_path):
    client = make_client(tmp_path)
    assert client.get("/samples/leads_sample.xlsx").status_code == 200
    original = client.get("/invoice-file/pioneer")
    assert original.status_code == 200
    assert original.mimetype == "image/jpeg"


def test_works_when_mounted_under_prefix(tmp_path):
    app = make_client(tmp_path).application
    site = Client(DispatcherMiddleware(Flask("main_site"), {"/data-demo": app}))
    html = site.get("/data-demo/").get_data(as_text=True)
    assert 'data-url="/data-demo/books"' in html
    assert 'data-url="/data-demo/invoices"' in html
    assert "/data-demo/static/style.css" in html
    data = site.post("/data-demo/books", data={"pages": "1"}).get_json()
    assert data["download"].startswith("/data-demo/download/")
