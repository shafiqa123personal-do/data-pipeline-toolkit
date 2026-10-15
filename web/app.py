"""Live demo page for the Data Pipeline Toolkit.

Run locally:   python -m web.app    ->  http://127.0.0.1:5000
On PythonAnywhere it is mounted at /data-demo (see docs/DEPLOY_PYTHONANYWHERE.md)."""
from flask import Flask, abort, jsonify, render_template, request, send_from_directory, url_for

import config
from core.excel import read_sheet
from web.demo import DEMO_INVOICES, MAX_DEMO_PAGES, DemoError, DemoRunner, RateLimiter

SAMPLES_DIR = config.PROJECT_DIR / "samples"
SAMPLE_FILES = {"books_report_sample.xlsx", "invoices_sample.xlsx", "leads_sample.xlsx"}
FIVERR_URL = "https://www.fiverr.com/systemsyncai"
GITHUB_URL = "https://github.com/shafiqa123personal-do/data-pipeline-toolkit"


def create_app(runner=None, limiter=None):
    app = Flask(__name__)
    app.config["SESSION_COOKIE_NAME"] = "data_demo_session"   # don't clash with the other apps
    runner = runner or DemoRunner(config.OUTPUT_DIR / "demo_cache", SAMPLES_DIR)
    limiter = limiter or RateLimiter()

    def visitor():
        return request.headers.get("X-Real-IP") or request.remote_addr or "unknown"

    def too_soon(card):
        wait = limiter.check(f"{visitor()}:{card}")
        if wait:
            return jsonify(error=f"Please wait {wait} seconds before running this again."), 429
        return None

    def unavailable(error, sample_name):
        return jsonify(error=str(error), sample=url_for("sample", name=sample_name)), 503

    @app.get("/")
    def index():
        leads_file = SAMPLES_DIR / "leads_sample.xlsx"
        leads = read_sheet(leads_file, "Leads")[:8] if leads_file.exists() else []
        return render_template("data_demo.html", invoices=DEMO_INVOICES, max_pages=MAX_DEMO_PAGES,
                               leads=leads, fiverr_url=FIVERR_URL, github_url=GITHUB_URL)

    @app.post("/books")
    def books():
        pages = request.form.get("pages", "")
        if not pages.isdigit() or not 1 <= int(pages) <= MAX_DEMO_PAGES:
            return jsonify(error=f"Choose between 1 and {MAX_DEMO_PAGES} pages."), 400
        if (blocked := too_soon("books")) is not None:
            return blocked
        try:
            result = runner.books(int(pages))
        except DemoError as error:
            return unavailable(error, "books_report_sample.xlsx")
        result["download"] = url_for("download", name=result["file"])
        return jsonify(result)

    @app.post("/invoices")
    def invoices():
        key = request.form.get("invoice", "")
        if key not in DEMO_INVOICES:
            return jsonify(error="Please choose one of the sample invoices."), 400
        if (blocked := too_soon("invoices")) is not None:
            return blocked
        try:
            result = runner.invoice(key)
        except DemoError as error:
            return unavailable(error, "invoices_sample.xlsx")
        result["download"] = url_for("download", name=result["file"])
        return jsonify(result)

    @app.get("/download/<name>")
    def download(name):
        path = runner.file_path(name)
        if path is None:
            abort(404)
        return send_from_directory(path.parent, path.name, as_attachment=True)

    @app.get("/samples/<name>")
    def sample(name):
        if name not in SAMPLE_FILES:
            abort(404)
        return send_from_directory(SAMPLES_DIR, name, as_attachment=True)

    @app.get("/invoice-file/<key>")
    def invoice_file(key):
        if key not in DEMO_INVOICES:
            abort(404)
        return send_from_directory(SAMPLES_DIR / "invoices", DEMO_INVOICES[key]["file"])

    return app


if __name__ == "__main__":
    create_app().run(debug=False)
