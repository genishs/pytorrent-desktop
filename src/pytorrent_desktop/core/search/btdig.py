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
originally not available to verify against, since docs/SCOPE.md forbids live
network access during development/CI, so ``_parse_results`` was first written
against a documented, plausible result-row shape. The magnet-anchor location
and the ``.torrent_files``/``.torrent_age``/``.torrent_excerpt`` fields below
were since live-verified (2026-07-05, one-off manual fetch outside the test
run) and captured into ``tests/fixtures/btdig_results_real.html`` — every
test still only ever exercises the saved HTML fixtures in ``tests/fixtures/``,
never a live request (docs/SCOPE.md's hard requirement).
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

# btdig sort mode (numeric): order=2 = most-recently-found first (recency).
# Used as the default so freshly-seen (more likely still-alive) torrents surface
# first, instead of btdig's relevance ordering which mixes in decade-old results.
_DEFAULT_ORDER = 2

_USER_AGENT = (
    "pytorrent-desktop/0.5.1a (experimental search feature; "
    "+https://github.com/genishs/pytorrent-desktop)"
)

_SIZE_PATTERN = re.compile(r"([\d.]+)\s*([A-Za-z]+)")
# btdig's magnet is either urn:btih (v1) or urn:btmh (v2/hybrid); both are
# hex-ish identifiers we just need to lift out verbatim (docs/DECISIONS.md D5).
_INFO_HASH_PATTERN = re.compile(r"urn:bt(?:ih|mh):([0-9A-Za-z]+)", re.IGNORECASE)
_WHITESPACE_RUN = re.compile(r"\s+")
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


def _info_hash_from_magnet(magnet: str) -> str | None:
    """Pull the ``xt=urn:bt(ih|mh):HASH`` identifier out of a magnet URI."""
    match = _INFO_HASH_PATTERN.search(magnet)
    return match.group(1) if match else None


def _clean_text(el) -> str:
    """``get_text()`` with a space separator, whitespace-collapsed.

    btdig wraps the matched search term in ``<b>...</b>`` inside
    ``.torrent_name`` (live-verified 2026-07-05, e.g. ``<a><b>Ubuntu</b>
    MATE ISO Archive (2025)</a>``). A plain ``get_text(strip=True)`` strips
    each text node individually before concatenating them, which silently
    swallows the space between the bolded term and the rest of the title
    (``"UbuntuMATE ISO..."``). Using a space separator and then collapsing
    whitespace runs keeps the title readable regardless of where btdig
    happens to split it with markup.
    """
    if el is None:
        return ""
    return _WHITESPACE_RUN.sub(" ", el.get_text(separator=" ")).strip()


def _parse_excerpt_lines(excerpt_el) -> list[str] | None:
    """Turn btdig's ``.torrent_excerpt`` file-tree preview into a flat list
    of one string per row (folder names, file names + size, and the
    "N hidden files" summary row), or ``None`` if there is no excerpt.

    btdig separates each row with a bare ``<br>`` inside a single
    ``display:table`` div rather than one element per row, so rows are
    recovered by replacing every ``<br>`` with a newline and splitting the
    resulting text on it — simpler and more robust than reconstructing
    "which size ``<span>`` belongs to which file ``<div>``" from sibling
    relationships.
    """
    if excerpt_el is None:
        return None
    for br in excerpt_el.find_all("br"):
        br.replace_with("\n")
    lines = [
        _WHITESPACE_RUN.sub(" ", line).strip() for line in excerpt_el.get_text(" ").split("\n")
    ]
    lines = [line for line in lines if line]
    return lines or None


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

    def search(
        self, query: str, *, page: int = 0, timeout: float = 10.0
    ) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []

        try:
            response = self._session.get(
                f"{self._base_url}/search",
                # btdig pages results 0-based via ``p`` (its ``page`` query
                # param is silently ignored) — live-verified 2026-07-05:
                # ``p=1`` returns the next ~PAGE_SIZE results after ``p=0``.
                params={"q": query, "p": page, "order": _DEFAULT_ORDER},
                timeout=timeout,
                headers={"User-Agent": _USER_AGENT},
            )
            response.raise_for_status()
            # btdig serves UTF-8, but requests defaults text/html without a
            # charset in the HTTP header to ISO-8859-1, which mangles non-ASCII
            # (e.g. Cyrillic/CJK) torrent names. Force UTF-8.
            response.encoding = "utf-8"
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
            # btdig puts the magnet in its own <a href="magnet:..."> in the
            # row (inside div.torrent_magnet) — NOT as the title link's href.
            # The title link (.torrent_name a) points at btdig's detail page.
            magnet_el = row.select_one("a[href^='magnet:']")
            if magnet_el is None:
                # Defensive: skip a malformed row rather than failing the
                # whole page. "Never partial/garbage results" (§9) is about
                # not fabricating junk entries, not about refusing to skip
                # one bad row among otherwise-good ones.
                continue
            magnet = (magnet_el.get("href") or "").strip()
            if not magnet.startswith("magnet:"):
                continue
            name_el = row.select_one(".torrent_name a")
            title = _clean_text(name_el) or _title_from_magnet(magnet)

            size_el = row.select_one(".torrent_size")
            seeders_el = row.select_one(".torrent_seeders")
            leechers_el = row.select_one(".torrent_leechers")
            files_count_el = row.select_one(".torrent_files")
            age_el = row.select_one(".torrent_age")
            excerpt_el = row.select_one(".torrent_excerpt")

            results.append(
                SearchResult(
                    title=title,
                    size_bytes=_parse_size_to_bytes(size_el.get_text() if size_el else None),
                    seeders=_parse_optional_int(seeders_el.get_text() if seeders_el else None),
                    leechers=_parse_optional_int(leechers_el.get_text() if leechers_el else None),
                    magnet=magnet,
                    source=self.name,
                    num_files=_parse_optional_int(
                        files_count_el.get_text() if files_count_el else None
                    ),
                    age=_clean_text(age_el) or None,
                    files=_parse_excerpt_lines(excerpt_el),
                    info_hash=_info_hash_from_magnet(magnet),
                )
            )
        return results
