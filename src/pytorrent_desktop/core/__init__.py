"""Core torrent engine (GUI-independent).

Everything in this package must stay free of any PySide6/Qt import so it can be
unit-tested headlessly and reused by a future CLI or daemon front end.
"""
