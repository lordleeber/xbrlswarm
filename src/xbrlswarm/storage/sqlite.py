"""Open runtime SQLite connections with evidence history safeguards."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path


_IMMUTABLE_PAIR = re.compile(
    r'\bOLD\."?(\w+)"?\s+IS\s+NOT\s+NEW\."?\1"?',
    re.IGNORECASE,
)


def _validate_evidence_guard(connection: sqlite3.Connection) -> None:
    evidence_exists = connection.execute(
        "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'evidence'"
    ).fetchone()
    if not evidence_exists:
        return

    trigger_rows = connection.execute(
        """
        SELECT name, sql FROM sqlite_schema
        WHERE type = 'trigger' AND tbl_name = 'evidence'
        """
    ).fetchall()
    triggers = {name: sql for name, sql in trigger_rows}
    if "evidence_source_immutable_delete" not in triggers:
        raise RuntimeError("missing evidence deletion guard")
    update_sql = triggers.get("evidence_source_immutable_update")
    if update_sql is None:
        raise RuntimeError("missing evidence update guard")

    source_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(evidence)")
    } - {"verification_state"}
    covered_columns = {
        column.lower() for column in _IMMUTABLE_PAIR.findall(update_sql)
    }
    unprotected = sorted(source_columns - covered_columns)
    if unprotected:
        raise RuntimeError(
            "unprotected evidence columns: " + ", ".join(unprotected)
        )


def connect_database(path: str | Path) -> sqlite3.Connection:
    """Open a runtime connection and reject an incomplete evidence guard."""

    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA recursive_triggers = ON")
        for setting in ("foreign_keys", "recursive_triggers"):
            enabled = connection.execute(f"PRAGMA {setting}").fetchone()
            if enabled is None or enabled[0] != 1:
                raise RuntimeError(f"SQLite {setting} must be enabled")
        _validate_evidence_guard(connection)
    except BaseException:
        connection.close()
        raise
    return connection
