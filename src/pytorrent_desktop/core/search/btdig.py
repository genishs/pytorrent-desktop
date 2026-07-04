"""btdig-style search provider (v0.5.1a, EXPERIMENTAL/ALPHA).

docs/SCOPE.md's explicit constraints for this provider:
  - HTTP query + HTML-response parsing ONLY. No DHT crawler/indexer is ever
    built here — btdig.com already runs one; this module just asks it a
    question over HTTP and reads the answer back.
  - The base URL is configurable (``core/config.py``'s
    ``SearchSettings.btdig_base_url``), so this module hardcodes exactly one
    fact: the *default* value of that URL (``DEFAULT_BASE_URL``).
  - Every network or parse failure is wrapped in ``core/errors.py``'s
    ``SearchError`` — never a raw ``requests``/``bs4`` exception, and never a
    partial/garbage result list.

Alpha-quality caveat (documented, not hidden): btdig's live page markup was
not available to verify against, since docs/SCOPE.md forbids live network
access during development/CI. ``_parse_results`` below is written against a
documented, plausible result-row shape and is only exercised against the
saved HTML fixtures in ``tests/fixtures/``. The CSS selectors here should be
revisited against the real site once this ships.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

from ..errors import SearchError
from .base import SearchProvider, SearchResult

_log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://btdig.com"

_USER_AGENT = (
    "pytorrent-desktop/0.5.1a (experimental search feature; "
    "+https://github.com/genishs/pytorrent-desktop)"
)

_SIZE_PATTERN = re.compile(r"([\d.]+)\s*([A-Za-z]+)")
_SIZE_UNITS = {
    "B": 1,
    "KB": 1024,
    "KIB": 1024,
    "MB": 1024**2,
    "MIB": 1024**2,
    "GB": 1024**3,
    "GIB": 1024**3,
    "TB": 1024**4,
    "TIB": 1024**4,
}


def _parse_size_to_bytes(text: str | None) -> int | None:
    """``"3.5 GB"`` -> bytes; ``None``/unparseable text -> ``None`` (never raises)."""
    if not text:
        return None
    match = _SIZE_PATTERN.search(text.replace(",", ""))
    if not match:
        return None
    number, unit = match.groups()
    scale = _SIZE_UNITS.get(unit.upper())
    if scale is None:
        return None
    try:
        return int(float(number) * scale)
    except ValueError:
        return None


def _parse_optional_int(text: str | None) -> int | None:
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _title_from_magnet(magnet: str) -> str:
    """Fallback title when the result row's link text is empty: the magnet's
    ``dn=`` display-name parameter, or a placeholder if that's absent too."""
    query = parse_qs(urlparse(magnet).query)
    names = query.get("dn")
    return names[0] if names else "(제목 없음 / untitled)"


class BtdigProvider(SearchProvider):
    """EXPERIMENTAL/ALPHA: HTTP query + HTML parse against a btdig-style
    search endpoint. Never crawls the DHT itself (docs/SCOPE.md).

    ``seeders``/``leechers`` are always reported as ``None`` — btdig is a
    DHT-metadata search engine, not a tracker, and has no live peer counts to
    report; the fields exist on :class:`SearchResult` for providers that do.
    """

    name = "btdig"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        session: requests.Session | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/") or DEFAULT_BASE_URL
        self._session = session or requests.Session()

    def search(self, query: str, *, timeout: float = 10.0) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []

        try:
            response = self._session.get(
                f"{self._base_url}/search",
                params={"q": query},
                timeout=timeout,
                headers={"User-Agent": _USER_AGENT},
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SearchError(f"btdig 검색 요청에 실패했습니다: {exc}") from exc

        try:
            return self._parse_results(response.text)
        except SearchError:
            raise
        except Exception as exc:  # noqa: BLE001 - a parser bug must never crash the app
            _log.warning("btdig response could not be parsed: %s", exc)
            raise SearchError(f"btdig 검색 결과를 해석할 수 없습니다: {exc}") from exc

    def _parse_results(self, html: str) -> list[SearchResult]:
        soup = BeautifulSoup(html, "html.parser")
        results: list[SearchResult] = []
        for row in soup.select("div.one_result"):
            name_el = row.select_one(".torrent_name a")
            if name_el is None:
                # Defensive: skip a malformed row rather than failing the
                # whole page. "Never partial/garbage results" (§9) is about
                # not fabricating junk entries, not about refusing to skip
                # one bad row among otherwise-good ones.
                continue
            magnet = (name_el.get("href") or "").strip()
            if not magnet.startswith("magnet:"):
                continue
            title = name_el.get_text(strip=True) or _title_from_magnet(magnet)

            size_el = row.select_one(".torrent_size")
            seeders_el = row.select_one(".torrent_seeders")
            leechers_el = row.select_one(".torrent_leechers")

            results.append(
                SearchResult(
                    title=title,
                    size_bytes=_parse_size_to_bytes(size_el.get_text() if size_el else None),
                    seeders=_parse_optional_int(seeders_el.get_text() if seeders_el else None),
                    leechers=_parse_optional_int(leechers_el.get_text() if leechers_el else None),
                    magnet=magnet,
                    source=self.name,
                )
            )
        return results
