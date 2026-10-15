"""Fiverr portfolio images (1280x769) built from the real sample outputs:

    python tools/portfolio_images.py   ->  docs/images/portfolio_1.png, _2.png, _3.png"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.excel import read_sheet  # noqa: E402

OUT = ROOT / "docs" / "images"
SAMPLES = ROOT / "samples"
W, H = 1280, 769
PURPLE, VIOLET, INK, MUTED, WHITE, SOFT = "#7c5cff", "#a855f7", "#1f2333", "#5b6070", "#ffffff", "#f4f0ff"
GREEN = "#15803d"


def font(size, bold=False):
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    try:
        return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)
    except OSError:
        return ImageFont.load_default(size)


def canvas():
    image = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(image)
    for y in range(170):                                       # purple header band
        t = y / 170
        r = int(0x7c + (0xa8 - 0x7c) * t)
        g = int(0x5c + (0x55 - 0x5c) * t)
        b = int(0xff + (0xf7 - 0xff) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    return image, draw


def header(draw, title, subtitle):
    draw.text((60, 40), title, font=font(46, True), fill=WHITE)
    draw.text((62, 105), subtitle, font=font(24), fill=WHITE)


def card(draw, box, title, lines, accent=PURPLE):
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=18, fill=SOFT, outline="#e2dbff", width=2)
    draw.text((x0 + 24, y0 + 20), title, font=font(26, True), fill=accent)
    y = y0 + 70
    for line in lines:
        draw.text((x0 + 24, y), line, font=font(21), fill=INK)
        y += 36


def table(draw, x, y, headers, rows, widths, size=18):
    draw.rectangle([x, y, x + sum(widths), y + 34], fill="#ece6ff")
    cx = x
    for text, width in zip(headers, widths):
        draw.text((cx + 8, y + 7), text, font=font(size, True), fill=INK)
        cx += width
    y += 34
    for row in rows:
        cx = x
        for text, width in zip(row, widths):
            value = str(text if text is not None else "")
            while value and draw.textlength(value, font=font(size)) > width - 14:
                value = value[:-2] + "…" if len(value) > 2 else ""
            draw.text((cx + 8, y + 7), value, font=font(size), fill=INK)
            cx += width
        draw.line([(x, y + 34), (x + sum(widths), y + 34)], fill="#e5e5ee")
        y += 34
    return y


def metric(rows, name):
    return next((r["Value"] for r in rows if r["Metric"] == name), "")


def overview():
    books = read_sheet(SAMPLES / "books_report_sample.xlsx", "Summary")
    invoices = read_sheet(SAMPLES / "invoices_sample.xlsx", "Summary")
    leads = read_sheet(SAMPLES / "leads_sample.xlsx", "Summary")
    image, draw = canvas()
    header(draw, "Data Pipeline Toolkit", "Web scraping  ·  AI data extraction  ·  Python automation")
    card(draw, (60, 210, 440, 600), "Web Scraping",
         [f"{metric(books, 'Total books')} products scraped", f"Avg price £{metric(books, 'Average price (£)')}",
          "Retries, polite delays", "Excel + Summary + Changes", "Price-change tracking"])
    card(draw, (450, 210, 830, 600), "Data Extraction",
         [f"{metric(invoices, 'Invoices')} invoices read by AI", f"{metric(invoices, 'Need checking')} need checking",
          "PDFs and phone photos", "Line items + totals check", "Never processed twice"])
    card(draw, (840, 210, 1220, 600), "Lead Generation",
         [f"{metric(leads, 'Total leads')} leads (sample)", f"With phone: {metric(leads, 'With phone')}",
          f"With website: {metric(leads, 'With website')}", f"With email: {metric(leads, 'With email')}",
          "Duplicates removed"])
    draw.text((60, 640), "Delivered as Excel · runs on a schedule · emails the report",
              font=font(26, True), fill=INK)
    draw.text((60, 690), "Live demo: systemsyncai.pythonanywhere.com/data-demo", font=font(22), fill=MUTED)
    image.save(OUT / "portfolio_1.png")


def invoice_before_after():
    invoices = read_sheet(SAMPLES / "invoices_sample.xlsx", "Invoices")
    items = read_sheet(SAMPLES / "invoices_sample.xlsx", "Line Items")
    pioneer = next(r for r in invoices if "pioneer" in str(r["File"]).lower())
    image, draw = canvas()
    header(draw, "Invoice → Excel with AI", "A tilted phone photo of a receipt becomes clean, checked data")
    photo = Image.open(SAMPLES / "invoices" / "scanned_receipt_pioneer.jpg")
    photo.thumbnail((360, 540))
    image.paste(photo, (60, 205))
    draw.text((60 + photo.width + 20, 430), "→", font=font(64, True), fill=PURPLE)
    x = 60 + photo.width + 100
    y = table(draw, x, 210, ["Field", "Extracted"],
              [["Supplier", pioneer["Supplier"]], ["Invoice No", pioneer["Invoice No"]],
               ["Date", pioneer["Invoice Date"]], ["Total", f"{pioneer['Currency']} {pioneer['Total']}"],
               ["Check", pioneer["Status"]]], [200, W - x - 260])
    rows = [[i["Description"], i["Quantity"], i["Amount"]] for i in items
            if "pioneer" in str(i["File"]).lower()][:6]
    table(draw, x, y + 30, ["Item", "Qty", "Amount"], rows, [W - x - 260, 100, 100])
    image.save(OUT / "portfolio_2.png")


def automation():
    image, draw = canvas()
    header(draw, "Runs by itself", "Scheduled jobs · one command per task · a log of every run")
    draw.rounded_rectangle((60, 205, 1220, 560), radius=16, fill="#14161f")
    log = ["> python run.py invoices",
           "[1/4] invoice_brightline.pdf   Brightline Office Supplies | GBP 303.56 | OK",
           "[2/4] invoice_greenleaf.pdf    Greenleaf Cleaning Services | USD 789.14 | OK",
           "[3/4] invoice_nova.pdf         NOVA WEB STUDIO | GBP 289.99 | OK",
           "[4/4] scanned_receipt_pioneer.jpg  PIONEER HARDWARE & TOOLS | USD 174.24 | OK",
           "Master file updated: invoices_master.xlsx",
           "DONE: 4 invoices added, 0 failed",
           "> python run.py books --pages 3",
           "DONE: 60 books -> books_report_2026-10-15_2117.xlsx   (Changes sheet vs last run)"]
    y = 225
    for line in log:
        draw.text((84, y), line, font=font(20), fill="#9be59b" if line.startswith(">") else "#e6e6f0")
        y += 36
    features = [(60, 600, "Stops safely if the internet or AI is down"),
                (660, 600, "Never processes an invoice twice"),
                (60, 650, "Excel open? Clear message, nothing lost"),
                (660, 650, "Optional email with the report")]
    for x, y, text in features:
        check(draw, x, y + 4)
        draw.text((x + 34, y), text, font=font(24, True), fill=GREEN)
    image.save(OUT / "portfolio_3.png")


def check(draw, x, y):
    """A drawn tick - Segoe UI has no ✔ glyph."""
    draw.line([(x, y + 13), (x + 8, y + 22), (x + 22, y + 4)], fill=GREEN, width=5)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    overview()
    invoice_before_after()
    automation()
    print("Saved portfolio images to", OUT)
