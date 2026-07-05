"""Pluggable search providers (v0.5.1a, EXPERIMENTAL/ALPHA).

Post-MVP feature per docs/ARCHITECTURE.md §9 and docs/SCOPE.md: search is
off by default, user-activated, and gated behind an explicit legal-notice
consent (``ui/dialogs.py``'s ``SearchConsentDialog``). ``btdig.py`` is the
first (and, for this alpha, only) provider: HTTP query + HTML parsing
against a btdig-style endpoint — never a DHT crawler/indexer (an explicit
non-goal, docs/SCOPE.md).

Importing this package has no side effects: it does not register, import,
or contact any provider on its own (docs/ARCHITECTURE.md §9's "자동으로
import되지 않는다"). Callers explicitly construct + ``register_provider``
(see ``base.py``) whatever they want.

No Qt import anywhere under ``core/search/`` (docs/ARCHITECTURE.md §1) —
this stays headless-testable like the rest of ``core/``.
"""

from __future__ import annotations
