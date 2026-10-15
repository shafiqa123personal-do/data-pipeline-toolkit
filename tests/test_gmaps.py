from scrapers.gmaps import dedupe_leads, search_url


def test_search_url():
    assert search_url("plumbers in london") == \
        "https://www.google.com/maps/search/plumbers+in+london?hl=en"


def test_dedupe_leads_by_place_url():
    leads = [{"Name": "A", "Address": "1 St", "Maps URL": "https://maps/place/a?x=1"},
             {"Name": "A", "Address": "1 St", "Maps URL": "https://maps/place/a?x=2"}]
    assert len(dedupe_leads(leads)) == 1


def test_dedupe_leads_by_name_and_address():
    leads = [{"Name": "A", "Address": "1 St", "Maps URL": "https://maps/place/a1"},
             {"Name": "A", "Address": "1 St", "Maps URL": "https://maps/place/a2"},
             {"Name": "A", "Address": "2 St", "Maps URL": "https://maps/place/a3"}]
    assert [lead["Maps URL"] for lead in dedupe_leads(leads)] == \
        ["https://maps/place/a1", "https://maps/place/a3"]


def test_dedupe_leads_without_address_keeps_same_name_branches():
    leads = [{"Name": "Pimlico Plumbers", "Maps URL": "https://maps/place/p1"},
             {"Name": "Pimlico Plumbers", "Maps URL": "https://maps/place/p2"}]
    assert len(dedupe_leads(leads, by_address=False)) == 2
