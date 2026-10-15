from core.clean import parse_price, parse_rating, parse_stock, strip_tracking


def test_parse_price_pounds():
    assert parse_price("£51.77") == 51.77


def test_parse_price_mojibake_and_commas():
    assert parse_price("Â£1,234.50") == 1234.5


def test_parse_price_no_number():
    assert parse_price("") is None
    assert parse_price("free") is None


def test_parse_rating_words():
    assert parse_rating("Three") == 3
    assert parse_rating(" five ") == 5


def test_parse_rating_unknown():
    assert parse_rating("Zero") is None


def test_parse_stock():
    assert parse_stock("In stock (22 available)") == 22


def test_parse_stock_without_count():
    assert parse_stock("In stock") is None


def test_strip_tracking_keeps_other_params():
    assert strip_tracking("https://a.com/?utm_source=g&x=1") == "https://a.com/?x=1"


def test_strip_tracking_removes_question_mark_when_empty():
    assert strip_tracking("https://a.com/page?utm_source=g&UTM_medium=m") == "https://a.com/page"
