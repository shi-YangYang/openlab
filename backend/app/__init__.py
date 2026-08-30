"""Application package.

``database`` is kept as an alias of the ``db`` package so the former
``from . import database`` import style (single-module database.py) keeps
working after the split into ``app/db/``.
"""
from . import db as database  # noqa: F401
