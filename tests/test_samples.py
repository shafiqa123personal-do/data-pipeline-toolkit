from tools.make_samples import generic_emails, mask_leads, mask_phone


def test_mask_phone():
    assert mask_phone("020 7123 4567") == "020 •••• ••67"
    assert mask_phone("+44 20 7123 4567") == "+44 2• •••• ••67"
    assert mask_phone("") == ""


def test_generic_emails_only():
    text = "info@abc.co.uk, john.smith@abc.co.uk, abcplumbing@gmail.com, Hello@abc.co.uk"
    assert generic_emails(text) == "info@abc.co.uk, hello@abc.co.uk"


def test_mask_leads_drops_private_columns():
    lead = {"Name": "ABC Plumbing", "Search": "plumbers in london", "Maps URL": "https://maps/x",
            "Category": "Plumber", "Rating": 4.8, "Phone": "020 7123 4567",
            "Website": "https://abc.co.uk/", "Address": "1 High St", "Email": "jo@abc.co.uk"}
    assert mask_leads([lead]) == [{"Name": "ABC Plumbing", "Category": "Plumber", "Rating": 4.8,
                                   "Phone": "020 •••• ••67", "Website": "https://abc.co.uk/",
                                   "Address": "1 High St", "Email": ""}]
