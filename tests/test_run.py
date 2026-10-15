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
