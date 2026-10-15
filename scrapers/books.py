"""Scrape books.toscrape.com: list pages, and optionally each book's detail page."""
import logging
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from core.clean import parse_price, parse_rating, parse_stock
from core.http import get_page

log = logging.getLogger(__name__)

PAGE_URL = "https://books.toscrape.com/catalogue/page-{}.html"
MAX_PAGES = 50


def parse_list_page(html, page_url):
    """One catalogue page -> list of books (title, price, rating, link)."""
    soup = BeautifulSoup(html, "html.parser")
    books = []
    for card in soup.select("article.product_pod"):
        link = card.select_one("h3 a")
        rating_box = card.select_one("p.star-rating")
        rating_word = ""
        if rating_box:
            rating_word = next((c for c in rating_box["class"] if c != "star-rating"), "")
        books.append({
            "Title": link["title"],
            "Price": parse_price(card.select_one("p.price_color").text),
            "Rating": parse_rating(rating_word),
            "Link": urljoin(page_url, link["href"]),
        })
    return books


def parse_detail_page(html):
    """One book page -> stock, category, description (blank values if missing)."""
    soup = BeautifulSoup(html, "html.parser")
    stock = soup.select_one("p.availability")
    crumbs = soup.select("ul.breadcrumb a")
    description = soup.select_one("#product_description + p")
    return {
        "Stock": parse_stock(stock.text) if stock else None,
        "Category": crumbs[2].text.strip() if len(crumbs) > 2 else "",
        "Description": description.text.strip() if description else "No description",
    }


def scrape_books(pages, details=False, delay=1, fetch=get_page):
    """Scrape catalogue pages 1..pages. Failed pages are logged and skipped."""
    if not 1 <= pages <= MAX_PAGES:
        raise ValueError(f"pages must be between 1 and {MAX_PAGES}")

    books = []
    for page in range(1, pages + 1):
        url = PAGE_URL.format(page)
        log.info("Page %d of %d", page, pages)
        html = fetch(url)
        if html is None:
            log.error("Skipping page %d - could not load it", page)
            continue

        page_books = parse_list_page(html, url)
        if details:
            for book in page_books:
                detail_html = fetch(book["Link"])
                if detail_html is None:
                    log.error("No details for %s", book["Link"])
                    book.update({"Stock": None, "Category": "", "Description": ""})
                else:
                    book.update(parse_detail_page(detail_html))
                time.sleep(delay)
        books.extend(page_books)
        if page < pages:
            time.sleep(delay)                      # be polite between pages

    log.info("Scraped %d books", len(books))
    return books
