import pytest

import run


def fake_books(pages, details=False):
    return [{"Title": "A", "Price": 10.0, "Rating": 3, "Link": "https://books.test/a"}]


def test_main_books_success(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "scrape_books", fake_books)
    code = run.main(["books", "--pages", "2"], output_dir=tmp_path / "out", log_dir=tmp_path / "logs")
    assert code == 0
    assert len(list((tmp_path / "out").glob("books_report_*.xlsx"))) == 1
    assert len(list((tmp_path / "logs").glob("run_*.log"))) == 1


def test_main_returns_1_when_no_books(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "scrape_books", lambda pages, details=False: [])
    code = run.main(["books", "--pages", "1"], output_dir=tmp_path / "out", log_dir=tmp_path / "logs")
    assert code == 1
    assert not (tmp_path / "out").exists()


def test_main_returns_1_when_file_locked(tmp_path, monkeypatch):
    def locked(*args, **kwargs):
        raise PermissionError("Cannot save report.xlsx - Close it and run again.")

    monkeypatch.setattr(run, "scrape_books", fake_books)
    monkeypatch.setattr(run, "build_report", locked)
    code = run.main(["books"], output_dir=tmp_path / "out", log_dir=tmp_path / "logs")
    assert code == 1


@pytest.mark.parametrize("value", ["0", "51", "abc"])
def test_pages_out_of_range_rejected(value, tmp_path):
    with pytest.raises(SystemExit) as exit_info:
        run.main(["books", "--pages", value], output_dir=tmp_path, log_dir=tmp_path)
    assert exit_info.value.code == 2


def test_job_is_required(tmp_path):
    with pytest.raises(SystemExit):
        run.main([], output_dir=tmp_path, log_dir=tmp_path)


import config


def fake_leads(searches, max_results=20):
    return [{"Name": "A", "Phone": "1", "Website": "https://a.test/"}]


def test_leads_success_without_emails(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(run, "scrape_gmaps", fake_leads)
    monkeypatch.setattr(run, "add_emails", lambda leads: calls.append(leads) or leads)
    code = run.main(["leads", "--search", "plumbers in london"], output_dir=tmp_path / "out",
                    log_dir=tmp_path / "logs")
    assert code == 0
    assert calls == []
    assert len(list((tmp_path / "out").glob("leads_report_*.xlsx"))) == 1


def test_leads_with_emails_flag(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(run, "scrape_gmaps", fake_leads)
    monkeypatch.setattr(run, "add_emails", lambda leads: calls.append(leads) or leads)
    run.main(["leads", "--search", "x", "--emails"], output_dir=tmp_path / "out",
             log_dir=tmp_path / "logs")
    assert len(calls) == 1


def test_leads_none_found(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "scrape_gmaps", lambda searches, max_results=20: [])
    assert run.main(["leads", "--search", "x"], output_dir=tmp_path, log_dir=tmp_path) == 1


def test_leads_requires_search(tmp_path):
    with pytest.raises(SystemExit) as exit_info:
        run.main(["leads"], output_dir=tmp_path, log_dir=tmp_path)
    assert exit_info.value.code == 2


def test_invoices_without_key_leaves_inbox_untouched(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    inbox = tmp_path / "invoices" / "inbox"
    inbox.mkdir(parents=True)
    (inbox / "a.pdf").write_bytes(b"%PDF")
    code = run.main(["invoices", "--folder", str(inbox)], output_dir=tmp_path / "out",
                    log_dir=tmp_path / "logs")
    assert code == 1
    assert [p.name for p in inbox.iterdir()] == ["a.pdf"]
    assert not (tmp_path / "invoices" / "failed").exists()


def test_invoices_exit_codes(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    results = iter([{"processed": 2, "failed": 1}, {"processed": 0, "failed": 0},
                    {"processed": 0, "failed": 2}])
    monkeypatch.setattr(run, "process_inbox", lambda *args, **kwargs: next(results))
    args = ["invoices", "--folder", str(tmp_path / "inbox")]
    assert run.main(args, output_dir=tmp_path, log_dir=tmp_path) == 0
    assert run.main(args, output_dir=tmp_path, log_dir=tmp_path) == 0
    assert run.main(args, output_dir=tmp_path, log_dir=tmp_path) == 1


def test_email_flag_sends_report(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(run, "scrape_books", fake_books)
    monkeypatch.setattr(run, "send_report", lambda path, subject: sent.append(path) or False)
    code = run.main(["books", "--pages", "1", "--email"], output_dir=tmp_path / "out",
                    log_dir=tmp_path / "logs")
    assert code == 0                               # a failed/skipped email does not fail the job
    assert len(sent) == 1
    assert sent[0].name.startswith("books_report_")


def test_no_email_without_flag(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(run, "scrape_books", fake_books)
    monkeypatch.setattr(run, "send_report", lambda path, subject: sent.append(path))
    run.main(["books", "--pages", "1"], output_dir=tmp_path / "out", log_dir=tmp_path / "logs")
    assert sent == []


def test_invoices_temporary_error_exit_1(tmp_path, monkeypatch):
    from extractors.invoices import TemporaryError

    def outage(*args, **kwargs):
        raise TemporaryError("Cannot reach Gemini")

    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(run, "process_inbox", outage)
    code = run.main(["invoices", "--folder", str(tmp_path / "inbox")], output_dir=tmp_path,
                    log_dir=tmp_path)
    assert code == 1
