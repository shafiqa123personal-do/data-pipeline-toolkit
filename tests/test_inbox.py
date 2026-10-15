import pytest

from automation import inbox
from automation.inbox import process_inbox
from automation.report import summarize_invoices
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
        (folder / name).write_bytes(b"%PDF-1.4")


def run(folders, extract=fake_extract):
    return process_inbox(folders["inbox"], folders["done"], folders["failed"], folders["master"],
                         extract=extract, delay=0)


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
