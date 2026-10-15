import requests

from core import http


class FakeResponse:
    def __init__(self, status=200, text="<html>ok</html>"):
        self.status_code = status
        self.text = text
        self.encoding = None

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code}", response=self)


def fake_get(responses, calls):
    """Return a fake requests.get that hands out responses (or raises errors) in order."""
    def _get(url, headers, timeout):
        calls.append(url)
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
    return _get


def test_get_page_success(monkeypatch):
    calls = []
    monkeypatch.setattr(http.requests, "get", fake_get([FakeResponse()], calls))
    assert http.get_page("https://x.test", delay=0) == "<html>ok</html>"
    assert len(calls) == 1


def test_get_page_retries_then_succeeds(monkeypatch):
    calls = []
    errors = [requests.exceptions.ConnectionError("down"), requests.exceptions.Timeout("slow")]
    monkeypatch.setattr(http.requests, "get", fake_get(errors + [FakeResponse()], calls))
    assert http.get_page("https://x.test", delay=0) == "<html>ok</html>"
    assert len(calls) == 3


def test_get_page_gives_up(monkeypatch):
    calls = []
    errors = [requests.exceptions.ConnectionError("down")] * 3
    monkeypatch.setattr(http.requests, "get", fake_get(errors, calls))
    assert http.get_page("https://x.test", delay=0) is None
    assert len(calls) == 3


def test_get_page_404_not_retried(monkeypatch):
    calls = []
    monkeypatch.setattr(http.requests, "get", fake_get([FakeResponse(status=404)], calls))
    assert http.get_page("https://x.test", delay=0) is None
    assert len(calls) == 1


def test_get_page_500_is_retried(monkeypatch):
    calls = []
    responses = [FakeResponse(status=500), FakeResponse()]
    monkeypatch.setattr(http.requests, "get", fake_get(responses, calls))
    assert http.get_page("https://x.test", delay=0) == "<html>ok</html>"
    assert len(calls) == 2
