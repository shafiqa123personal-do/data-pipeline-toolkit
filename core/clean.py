"""Small helpers that turn messy scraped text into clean values."""
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

RATING_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def parse_price(text):
    """'£51.77' -> 51.77. Returns None when there is no number."""
    cleaned = "".join(ch for ch in text if ch.isdigit() or ch == ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_rating(word):
    """'Three' -> 3. Returns None for unknown words."""
    return RATING_WORDS.get(word.strip().title())


def parse_stock(text):
    """'In stock (22 available)' -> 22. Returns None when no count is shown."""
    match = re.search(r"\((\d+) available\)", text)
    return int(match.group(1)) if match else None


def strip_tracking(url):
    """Remove utm_* tracking parameters from a link, keep everything else."""
    parts = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
             if not key.lower().startswith("utm_")]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
