import pytest

from automation import inbox
from automation.inbox import process_inbox
from automation.report import summarize_invoices
from extractors.invoices import TemporaryError
from core.excel import read_sheet


def fake_extract(path):
    if "bad" in path.name:
        raise ValueError("Gemini could not read it")
    return ({"File": path.name, "Supplier": "S", "Currency": "GBP", "Total": 10.0, "Status": "OK"},
            [{"File": path.name, "Description": "x", "Amount": 10.0}])


def no_items_extract(path):
    return ({"File": path.name, "Currency": "USD", "Total": 5.0, "Status": "OK"}, [])


@pytest.fixture
def folders(tmp_path):
    paths = {name: tmp_path / name for name in ("inbox", "done", "failed")}
    paths["inbox"].mkdir()
    paths["master"] = tmp_path / "out" / "invoices_master.xlsx"
    return paths


def add_files(folder, *names):
    for name in names:
        (folder / name).write_bytes(b"%PDF-1.4 " + name.encode())    # different content per file


def run(folders, extract=fake_extract):
    return process_inbox(folders["inbox"], folders["done"], folders["failed"], folders["master"],
                         extract=extract, delay=0, min_age=0)


def test_processes_files_and_moves_them_to_done(folders):
    add_files(folders["inbox"], "a.pdf", "b.pdf")
    assert run(folders) == {"processed": 2, "failed": 0}
    assert [r["File"] for r in read_sheet(folders["master"], "Invoices")] == ["a.pdf", "b.pdf"]
    assert len(read_sheet(folders["master"], "Line Items")) == 2
    assert sorted(p.name for p in folders["done"].iterdir()) == ["a.pdf", "b.pdf"]
    assert list(folders["inbox"].iterdir()) == []


def test_second_run_appends_to_master(folders):
    add_files(folders["inbox"], "a.pdf")
    run(folders)
    add_files(folders["inbox"], "b.pdf")
    run(folders)
    assert [r["File"] for r in read_sheet(folders["master"], "Invoices")] == ["a.pdf", "b.pdf"]


def test_failed_file_goes_to_failed_folder(folders):
    add_files(folders["inbox"], "a.pdf", "bad.pdf")
    assert run(folders) == {"processed": 1, "failed": 1}
    assert [p.name for p in folders["failed"].iterdir()] == ["bad.pdf"]
    assert [p.name for p in folders["done"].iterdir()] == ["a.pdf"]


def test_empty_inbox_does_nothing(folders):
    assert run(folders) == {"processed": 0, "failed": 0}
    assert not folders["master"].exists()


def test_locked_master_leaves_files_in_inbox(folders, monkeypatch):
    def locked(sheets, path):
        raise PermissionError("Cannot save invoices_master.xlsx - Close it and run again.")

    monkeypatch.setattr(inbox, "save_excel", locked)
    add_files(folders["inbox"], "a.pdf", "bad.pdf")
    with pytest.raises(PermissionError):
        run(folders)
    assert sorted(p.name for p in folders["inbox"].iterdir()) == ["a.pdf", "bad.pdf"]


def test_same_name_in_done_is_not_overwritten(folders):
    folders["done"].mkdir()
    (folders["done"] / "a.pdf").write_bytes(b"old")
    add_files(folders["inbox"], "a.pdf")
    run(folders)
    assert len(list(folders["done"].iterdir())) == 2
    assert (folders["done"] / "a.pdf").read_bytes() == b"old"


def test_master_without_line_items_can_be_appended(folders):
    add_files(folders["inbox"], "a.pdf")
    run(folders, extract=no_items_extract)
    add_files(folders["inbox"], "b.pdf")
    run(folders, extract=no_items_extract)
    assert len(read_sheet(folders["master"], "Invoices")) == 2
    assert all("Info" not in row for row in read_sheet(folders["master"], "Invoices"))


