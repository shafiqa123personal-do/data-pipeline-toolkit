"""Download web pages politely: browser User-Agent, timeout, retries."""
import logging
import time

import requests

log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"}


def get_page(url, retries=3, delay=3, timeout=15):
    """Return the page HTML as text, or None if every attempt failed."""
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            response.encoding = "utf-8"
            return response.text
        except requests.exceptions.HTTPError as error:
            if error.response is not None and error.response.status_code < 500:
                log.error("%s returned %s - not retrying", url, error.response.status_code)
                return None
            log.warning("Attempt %d/%d failed for %s: %s", attempt, retries, url, error)
        except requests.exceptions.RequestException as error:
            log.warning("Attempt %d/%d failed for %s: %s", attempt, retries, url, error)
        if attempt < retries:
            time.sleep(delay)
    log.error("Giving up on %s after %d attempts", url, retries)
    return None
