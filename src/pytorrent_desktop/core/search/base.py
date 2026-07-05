"""Search-provider contract + explicit registry (v0.5.1a, EXPERIMENTAL/ALPHA).

Sketched in docs/ARCHITECTURE.md §9, scoped in docs/SCOPE.md: pluggable,
off-by-default, user-activated search providers. This module only defines
the interface — no network code, no Qt import (``core/`` must stay
headless-testable, docs/ARCHITECTURE.md §1).

Providers are discovered through the registry below, never by
auto-importing anything from the internet or a plugin directory (§9's
"자동으로 import되지 않는다") — importing this module has zero side effects
and touches no network. The caller (``ui/main_window.py``'s search-provider
factory, currently the only caller) explicitly constructs and registers
whichever provider(s) it wants.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

# Nominal results-per-page every provider currently returns (btdig's page
# size, live-verified 2026-07-05). Callers use this to decide whether a
# "more results" affordance should be offered: a page shorter than this is
# taken to mean "no more pages" (see ui/dialogs.py's SearchDialog).
PAGE_SIZE = 10


@dataclass(frozen=True)
class SearchResult:
    """One row returned by a :class:`SearchProvider` (docs/ARCHITECTURE.md §9).

    ``size_bytes``/``seeders``/``leechers`` are ``None`` when a provider
    can't report them — e.g. btdig is a DHT-metadata search engine and does
    not track live peer counts, so it always reports ``seeders``/``leechers``
    as ``None``. The UI renders ``None`` as ``"-"`` rather than a misleading
    ``0``.

    ``num_files``/``age``/``files``/``info_hash`` were added for the search
    result list/detail UX (result-list liveliness signal + a double-click
    detail view): all four are optional trailing fields, defaulted to
    ``None`` so any existing positional-argument construction of this
    dataclass keeps working unchanged.

    - ``num_files``: file count reported by the provider (btdig's
      ``.torrent_files``), or ``None`` if not reported.
    - ``age``: how long ago the provider last saw this torrent — btdig's
      ``.torrent_age`` (kept as the provider's original text, e.g. ``"found
      2 months ago"``), a rough proxy for "is a seed still likely alive".
    - ``files``: a preview of the file list inside the torrent (btdig's
      ``.torrent_excerpt``), as a list of preview lines, a single blob of
      text, or ``None`` if the provider didn't return one.
    - ``info_hash``: the torrent's info-hash, parsed from ``magnet``'s
      ``xt=urn:bt(ih|mh):...`` parameter when possible.
    """

    title: str
    size_bytes: int | None
    seeders: int | None
    leechers: int | None
    magnet: str
    source: str
    num_files: int | None = None
    age: str | None = None
    files: list[str] | str | None = None
    info_hash: str | None = None


class SearchProvider(ABC):
    """Contract every search provider implements.

    ``name`` is the stable id shown in the result table's "출처" (source)
    column and used as the registry key. Implementations must never let
    anything but :class:`~pytorrent_desktop.core.errors.SearchError` escape
    :meth:`search` — network/parsing failures are the caller's problem to
    display gracefully, never to crash on (docs/SCOPE.md: "graceful, no
    crash").
    """

    name: str

    @abstractmethod
    def search(
        self, query: str, *, page: int = 0, timeout: float = 10.0
    ) -> list[SearchResult]:
        """Query for ``query`` and return matching results (possibly empty).

        ``page`` is 0-based (page 0 is the first/default page); passing the
        same ``query`` with an incrementing ``page`` is how a caller fetches
        "more results" without ever bulk-fetching every page up front
        (docs/SCOPE.md: paging is explicit and caller-driven, never a
        provider-side crawl). Existing callers that don't pass ``page`` keep
        getting page 0, unchanged.

        Must raise :class:`~pytorrent_desktop.core.errors.SearchError`
        (never a raw network/parsing exception) on failure, and must never
        perform any DHT crawling/indexing of its own — HTTP query + response
        parsing only (docs/SCOPE.md's explicit non-goal: no DHT crawler is
        ever built here).
        """


# -- explicit registry (docs/ARCHITECTURE.md §9's "통합 계약") ------------------

_registry: dict[str, SearchProvider] = {}


def register_provider(provider: SearchProvider) -> None:
    """Register ``provider`` under its ``name`` (re-registering overwrites)."""
    _registry[provider.name] = provider


def get_provider(name: str) -> SearchProvider | None:
    """Look up a previously registered provider by name, or ``None``."""
    return _registry.get(name)


def list_providers() -> list[SearchProvider]:
    """All currently registered providers, in registration order."""
    return list(_registry.values())


def unregister_all() -> None:
    """Test helper: clear the registry so isolated tests don't leak state."""
    _registry.clear()
