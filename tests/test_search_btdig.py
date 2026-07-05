"""Tests for :mod:`pytorrent_desktop.core.search.btdig` (v0.5.1a, EXPERIMENTAL/ALPHA).

**No live network** (docs/SCOPE.md's hard requirement): every test either
parses a saved HTML fixture directly, or stubs out ``requests.Session`` with
an in-test fake so ``BtdigProvider.search`` never actually opens a socket.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import requests

from pytorrent_desktop.core.errors import SearchError
from pytorrent_desktop.core.search.btdig import BtdigProvider, _parse_size_to_bytes

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


class _FakeResponse:
    def __init__(self, text: str, *, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class _FakeSession:
    """Stands in for ``requests.Session`` — records calls, never opens a socket."""

    def __init__(
        self, response: _FakeResponse | None = None, *, exc: Exception | None = None
    ) -> None:
        self._response = response
        self._exc = exc
        self.calls: list[dict] = []

    def get(self, url, *, params=None, timeout=None, headers=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout, "headers": headers})
        if self._exc is not None:
            raise self._exc
        return self._response


def _fixture(name: str) -> str:
    return (_FIXTURES_DIR / name).read_text(encoding="utf-8")


# -- size parsing helper ------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("3.5 GB", int(3.5 * 1024**3)),
        ("660 MB", 660 * 1024**2),
        ("128 KB", 128 * 1024),
        ("42 B", 42),
        ("1,234 MB", 1234 * 1024**2),
        (None, None),
        ("", None),
        ("unparseable-size-text", None),
    ],
)
def test_parse_size_to_bytes(text, expected) -> None:
    assert _parse_size_to_bytes(text) == expected


# -- happy path: parsing a saved results page ---------------------------------


def test_search_parses_saved_results_fixture() -> None:
    session = _FakeSession(_FakeResponse(_fixture("btdig_results.html")))
    provider = BtdigProvider(session=session)

    results = provider.search("ubuntu", timeout=5.0)

    assert len(results) == 3
    first = results[0]
    assert first.title == "Ubuntu 22.04 Desktop ISO"
    assert first.magnet.startswith("magnet:?xt=urn:btih:0123456789abcdef")
    assert first.size_bytes == int(3.5 * 1024**3)
    assert first.source == "btdig"
    # btdig has no live peer/seed counts in this row -> None, not 0.
    assert first.seeders is None
    assert first.leechers is None

    third = results[2]
    assert third.size_bytes == 128 * 1024
    assert third.seeders == 12
    assert third.leechers == 3


def test_search_sends_query_and_timeout_through_to_the_session() -> None:
    session = _FakeSession(_FakeResponse(_fixture("btdig_no_results.html")))
    provider = BtdigProvider(base_url="https://btdig.example", session=session)

    provider.search("my query", timeout=7.5)

    assert len(session.calls) == 1
    call = session.calls[0]
    assert call["url"] == "https://btdig.example/search"
    assert call["params"] == {"q": "my query"}
    assert call["timeout"] == 7.5


def test_search_with_empty_query_returns_empty_without_a_network_call() -> None:
    session = _FakeSession(_FakeResponse(_fixture("btdig_results.html")))
    provider = BtdigProvider(session=session)

    assert provider.search("   ") == []
    assert session.calls == []  # never touched the (fake) network


def test_search_with_no_results_fixture_returns_empty_list() -> None:
    session = _FakeSession(_FakeResponse(_fixture("btdig_no_results.html")))
    provider = BtdigProvider(session=session)

    assert provider.search("nonexistent-query-xyz") == []


def test_search_skips_malformed_rows_without_crashing() -> None:
    session = _FakeSession(_FakeResponse(_fixture("btdig_malformed_row.html")))
    provider = BtdigProvider(session=session)

    results = provider.search("whatever")

    # Only the third row has both a real .torrent_name a[href^=magnet:] link
    # and is otherwise well-formed; the first (no link) and second (non-magnet
    # href) rows must be skipped silently, not raise.
    assert len(results) == 1
    assert results[0].title == "Still Works"
    assert results[0].size_bytes is None  # unparseable size text -> None, not a crash


# -- error handling: network + HTTP failures become SearchError --------------


def test_search_wraps_connection_error_in_search_error() -> None:
    session = _FakeSession(exc=requests.ConnectionError("connection refused"))
    provider = BtdigProvider(session=session)

    with pytest.raises(SearchError):
        provider.search("anything")


def test_search_wraps_timeout_in_search_error() -> None:
    session = _FakeSession(exc=requests.Timeout("timed out"))
    provider = BtdigProvider(session=session)

    with pytest.raises(SearchError):
        provider.search("anything")


def test_search_wraps_http_error_status_in_search_error() -> None:
    session = _FakeSession(_FakeResponse("<html></html>", status_code=503))
    provider = BtdigProvider(session=session)

    with pytest.raises(SearchError):
        provider.search("anything")


def test_search_wraps_a_parser_bug_in_search_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Even a totally broken parser must surface as SearchError, never crash."""
    session = _FakeSession(_FakeResponse(_fixture("btdig_results.html")))
    provider = BtdigProvider(session=session)

    def _boom(self, html: str) -> list:
        raise RuntimeError("simulated parser bug")

    monkeypatch.setattr(BtdigProvider, "_parse_results", _boom)

    with pytest.raises(SearchError):
        provider.search("anything")


def test_base_url_trailing_slash_is_normalized() -> None:
    session = _FakeSession(_FakeResponse(_fixture("btdig_no_results.html")))
    provider = BtdigProvider(base_url="https://btdig.example/", session=session)

    provider.search("q")

    assert session.calls[0]["url"] == "https://btdig.example/search"


def test_search_parses_btdig_real_structure_magnet_in_separate_anchor():
    """Regression (live-verified 2026-07-05): btdig keeps the magnet in its own
    <a href="magnet:..."> anchor, separate from the (non-magnet) title link. The
    parser must read the magnet from the magnet anchor, not the title link's
    href — the original fabricated fixture assumed the latter and live search
    returned 0 results as a result.
    """
    html = (_FIXTURES_DIR / "btdig_results_real.html").read_text(encoding="utf-8")
    provider = BtdigProvider(session=_FakeSession(_FakeResponse(html)))
    results = provider.search("ubuntu")
    assert len(results) == 2
    assert results[0].title == "Ubuntu 24.04 Desktop amd64"
    assert results[0].magnet.startswith("magnet:?xt=urn:btih:aaaaaaaaaaaa")
    assert results[0].size_bytes == _parse_size_to_bytes("5.7 GB")
    assert results[1].magnet.startswith("magnet:?xt=urn:btih:bbbbbbbbbbbb")
