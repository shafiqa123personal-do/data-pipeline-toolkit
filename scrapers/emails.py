"""Find public business emails on each lead's website (home page, then Contact page)."""
import logging
import re
import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from core.http import get_page

log = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Fake / junk emails that websites use as examples or inside code and images
JUNK_WORDS = ["example", "domain.com", "yourname", "emailname", "user@", "name@", "you@",
              "email.com", ".test", "sentry", "wixpress", "godaddy",
              "@2x", ".png", ".jpg", ".gif", ".webp", ".svg"]

# Free email providers that small businesses often use
FREE_PROVIDERS = ["gmail.com", "outlook.com", "hotmail.com", "hotmail.co.uk", "live.com",
                  "yahoo.com", "yahoo.co.uk", "ymail.com", "aol.com", "icloud.com",
                  "btinternet.com", "talktalk.net", "sky.com", "virginmedia.com", "protonmail.com"]


def quick_fetch(url):
    """Business websites are often slow or dead - one try, short timeout."""
    return get_page(url, retries=1, timeout=10)


def website_domain(website):
    """'https://www.abc.co.uk/x' -> 'abc.co.uk'"""
    return urlparse(website).netloc.lower().removeprefix("www.")


def is_trusted(email, website):
    """True if the email belongs to the business (its own domain or a free provider)."""
    email_domain = email.split("@")[1]
    domain = website_domain(website)
    if domain and (email_domain == domain or email_domain.endswith("." + domain)):
        return True
    return email_domain in FREE_PROVIDERS


def find_emails(html):
    emails = []
    for email in EMAIL_PATTERN.findall(html):
        email = email.lower()
        if not any(word in email for word in JUNK_WORDS) and email not in emails:
            emails.append(email)
    return emails


def find_contact_page(html, website):
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("a[href]"):
        if "contact" in a["href"].lower() or "contact" in a.text.lower():
            return urljoin(website, a["href"])
    return ""


def emails_for_website(website, fetch=quick_fetch):
    html = fetch(website) or ""
    emails = [e for e in find_emails(html) if is_trusted(e, website)]
    if not emails:
        contact = find_contact_page(html, website)
        if contact:
            emails = [e for e in find_emails(fetch(contact) or "") if is_trusted(e, website)]
    return emails[:3]


def add_emails(leads, fetch=quick_fetch, delay=1):
    found = 0
    for number, lead in enumerate(leads, start=1):
        lead["Email"] = ""
        website = lead.get("Website")
        if not website:
            continue
        log.info("[%d/%d] emails for %s", number, len(leads), website)
        emails = emails_for_website(website, fetch)
        if emails:
            lead["Email"] = ", ".join(emails)
            found += 1
        time.sleep(delay)                          # be polite
    log.info("Found emails for %d of %d leads", found, len(leads))
    return leads
