import os
import time
from datetime import datetime, timedelta

import pytest

from web.demo import DEMO_INVOICES, DemoError, DemoRunner, RateLimiter


def fake_scrape(calls):
    def _scrape(pages, delay):
        calls.append(pages)
        return [{"Title": f"Book {i}", "Price": 10.0 + i, "Rating": 3, "Link": f"https://b/{i}",
                 "Page": 1 + i // 20} for i in range(pages * 20)]
    return _scrape


def fake_extract(calls):
    def _extract(path):
        calls.append(path.name)
        return ({"File": path.name, "Supplier": "Brightline", "Currency": "GBP", "Total": 303.56,
                 "Status": "OK"}, [{"File": path.name, "Description": "Paper", "Amount": 303.56}])
    return _extract


class Clock:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


@pytest.fixture
def runner(tmp_path):
    scrapes, extracts = [], []
    clock = Clock(datetime(2026, 10, 15, 9, 30))
    demo = DemoRunner(tmp_path / "cache", tmp_path / "samples", scrape=fake_scrape(scrapes),
                      extract=fake_extract(extracts), now=clock)
    return demo, scrapes, extracts, clock


def test_books_result(runner):
    demo, scrapes, _, _ = runner
    result = demo.books(2)
    assert result["count"] == 40
    assert len(result["preview"]) == 10
    assert result["preview"][0]["Title"] == "Book 0"
    assert {row["Metric"] for row in result["summary"]} >= {"Total books", "Average price (£)"}
    assert demo.file_path(result["file"]).exists()


def test_books_cached_within_the_hour(runner):
    demo, scrapes, _, clock = runner
    demo.books(1)
    clock.value = datetime(2026, 10, 15, 9, 59)
    demo.books(1)
    assert scrapes == [1]
    clock.value = datetime(2026, 10, 15, 10, 1)
    demo.books(1)
    assert scrapes == [1, 1]


def test_books_bad_page_count(runner):
    demo, *_ = runner
    for pages in (0, 6):
        with pytest.raises(DemoError):
            demo.books(pages)


def test_books_unavailable(tmp_path):
    demo = DemoRunner(tmp_path, tmp_path, scrape=lambda pages, delay: [])
    with pytest.raises(DemoError, match="sample"):
        demo.books(1)


def test_invoice_result(runner):
    demo, _, extracts, _ = runner
    result = demo.invoice("brightline")
    assert result["invoice"]["Total"] == 303.56
    assert result["items"][0]["Description"] == "Paper"
    assert extracts == [DEMO_INVOICES["brightline"]["file"]]


def test_invoice_is_cached_for_the_day(runner):
    demo, _, extracts, clock = runner
    demo.invoice("brightline")
    clock.value = datetime(2026, 10, 15, 23, 0)
    demo.invoice("brightline")
    assert len(extracts) == 1


def test_invoice_unknown_key(runner):
    demo, *_ = runner
    with pytest.raises(DemoError):
        demo.invoice("../../.env")


def test_invoice_unavailable(tmp_path):
    def broken(path):
        raise RuntimeError("Gemini down")

    demo = DemoRunner(tmp_path, tmp_path, extract=broken)
    with pytest.raises(DemoError, match="sample"):
        demo.invoice("pioneer")


def test_file_path_rejects_unknown_names(runner):
    demo, *_ = runner
    for name in ("../config.py", "books-1.xlsx", "secret.xlsx", "books-9-20261015-09.xlsx"):
        assert demo.file_path(name) is None


def test_old_cache_files_are_cleaned(runner):
    demo, _, _, _ = runner
    old = demo.cache_dir / "books-1-20261001-09.xlsx"
    demo.cache_dir.mkdir(parents=True, exist_ok=True)
    old.write_bytes(b"old")
    week_ago = time.time() - 7 * 24 * 3600
    os.utime(old, (week_ago, week_ago))
    demo.books(1)
    assert not old.exists()


def test_rate_limiter():
    clock = Clock(100.0)
    limiter = RateLimiter(wait=30, clock=clock)
    assert limiter.check("1.2.3.4:books") == 0
    clock.value = 110.0
    assert limiter.check("1.2.3.4:books") == 20
    assert limiter.check("1.2.3.4:invoices") == 0      # other card is separate
    assert limiter.check("5.6.7.8:books") == 0         # other visitor is separate
    clock.value = 131.0
    assert limiter.check("1.2.3.4:books") == 0


def test_scrape_crash_becomes_friendly_error(tmp_path):
    def crash(pages, delay):
        raise RuntimeError("site layout changed")

    demo = DemoRunner(tmp_path, tmp_path, scrape=crash)
    with pytest.raises(DemoError, match="sample"):
        demo.books(1)


def test_failure_is_remembered_for_a_few_minutes(tmp_path):
    calls = []
    clock = Clock(datetime(2026, 10, 15, 9, 30))

    def down(pages, delay):
        calls.append(pages)
        return []

    demo = DemoRunner(tmp_path, tmp_path, scrape=down, now=clock)
    for _ in range(3):
        with pytest.raises(DemoError):
            demo.books(1)
    assert calls == [1]                            # no new attempt while the site is down
    clock.value += timedelta(minutes=6)
    with pytest.raises(DemoError):
        demo.books(1)
    assert calls == [1, 1]


def test_invoice_failure_is_remembered(tmp_path):
    calls = []

    def broken(path):
        calls.append(path)
        raise RuntimeError("Gemini down")

    demo = DemoRunner(tmp_path, tmp_path, extract=broken,
                      now=lambda: datetime(2026, 10, 15, 9, 30))
    for key in ("brightline", "greenleaf"):
        with pytest.raises(DemoError):
            demo.invoice(key)
    assert len(calls) == 1


def test_live_runs_are_capped_per_hour(runner):
    demo, scrapes, _, _ = runner
    demo.max_live_runs = 2
    demo.books(1)
    demo.books(2)
    with pytest.raises(DemoError, match="busy"):
        demo.books(3)
    demo.books(1)                                  # cached results are always fine
    assert scrapes == [1, 2]


def test_partial_scrape_is_labelled_and_tried_again(tmp_path):
    calls = []

    def half(pages, delay):
        calls.append(pages)
        return fake_scrape([])(pages - 1, delay)    # one page short

    demo = DemoRunner(tmp_path, tmp_path, scrape=half, now=lambda: datetime(2026, 10, 15, 9, 30))
    result = demo.books(2)
    assert result["partial"] is True
    assert result["count"] == 20
    assert demo.file_path(result["file"]) is not None
    demo.books(2)
    assert calls == [2, 2]                         # partial results are not kept for the hour


def test_full_scrape_is_not_partial(runner):
    demo, *_ = runner
    assert demo.books(1)["partial"] is False


def test_result_says_how_old_it_is(runner):
    demo, _, _, clock = runner
    assert demo.books(1)["minutes_ago"] == 0
    clock.value = datetime(2026, 10, 15, 9, 50)
    assert demo.books(1)["minutes_ago"] == 20


def test_file_path_rejects_page_counts_above_the_limit(runner):
    demo, *_ = runner
    demo.cache_dir.mkdir(parents=True, exist_ok=True)
    (demo.cache_dir / "books-12-20261015-09.xlsx").write_bytes(b"x")
    assert demo.file_path("books-12-20261015-09.xlsx") is None


def test_old_tmp_files_are_cleaned(runner):
    demo, *_ = runner
    demo.cache_dir.mkdir(parents=True, exist_ok=True)
    leftover = demo.cache_dir / "books-1-20261001-09.xlsx.tmp"
    leftover.write_bytes(b"half written")
    week_ago = time.time() - 7 * 24 * 3600
    os.utime(leftover, (week_ago, week_ago))
    demo.books(1)
    assert not leftover.exists()


def test_rate_limiter_forgets_old_visitors():
    clock = Clock(0.0)
    limiter = RateLimiter(wait=30, clock=clock)
    for n in range(100):
        limiter.check(f"10.0.0.{n}:books")
    clock.value = 100.0
    limiter.check("1.2.3.4:books")
    assert len(limiter.last_run) == 1
