import sqlite3
from pathlib import Path

import pytest


MIGRATIONS = Path("migrations")


def _connect(path: str | Path) -> sqlite3.Connection:
    from xbrlswarm.storage import connect_database

    return connect_database(path)


def _apply_migrations(connection: sqlite3.Connection) -> None:
    for path in sorted(MIGRATIONS.glob("*.sql")):
        connection.executescript(path.read_text(encoding="utf-8"))


def test_runtime_connection_enables_foreign_keys_and_recursive_triggers() -> None:
    connection = _connect(":memory:")

    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert connection.execute("PRAGMA recursive_triggers").fetchone()[0] == 1


def test_reopened_database_rejects_new_unprotected_source_column(tmp_path: Path) -> None:
    path = tmp_path / "step14.sqlite"
    connection = sqlite3.connect(path)
    _apply_migrations(connection)
    connection.execute("ALTER TABLE evidence ADD COLUMN filing_kind TEXT")
    connection.close()

    with pytest.raises(RuntimeError, match="unprotected evidence columns: filing_kind"):
        _connect(path)


def test_reopened_database_accepts_current_immutability_guard(tmp_path: Path) -> None:
    path = tmp_path / "step14.sqlite"
    connection = sqlite3.connect(path)
    _apply_migrations(connection)
    connection.close()

    reopened = _connect(path)

    assert reopened.execute("PRAGMA recursive_triggers").fetchone()[0] == 1
    reopened.close()
