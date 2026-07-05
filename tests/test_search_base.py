"""Tests for :mod:`pytorrent_desktop.core.search.base` (v0.5.1a, EXPERIMENTAL/ALPHA).

Headless, no network, no Qt — just the dataclass + registry contract
(docs/ARCHITECTURE.md §9).
"""

from __future__ import annotations

import pytest

from pytorrent_desktop.core.search.base import (
    SearchProvider,
    SearchResult,
    get_provider,
    list_providers,
    register_provider,
    unregister_all,
)


class FakeProvider(SearchProvider):
    name = "fake"

    def __init__(self, results: list[SearchResult] | None = None) -> None:
        self._results = results or []

    def search(self, query: str, *, page: int = 0, timeout: float = 10.0) -> list[SearchResult]:
        return list(self._results)


@pytest.fixture(autouse=True)
def _clean_registry():
    unregister_all()
    yield
    unregister_all()


def test_search_result_is_frozen_and_carries_all_fields() -> None:
    result = SearchResult(
        title="example.iso",
        size_bytes=1024,
        seeders=5,
        leechers=1,
        magnet="magnet:?xt=urn:btih:" + "a" * 40,
        source="fake",
    )
    assert result.title == "example.iso"
    with pytest.raises(AttributeError):
        result.title = "changed"  # type: ignore[misc]


def test_search_result_allows_none_for_unknown_optional_fields() -> None:
    result = SearchResult(
        title="example.iso",
        size_bytes=None,
        seeders=None,
        leechers=None,
        magnet="magnet:?xt=urn:btih:" + "a" * 40,
        source="fake",
    )
    assert result.size_bytes is None
    assert result.seeders is None
    assert result.leechers is None


def test_search_result_extended_fields_default_to_none() -> None:
    """num_files/age/files/info_hash are trailing optional fields (added for
    the result-list/detail UX) so any existing 6-positional-arg construction
    of this dataclass keeps working unchanged."""
    result = SearchResult(
        "example.iso", None, None, None, "magnet:?xt=urn:btih:" + "a" * 40, "fake"
    )
    assert result.num_files is None
    assert result.age is None
    assert result.files is None
    assert result.info_hash is None


def test_search_result_extended_fields_carry_the_given_values() -> None:
    result = SearchResult(
        title="example.iso",
        size_bytes=1024,
        seeders=None,
        leechers=None,
        magnet="magnet:?xt=urn:btih:" + "a" * 40,
        source="fake",
        num_files=12,
        age="found 2 months ago",
        files=["a.txt", "b.txt"],
        info_hash="a" * 40,
    )
    assert result.num_files == 12
    assert result.age == "found 2 months ago"
    assert result.files == ["a.txt", "b.txt"]
    assert result.info_hash == "a" * 40


def test_provider_is_abstract_without_search_implemented() -> None:
    with pytest.raises(TypeError):

        class IncompleteProvider(SearchProvider):
            name = "incomplete"

        IncompleteProvider()  # type: ignore[abstract]


def test_register_and_get_provider_round_trips() -> None:
    provider = FakeProvider()
    register_provider(provider)
    assert get_provider("fake") is provider
    assert get_provider("does-not-exist") is None


def test_list_providers_returns_all_registered() -> None:
    register_provider(FakeProvider())
    assert [p.name for p in list_providers()] == ["fake"]


def test_registry_starts_empty_and_is_not_populated_by_import() -> None:
    # Importing core.search.base (done at module load above) must not have
    # auto-registered anything — no network/plugin auto-discovery (§9).
    assert list_providers() == []


def test_re_registering_same_name_overwrites() -> None:
    magnet = "magnet:?xt=urn:btih:" + "b" * 40
    first = FakeProvider([])
    second = FakeProvider([SearchResult("x", None, None, None, magnet, "fake")])
    register_provider(first)
    register_provider(second)
    assert get_provider("fake") is second