def test_summarize_invoices():
    summary = {row["Metric"]: row["Value"] for row in summarize_invoices([
        {"Currency": "GBP", "Total": 10.0, "Status": "OK"},
        {"Currency": "GBP", "Total": 5.5, "Status": "CHECK: no invoice number"},
        {"Currency": "USD", "Total": 7.0, "Status": "OK"},
    ])}
    assert summary["Invoices"] == 3
    assert summary["Need checking"] == 1
    assert summary["Total GBP"] == 15.5
    assert summary["Total USD"] == 7.0


def test_temporary_error_stops_and_keeps_rest_in_inbox(folders):
    def extract(path):
        if path.name == "b.pdf":
            raise TemporaryError("Gemini unavailable (429)")
        return fake_extract(path)

    add_files(folders["inbox"], "a.pdf", "b.pdf", "c.pdf")
    with pytest.raises(TemporaryError):
        run(folders, extract=extract)
    assert [r["File"] for r in read_sheet(folders["master"], "Invoices")] == ["a.pdf"]
    assert sorted(p.name for p in folders["inbox"].iterdir()) == ["b.pdf", "c.pdf"]
    assert not folders["failed"].exists() or list(folders["failed"].iterdir()) == []


def test_new_files_wait_until_fully_copied(folders):
    add_files(folders["inbox"], "a.pdf")
    result = process_inbox(folders["inbox"], folders["done"], folders["failed"], folders["master"],
                           extract=fake_extract, delay=0, min_age=60)
    assert result == {"processed": 0, "failed": 0}
    assert [p.name for p in folders["inbox"].iterdir()] == ["a.pdf"]


def test_ignores_system_and_partial_files(folders):
    add_files(folders["inbox"], "a.pdf", "desktop.ini", "Thumbs.db", "scan.pdf.crdownload")
    assert run(folders) == {"processed": 1, "failed": 0}
    assert sorted(p.name for p in folders["inbox"].iterdir()) == \
        ["Thumbs.db", "desktop.ini", "scan.pdf.crdownload"]


def test_same_invoice_is_not_extracted_twice(folders):
    calls = []

    def counting_extract(path):
        calls.append(path.name)
        return fake_extract(path)

    (folders["inbox"] / "a.pdf").write_bytes(b"same invoice")
    (folders["inbox"] / "a copy.pdf").write_bytes(b"same invoice")
    run(folders, extract=counting_extract)
    (folders["inbox"] / "a again.pdf").write_bytes(b"same invoice")
    run(folders, extract=counting_extract)
    assert calls == ["a copy.pdf"]
    assert len(read_sheet(folders["master"], "Invoices")) == 1
    assert list(folders["inbox"].iterdir()) == []


def test_move_failure_after_save_does_not_duplicate(folders, monkeypatch):
    real_move = inbox.shutil.move
    attempts = []

    def flaky_move(src, dst):
        attempts.append(src)
        if len(attempts) == 1:
            raise PermissionError("file is open in a PDF viewer")
        return real_move(src, dst)

    monkeypatch.setattr(inbox.shutil, "move", flaky_move)
    add_files(folders["inbox"], "a.pdf")
    run(folders)                                   # saved to master, but the move fails
    assert [p.name for p in folders["inbox"].iterdir()] == ["a.pdf"]
    run(folders)                                   # next run: recognised, just moved
    assert len(read_sheet(folders["master"], "Invoices")) == 1
    assert [p.name for p in folders["done"].iterdir()] == ["a.pdf"]


def test_locked_master_is_detected_before_extracting(folders, monkeypatch):
    calls = []

    def locked(path):
        raise PermissionError("Cannot update invoices_master.xlsx - Close it and run again.")

    monkeypatch.setattr(inbox, "_check_writable", locked)
    add_files(folders["inbox"], "a.pdf")
    with pytest.raises(PermissionError):
        run(folders, extract=lambda path: calls.append(path) or fake_extract(path))
    assert calls == []


def test_master_summary_warns_it_is_rebuilt(folders):
    add_files(folders["inbox"], "a.pdf")
    run(folders)
    notes = [r["Value"] for r in read_sheet(folders["master"], "Summary") if r["Metric"] == "Note"]
    assert notes and "copy it before editing" in notes[0]
