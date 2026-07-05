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
    assert call["params"] == {"q": "my query", "p": 0}
    assert call["timeout"] == 7.5


# -- paging: btdig's ``p`` (0-based) query param, live-verified 2026-07-05 ----


def test_search_defaults_to_page_0_when_page_is_not_passed() -> None:
    session = _FakeSession(_FakeResponse(_fixture("btdig_results.html")))
    provider = BtdigProvider(session=session)

    provider.search("ubuntu")

    assert session.calls[0]["params"] == {"q": "ubuntu", "p": 0}


def test_search_sends_the_page_argument_as_the_p_param() -> None:
    session = _FakeSession(_FakeResponse(_fixture("btdig_results.html")))
    provider = BtdigProvider(session=session)

    provider.search("ubuntu", page=1)

    assert session.calls[0]["params"] == {"q": "ubuntu", "p": 1}


def test_search_page_2_uses_p_equals_2() -> None:
    session = _FakeSession(_FakeResponse(_fixture("btdig_results.html")))
    provider = BtdigProvider(session=session)

    provider.search("ubuntu", page=2)

    assert session.calls[0]["params"] == {"q": "ubuntu", "p": 2}


def test_search_different_pages_can_return_different_fixtures() -> None:
    """Simulates btdig returning a different set of rows per page: the
    provider must simply parse+return whatever the (fake) page 1 response
    contains, with no special-casing of the page number itself."""
    session = _FakeSession(_FakeResponse(_fixture("btdig_results_real.html")))
    provider = BtdigProvider(session=session)

    page1_results = provider.search("ubuntu", page=1)

    assert session.calls[0]["params"]["p"] == 1
    assert len(page1_results) == 2
    assert page1_results[0].title == "Ubuntu 24.04 Desktop amd64"


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


# -- extended fields for the search-result list/detail UX (2026-07 UX pass) ---


def test_search_parses_title_split_by_btdigs_bold_highlight_span():
    """Regression: btdig wraps the matched query term in <b> inside
    .torrent_name (live-verified), e.g. "<a><b>Ubuntu</b> 24.04 ...</a>". A
    naive get_text(strip=True) drops the space between the bolded fragment
    and the rest of the title, producing "Ubuntu24.04..." — the title must
    come out with the space intact.
    """
    html = (_FIXTURES_DIR / "btdig_results_real.html").read_text(encoding="utf-8")
    provider = BtdigProvider(session=_FakeSession(_FakeResponse(html)))
    results = provider.search("ubuntu")
    assert results[0].title == "Ubuntu 24.04 Desktop amd64"


def test_search_parses_num_files_from_torrent_files_span():
    html = (_FIXTURES_DIR / "btdig_results_real.html").read_text(encoding="utf-8")
    provider = BtdigProvider(session=_FakeSession(_FakeResponse(html)))
    results = provider.search("ubuntu")
    assert results[0].num_files == 396


def test_search_parses_age_from_torrent_age_span():
    html = (_FIXTURES_DIR / "btdig_results_real.html").read_text(encoding="utf-8")
    provider = BtdigProvider(session=_FakeSession(_FakeResponse(html)))
    results = provider.search("ubuntu")
    assert results[0].age == "found 2 months ago"


def test_search_parses_info_hash_from_the_magnet_xt_parameter():
    html = (_FIXTURES_DIR / "btdig_results_real.html").read_text(encoding="utf-8")
    provider = BtdigProvider(session=_FakeSession(_FakeResponse(html)))
    results = provider.search("ubuntu")
    assert results[0].info_hash == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert results[1].info_hash == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def test_search_parses_excerpt_into_a_flat_list_of_preview_lines():
    html = (_FIXTURES_DIR / "btdig_results_real.html").read_text(encoding="utf-8")
    provider = BtdigProvider(session=_FakeSession(_FakeResponse(html)))
    results = provider.search("ubuntu")
    files = results[0].files
    assert isinstance(files, list)
    assert files[0] == "Ubuntu 24.04 Desktop amd64"  # folder row, highlight preserved
    assert "ubuntu -24.04-desktop-amd64.iso 5.7 GB" in files
    assert "2 hidden files 1.2 MB" in files


def test_search_missing_optional_fields_are_gracefully_none():
    """Row 2 in the real-structure fixture has no .torrent_files/.torrent_age/
    .torrent_excerpt at all — the provider must report None, not crash or
    fabricate a value, for every field it doesn't have (§9's "graceful")."""
    html = (_FIXTURES_DIR / "btdig_results_real.html").read_text(encoding="utf-8")
    provider = BtdigProvider(session=_FakeSession(_FakeResponse(html)))
    results = provider.search("ubuntu")
    second = results[1]
    assert second.num_files is None
    assert second.age is None
    assert second.files is None
    assert second.info_hash == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def test_search_extended_fields_are_none_on_the_older_plain_fixture():
    """The pre-existing btdig_results.html fixture has no .torrent_age/
    .torrent_excerpt at all — must not error, just report None for those."""
    session = _FakeSession(_FakeResponse(_fixture("btdig_results.html")))
    provider = BtdigProvider(session=session)
    results = provider.search("ubuntu")
    assert results[0].age is None
    assert results[0].files is None
    assert results[0].info_hash == "0123456789abcdef0123456789abcdef01234567"
