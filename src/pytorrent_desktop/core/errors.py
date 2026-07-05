"""Typed exception hierarchy for :mod:`pytorrent_desktop.core.engine`.

Every error the engine raises derives from :class:`EngineError`, so ``ui/`` can
``except EngineError`` for a generic dialog and special-case a few concrete
types. No raw exception from libtorrent (or the filesystem) is ever allowed to
cross the facade boundary — see docs/ARCHITECTURE.md §8.
"""

from __future__ import annotations


class EngineError(Exception):
    """Base class for all errors raised by :class:`TorrentEngine`."""


class EngineInitError(EngineError):
    """The libtorrent session could not be created/bound."""


class InvalidMagnetError(EngineError):
    """The given magnet URI could not be parsed."""


class InvalidTorrentError(EngineError):
    """The given ``.torrent`` file does not exist or could not be parsed.

    This is the name used in docs/ARCHITECTURE.md's method-contract table
    (§3.2, the ``Raises`` column for ``add_torrent_file``).
    """


# Alias: the product brief for this milestone names this case
# ``TorrentFileError``. Kept as an alias (not a separate subclass) so both
# ``except InvalidTorrentError`` and ``except TorrentFileError`` catch the
# same error — no consumer needs to know which name was used to raise it.
TorrentFileError = InvalidTorrentError


class DuplicateTorrentError(EngineError):
    """A torrent with the same info-hash is already known to the engine."""

    def __init__(self, info_hash: str) -> None:
        super().__init__(f"Torrent already added: {info_hash}")
        self.info_hash = info_hash


class SavePathError(EngineError):
    """The requested save path is missing, not a directory, or not writable."""


class UnknownTorrentError(EngineError):
    """A control call referenced an info-hash the engine does not know about."""

    def __init__(self, info_hash: str) -> None:
        super().__init__(f"Unknown torrent: {info_hash}")
        self.info_hash = info_hash


class ProxyConfigError(EngineError):
    """Proxy configuration (host/port/etc.) is invalid.

    Raised by ``TorrentEngine.configure_privacy`` (docs/ARCHITECTURE.md §11,
    §8's error-handling table) when ``ProxyConfig.host`` is empty or
    ``ProxyConfig.port`` is out of range.
    """


class SearchError(EngineError):
    """EXPERIMENTAL/ALPHA (v0.5.1a, docs/ARCHITECTURE.md §9, docs/SCOPE.md).

    Raised by a ``core/search/*`` :class:`~pytorrent_desktop.core.search.base.SearchProvider`
    when a query fails — network error (timeout, connection refused, non-2xx
    response) or a result page that could not be parsed. Every failure mode a
    provider can hit must be wrapped in this single type rather than letting a
    raw ``requests`` or ``bs4`` exception escape, so ``ui/`` (the experimental
    search dialog) can catch one type and show a graceful inline message
    instead of crashing.

    Not raised by :class:`TorrentEngine` itself — search providers are a
    separate, optional, user-activated subsystem (§9) — but subclassing
    :class:`EngineError` lets any existing ``except EngineError`` call site
    keep working unchanged if a search failure ever needs to surface through
    the same generic-dialog path.
    """
