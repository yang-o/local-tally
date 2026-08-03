from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address TEXT NOT NULL DEFAULT '',
    remind_days INTEGER NOT NULL DEFAULT 7,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    room_no TEXT NOT NULL,
    area REAL NOT NULL DEFAULT 0,
    lease_status TEXT NOT NULL DEFAULT '空置',
    UNIQUE(project_id, room_no),
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS leases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL,
    deposit REAL NOT NULL DEFAULT 0,
    monthly_rent REAL NOT NULL DEFAULT 0,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    free_start TEXT,
    free_end TEXT,
    status TEXT NOT NULL DEFAULT '生效',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lease_id INTEGER NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    amount REAL NOT NULL,
    paid_at TEXT NOT NULL DEFAULT (date('now', 'localtime')),
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY(lease_id) REFERENCES leases(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS lease_free_periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lease_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    FOREIGN KEY(lease_id) REFERENCES leases(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rooms_project ON rooms(project_id);
CREATE INDEX IF NOT EXISTS idx_leases_room ON leases(room_id);
CREATE INDEX IF NOT EXISTS idx_leases_status ON leases(status);
CREATE INDEX IF NOT EXISTS idx_payments_lease ON payments(lease_id);
CREATE INDEX IF NOT EXISTS idx_free_periods_lease ON lease_free_periods(lease_id);
"""

DEFAULT_SETTINGS = {
    "lease_expire_remind_days": "7",
    "rent_due_remind_days": "7",
}


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            self._seed_settings(conn)
            self._migrate_free_periods(conn)

    def _migrate_free_periods(self, conn: sqlite3.Connection) -> None:
        """将旧版单段免租期迁移到 lease_free_periods。"""
        rows = conn.execute(
            """
            SELECT id, free_start, free_end
            FROM leases
            WHERE free_start IS NOT NULL
              AND free_end IS NOT NULL
              AND TRIM(free_start) != ''
              AND TRIM(free_end) != ''
            """
        ).fetchall()
        for row in rows:
            exists = conn.execute(
                "SELECT 1 FROM lease_free_periods WHERE lease_id = ? LIMIT 1",
                (row["id"],),
            ).fetchone()
            if exists:
                continue
            conn.execute(
                """
                INSERT INTO lease_free_periods (lease_id, start_date, end_date)
                VALUES (?, ?, ?)
                """,
                (row["id"], row["free_start"], row["free_end"]),
            )

    def _seed_settings(self, conn: sqlite3.Connection) -> None:
        defaults = dict(DEFAULT_SETTINGS)

        legacy = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", ("remind_days",)
        ).fetchone()
        if legacy is not None:
            defaults["lease_expire_remind_days"] = legacy["value"]
            defaults["rent_due_remind_days"] = legacy["value"]
        else:
            migrated_remind = conn.execute(
                "SELECT remind_days FROM projects ORDER BY id ASC LIMIT 1"
            ).fetchone()
            if migrated_remind is not None:
                value = str(migrated_remind["remind_days"])
                defaults["lease_expire_remind_days"] = value
                defaults["rent_due_remind_days"] = value

        for key, value in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
                (key, value),
            )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
