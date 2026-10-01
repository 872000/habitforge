"""Zero-config SQLite storage for HabitForge.

A single local database file holds everything.  The default location is
``~/.habitforge/habits.db``; override it with the ``HABITFORGE_DB``
environment variable or the CLI ``--db`` flag.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

from .dates import FREQUENCIES

SCHEMA = """
CREATE TABLE IF NOT EXISTS habits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    frequency   TEXT NOT NULL CHECK (frequency IN ('daily', 'weekly')),
    target      INTEGER NOT NULL DEFAULT 1 CHECK (target >= 1),
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS checkins (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id    INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    date        TEXT NOT NULL,              -- YYYY-MM-DD, day the habit was done
    note        TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    UNIQUE (habit_id, date)
);
CREATE INDEX IF NOT EXISTS idx_checkins_habit_date ON checkins(habit_id, date);
"""


@dataclass
class Habit:
    id: int
    name: str
    frequency: str
    target: int
    created_at: str


@dataclass
class Checkin:
    id: int
    habit_id: int
    date: str  # YYYY-MM-DD
    note: str


class DuplicateCheckin(Exception):
    """Raised when a check-in already exists for that habit and day."""


class HabitNotFound(Exception):
    """Raised when a habit name/id does not match anything."""


def default_db_path() -> Path:
    env = os.environ.get("HABITFORGE_DB")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".habitforge" / "habits.db"


class HabitDB:
    """Thin persistence layer over a single SQLite file."""

    def __init__(self, path: Optional[Path | str] = None):
        self.path = Path(path).expanduser() if path else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)

    # -- habits ---------------------------------------------------------
    def add_habit(self, name: str, frequency: str = "daily", target: int = 1) -> Habit:
        name = name.strip()
        if not name:
            raise ValueError("habit name cannot be empty")
        if frequency not in FREQUENCIES:
            raise ValueError(f"frequency must be one of {FREQUENCIES}")
        if target < 1:
            raise ValueError("target must be >= 1")
        if frequency == "daily" and target != 1:
            raise ValueError("daily habits use one check-in per day (target must be 1)")
        now = datetime.now().isoformat(timespec="seconds")
        try:
            cur = self._conn.execute(
                "INSERT INTO habits (name, frequency, target, created_at) VALUES (?, ?, ?, ?)",
                (name, frequency, target, now),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"a habit named {name!r} already exists") from exc
        self._conn.commit()
        return self.get_habit(cur.lastrowid)

    def get_habit(self, ref: int | str) -> Habit:
        row = self._find_habit_row(ref)
        if row is None:
            raise HabitNotFound(f"no habit matching {ref!r}")
        return self._row_to_habit(row)

    def list_habits(self) -> list[Habit]:
        rows = self._conn.execute("SELECT * FROM habits ORDER BY id").fetchall()
        return [self._row_to_habit(r) for r in rows]

    def remove_habit(self, ref: int | str) -> Habit:
        habit = self.get_habit(ref)
        self._conn.execute("DELETE FROM habits WHERE id = ?", (habit.id,))
        self._conn.commit()
        return habit

    # -- check-ins ------------------------------------------------------
    def log_checkin(
        self, ref: int | str, day: Optional[date] = None, note: str = ""
    ) -> Checkin:
        habit = self.get_habit(ref)
        day = day or date.today()
        iso = day.isoformat()
        now = datetime.now().isoformat(timespec="seconds")
        try:
            cur = self._conn.execute(
                "INSERT INTO checkins (habit_id, date, note, created_at) VALUES (?, ?, ?, ?)",
                (habit.id, iso, note or "", now),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateCheckin(
                f"{habit.name!r} is already checked in for {iso}"
            ) from exc
        self._conn.commit()
        return Checkin(cur.lastrowid, habit.id, iso, note or "")

    def checkin_dates(
        self, habit_id: int, start: Optional[date] = None, end: Optional[date] = None
    ) -> list[date]:
        """All check-in days for a habit, optionally bounded, oldest first."""
        query = "SELECT date FROM checkins WHERE habit_id = ?"
        params: list = [habit_id]
        if start:
            query += " AND date >= ?"
            params.append(start.isoformat())
        if end:
            query += " AND date <= ?"
            params.append(end.isoformat())
        query += " ORDER BY date"
        rows = self._conn.execute(query, params).fetchall()
        return [date.fromisoformat(r["date"]) for r in rows]

    def checkin_count(self, habit_id: int) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM checkins WHERE habit_id = ?", (habit_id,)
        ).fetchone()
        return int(row["n"])

    # -- internals ------------------------------------------------------
    def _find_habit_row(self, ref: int | str) -> Optional[sqlite3.Row]:
        if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
            row = self._conn.execute(
                "SELECT * FROM habits WHERE id = ?", (int(ref),)
            ).fetchone()
            if row:
                return row
        return self._conn.execute(
            "SELECT * FROM habits WHERE lower(name) = lower(?)", (str(ref).strip(),)
        ).fetchone()

    @staticmethod
    def _row_to_habit(row: sqlite3.Row) -> Habit:
        return Habit(
            id=row["id"],
            name=row["name"],
            frequency=row["frequency"],
            target=row["target"],
            created_at=row["created_at"],
        )

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "HabitDB":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def resolve_habits(db: HabitDB, refs: Iterable[int | str]) -> list[Habit]:
    return [db.get_habit(r) for r in refs]
