from scrapers.emails import add_emails, emails_for_website, find_contact_page, find_emails, is_trusted

SITE = "https://www.abcplumbing.co.uk/"


def test_find_emails_cleans_and_dedupes():
    html = "Mail INFO@abcplumbing.co.uk or info@abcplumbing.co.uk, logo@2x.png, you@example.com"
    assert find_emails(html) == ["info@abcplumbing.co.uk"]


def test_is_trusted_same_domain_and_subdomain():
    assert is_trusted("info@abcplumbing.co.uk", SITE)
    assert is_trusted("jo@mail.abcplumbing.co.uk", SITE)


def test_is_trusted_free_provider():
    assert is_trusted("abcplumbing@gmail.com", SITE)


def test_is_trusted_rejects_other_companies():
    assert not is_trusted("hello@webdesignco.com", SITE)
    assert not is_trusted("info@notabcplumbing.co.uk", SITE)


def test_find_contact_page():
    html = '<a href="/about">About</a><a href="/contact-us">Contact</a>'
    assert find_contact_page(html, SITE) == "https://www.abcplumbing.co.uk/contact-us"
    assert find_contact_page("<p>nothing</p>", SITE) == ""


def test_emails_for_website_home_page():
    pages = {SITE: "info@abcplumbing.co.uk hello@webdesignco.com"}
    assert emails_for_website(SITE, fetch=pages.get) == ["info@abcplumbing.co.uk"]


def test_emails_for_website_falls_back_to_contact_page():
    pages = {SITE: '<a href="/contact">Contact</a>',
             "https://www.abcplumbing.co.uk/contact": "office@abcplumbing.co.uk"}
    assert emails_for_website(SITE, fetch=pages.get) == ["office@abcplumbing.co.uk"]


def test_add_emails_handles_missing_and_dead_websites():
    leads = [{"Name": "No site", "Website": ""}, {"Name": "Dead", "Website": "https://dead.test/"},
             {"Name": "ABC", "Website": SITE}]
    pages = {SITE: "info@abcplumbing.co.uk"}
    result = add_emails(leads, fetch=pages.get, delay=0)
    assert [lead["Email"] for lead in result] == ["", "", "info@abcplumbing.co.uk"]
