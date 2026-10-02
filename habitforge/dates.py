"""Period arithmetic for daily and weekly habit cadences.

A *period* is the unit a habit is measured in: one calendar day for daily
habits, one ISO week (Monday–Sunday) for weekly habits.  Every period maps
to a single integer ordinal so streak math is just integer runs.
"""

from __future__ import annotations

from datetime import date, timedelta

FREQUENCIES = ("daily", "weekly")


def today() -> date:
    return date.today()


def period_ordinal(day: date, frequency: str) -> int:
    """Map a calendar day to its period ordinal for the given cadence."""
    if frequency == "daily":
        return day.toordinal()
    if frequency == "weekly":
        monday = day - timedelta(days=day.weekday())
        return monday.toordinal() // 7
    raise ValueError(f"unknown frequency: {frequency!r} (expected 'daily' or 'weekly')")


def period_start(ordinal: int, frequency: str) -> date:
    """First calendar day of a period ordinal."""
    if frequency == "daily":
        return date.fromordinal(ordinal)
    if frequency == "weekly":
        # Monday ordinals are 1 (mod 7) — 0001-01-01 was a Monday — so the
        # inverse of period_ordinal's //7 is *7 + 1, not *7.
        return date.fromordinal(ordinal * 7 + 1)
    raise ValueError(f"unknown frequency: {frequency!r}")


def period_label(ordinal: int, frequency: str) -> str:
    """Human-readable label for a period ordinal."""
    start = period_start(ordinal, frequency)
    if frequency == "daily":
        return start.strftime("%b %-d")
    end = start + timedelta(days=6)
    return f"{start.strftime('%b %-d')}–{end.strftime('%b %-d')}"


def periods_between(start: date, end: date, frequency: str) -> list[int]:
    """All period ordinals touching the inclusive date range [start, end]."""
    if start > end:
        return []
    ordinals: list[int] = []
    seen: set[int] = set()
    day = start
    while day <= end:
        ordinal = period_ordinal(day, frequency)
        if ordinal not in seen:
            seen.add(ordinal)
            ordinals.append(ordinal)
        day += timedelta(days=1)
    return ordinals


def week_monday(day: date) -> date:
    return day - timedelta(days=day.weekday())
