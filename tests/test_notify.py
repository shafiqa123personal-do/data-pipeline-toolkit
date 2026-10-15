import smtplib

import pytest

import config
from automation.notify import send_report


class FakeSMTP:
    def __init__(self, host, port, timeout):
        self.host, self.port = host, port
        self.sent = []
        FakeSMTP.last = self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        self.login_args = (user, password)

    def send_message(self, message):
        self.sent.append(message)


class FailingSMTP(FakeSMTP):
    def login(self, user, password):
        raise smtplib.SMTPAuthenticationError(535, b"bad password")


@pytest.fixture
def report(tmp_path):
    path = tmp_path / "books_report.xlsx"
    path.write_bytes(b"xlsx bytes")
    return path


@pytest.fixture
def gmail(monkeypatch):
    monkeypatch.setattr(config, "GMAIL_ADDRESS", "me@gmail.com")
    monkeypatch.setattr(config, "GMAIL_APP_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.setattr(config, "REPORT_TO", "boss@example.org")


def test_skipped_without_credentials(report, monkeypatch):
    monkeypatch.setattr(config, "GMAIL_ADDRESS", "")
    monkeypatch.setattr(config, "GMAIL_APP_PASSWORD", "")

    def must_not_connect(*args, **kwargs):
        raise AssertionError("should not connect")

    assert send_report(report, "Books report", smtp_class=must_not_connect) is False


def test_sends_report_with_attachment(report, gmail):
    assert send_report(report, "Books report", smtp_class=FakeSMTP) is True
    smtp = FakeSMTP.last
    assert (smtp.host, smtp.port) == ("smtp.gmail.com", 465)
    assert smtp.login_args == ("me@gmail.com", "abcd efgh ijkl mnop")
    message = smtp.sent[0]
    assert message["To"] == "boss@example.org"
    assert message["Subject"] == "Books report"
    assert [a.get_filename() for a in message.iter_attachments()] == ["books_report.xlsx"]


def test_login_failure_returns_false(report, gmail):
    assert send_report(report, "Books report", smtp_class=FailingSMTP) is False
