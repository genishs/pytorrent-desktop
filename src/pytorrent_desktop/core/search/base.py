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


@dataclass(frozen=True)
class SearchResult:
    """One row returned by a :class:`SearchProvider` (docs/ARCHITECTURE.md §9).

    ``size_bytes``/``seeders``/``leechers`` are ``None`` when a provider
    can't report them — e.g. btdig is a DHT-metadata search engine and does
    not track live peer counts, so it always reports ``seeders``/``leechers``
    as ``None``. The UI renders ``None`` as ``"-"`` rather than a misleading
    ``0``.
    """

    title: str
    size_bytes: int | None
    seeders: int | None
    leechers: int | None
    magnet: str
    source: str


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
    def search(self, query: str, *, timeout: float = 10.0) -> list[SearchResult]:
        """Query for ``query`` and return matching results (possibly empty).

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
