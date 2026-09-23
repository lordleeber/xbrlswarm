"""SQLite runtime connection policy."""

from .sqlite import connect_database

__all__ = ["connect_database"]
