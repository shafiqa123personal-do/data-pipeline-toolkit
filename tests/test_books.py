import pytest

from scrapers.books import parse_detail_page, parse_list_page, scrape_books

PAGE_URL = "https://books.toscrape.com/catalogue/page-1.html"

LIST_HTML = """
<article class="product_pod">
  <p class="star-rating Three"></p>
  <h3><a href="a-light-in-the-attic_1000/index.html" title="A Light in the Attic">A Light ...</a></h3>
  <div class="product_price"><p class="price_color">Â£51.77</p></div>
</article>
<article class="product_pod">
  <p class="star-rating One"></p>
  <h3><a href="tipping-the-velvet_999/index.html" title="Tipping the Velvet">Tipping ...</a></h3>
  <div class="product_price"><p class="price_color">£53.74</p></div>
</article>
"""

DETAIL_HTML = """
<ul class="breadcrumb">
  <li><a href="../index.html">Home</a></li>
  <li><a href="../category/books_1/index.html">Books</a></li>
  <li><a href="../category/books/poetry_23/index.html">Poetry</a></li>
  <li class="active">A Light in the Attic</li>
</ul>
<div id="product_description" class="sub-header"><h2>Product Description</h2></div>
<p>It's hard to imagine a world without A Light in the Attic.</p>
<p class="instock availability"><i class="icon-ok"></i> In stock (22 available) </p>
"""

DETAIL_NO_DESCRIPTION = """
<ul class="breadcrumb">
  <li><a href="../index.html">Home</a></li>
  <li><a href="../category/books_1/index.html">Books</a></li>
  <li><a href="../category/books/default_15/index.html">Default</a></li>
</ul>
<p class="instock availability"> In stock (1 available) </p>
"""


def test_parse_list_page():
    books = parse_list_page(LIST_HTML, PAGE_URL)
    assert books == [
        {"Title": "A Light in the Attic", "Price": 51.77, "Rating": 3,
         "Link": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"},
        {"Title": "Tipping the Velvet", "Price": 53.74, "Rating": 1,
         "Link": "https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html"},
    ]


def test_parse_list_page_missing_rating():
    html = LIST_HTML.replace('<p class="star-rating Three"></p>', "")
    assert parse_list_page(html, PAGE_URL)[0]["Rating"] is None


def test_parse_detail_page():
    assert parse_detail_page(DETAIL_HTML) == {
        "Stock": 22,
        "Category": "Poetry",
        "Description": "It's hard to imagine a world without A Light in the Attic.",
    }


def test_parse_detail_page_without_description():
    details = parse_detail_page(DETAIL_NO_DESCRIPTION)
    assert details["Description"] == "No description"
    assert details["Stock"] == 1


def fake_fetch(pages):
    """pages = {url: html or None}; unknown URLs return None (like a failed download)."""
    def _fetch(url):
        return pages.get(url)
    return _fetch


def test_scrape_books_two_pages():
    fetch = fake_fetch({
        "https://books.toscrape.com/catalogue/page-1.html": LIST_HTML,
        "https://books.toscrape.com/catalogue/page-2.html": LIST_HTML,
    })
    assert len(scrape_books(2, delay=0, fetch=fetch)) == 4


def test_scrape_books_skips_failed_page():
    fetch = fake_fetch({"https://books.toscrape.com/catalogue/page-2.html": LIST_HTML})
    books = scrape_books(2, delay=0, fetch=fetch)
    assert len(books) == 2


def test_scrape_books_with_details():
    fetch = fake_fetch({
        "https://books.toscrape.com/catalogue/page-1.html": LIST_HTML,
        "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html": DETAIL_HTML,
        "https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html": DETAIL_HTML,
    })
    books = scrape_books(1, details=True, delay=0, fetch=fetch)
    assert books[0]["Category"] == "Poetry"
    assert books[0]["Stock"] == 22


def test_scrape_books_details_failed_keeps_book():
    fetch = fake_fetch({"https://books.toscrape.com/catalogue/page-1.html": LIST_HTML})
    books = scrape_books(1, details=True, delay=0, fetch=fetch)
    assert len(books) == 2
    assert books[0]["Stock"] is None
    assert books[0]["Category"] == ""


def test_scrape_books_records_page_number():
    fetch = fake_fetch({
        "https://books.toscrape.com/catalogue/page-1.html": LIST_HTML,
        "https://books.toscrape.com/catalogue/page-2.html": LIST_HTML,
    })
    books = scrape_books(2, delay=0, fetch=fetch)
    assert [b["Page"] for b in books] == [1, 1, 2, 2]


def counting_fetch(pages, calls):
    def _fetch(url):
        calls.append(url)
        return pages.get(url)
    return _fetch


def test_scrape_books_stops_after_3_failed_pages_in_a_row():
    calls = []
    books = scrape_books(50, delay=0, fetch=counting_fetch({}, calls))
    assert books == []
    assert len(calls) == 3


def test_scrape_books_stops_after_3_failed_detail_pages_in_a_row():
    calls = []
    fetch = counting_fetch({"https://books.toscrape.com/catalogue/page-1.html": LIST_HTML * 2}, calls)
    books = scrape_books(2, details=True, delay=0, fetch=fetch)
    assert len(calls) == 4                     # list page + 3 failed detail pages, then stop
    assert len(books) == 4                     # books from page 1 are kept, with blank details
    assert all(b["Stock"] is None for b in books)


@pytest.mark.parametrize("pages", [0, 51])
def test_scrape_books_rejects_bad_page_count(pages):
    with pytest.raises(ValueError):
        scrape_books(pages, fetch=fake_fetch({}))


@pytest.mark.live
def test_scrape_books_live():
    books = scrape_books(1, delay=0)
    assert len(books) == 20
    for book in books:
        assert book["Title"]
        assert isinstance(book["Price"], float)
        assert book["Rating"] in {1, 2, 3, 4, 5}
        assert book["Link"].startswith("https://books.toscrape.com/catalogue/")
