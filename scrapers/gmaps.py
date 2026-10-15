"""Google Maps business leads with Selenium. Runs on your own PC (needs Chrome).

Collects public business information only: name, category, rating, phone,
website and address."""
import logging
import time
from urllib.parse import quote_plus

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.clean import strip_tracking

log = logging.getLogger(__name__)


def search_url(search):
    return "https://www.google.com/maps/search/" + quote_plus(search) + "?hl=en"


def dedupe_leads(leads, by_address=True):
    """Remove repeats: same place URL, and (by_address) same name + address."""
    unique, seen_places, seen_pairs = [], set(), set()
    for lead in leads:
        place = lead.get("Maps URL", "").split("?")[0]
        pair = (lead.get("Name", ""), lead.get("Address", ""))
        if place in seen_places or (by_address and pair in seen_pairs):
            continue
        seen_places.add(place)
        seen_pairs.add(pair)
        unique.append(lead)
    return unique


def scrape_gmaps(searches, max_results=20, driver=None):
    own_driver = driver is None
    if own_driver:
        driver = _make_driver()
    try:
        found = []
        for search in searches:
            log.info("Searching: %s", search)
            try:
                found.extend(_search_results(driver, search, max_results))
            except Exception as error:
                log.error("Search failed, skipping: %s (%s)", search, error)
        leads = dedupe_leads(found, by_address=False)   # by place URL before opening pages
        for number, lead in enumerate(leads, start=1):
            log.info("[%d/%d] %s", number, len(leads), lead["Name"])
            _add_details(driver, lead)
    finally:
        if own_driver:
            driver.quit()
    leads = dedupe_leads(leads)                    # again, now that addresses are known
    log.info("Collected %d unique leads", len(leads))
    return leads


def _make_driver():
    options = webdriver.ChromeOptions()
    options.add_experimental_option("excludeSwitches", ["enable-logging"])  # hide Chrome's noise
    return webdriver.Chrome(options=options)


def _search_results(driver, search, max_results):
    driver.get(search_url(search))
    feed = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="feed"]')))
    last_count, no_change = 0, 0
    while True:                                    # scroll the list to load more businesses
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", feed)
        time.sleep(2)
        results = driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc")
        if len(results) >= max_results or "end of the list" in driver.page_source:
            break
        no_change = no_change + 1 if len(results) == last_count else 0
        if no_change == 3:
            break
        last_count = len(results)
    log.info("   %d results for %s", min(len(results), max_results), search)
    return [{"Name": r.get_attribute("aria-label"), "Search": search,
             "Maps URL": r.get_attribute("href")} for r in results[:max_results]]


def _add_details(driver, lead):
    lead.update({"Category": "", "Rating": None, "Phone": "", "Website": "", "Address": ""})
    url = lead["Maps URL"]
    try:
        driver.get(url + ("&" if "?" in url else "?") + "hl=en")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1")))
        time.sleep(2)
        lead["Category"] = _text(driver, "button.DkEaL")
        lead["Rating"] = _to_float(_text(driver, 'div.F7nice span[aria-hidden="true"]'))
        lead["Address"] = _text(driver, 'button[data-item-id="address"]', "Address:")
        lead["Phone"] = _text(driver, 'button[data-item-id^="phone:tel:"]', "Phone:")
        website = driver.find_elements(By.CSS_SELECTOR, 'a[data-item-id="authority"]')
        if website:
            lead["Website"] = strip_tracking(website[0].get_attribute("href"))
    except Exception as error:
        log.error("   details failed for %s (%s)", lead["Name"], error)


def _text(driver, selector, remove=""):
    found = driver.find_elements(By.CSS_SELECTOR, selector)
    if not found:
        return ""
    text = found[0].get_attribute("aria-label") or found[0].text
    return text.replace(remove, "").strip()


def _to_float(text):
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None
