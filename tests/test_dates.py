"""Tests for period arithmetic (daily/weekly ordinals)."""
from datetime import date

from habitforge import dates


def test_weekly_period_start_round_trips_to_monday():
    # Regression: period_start used ordinal*7, but Monday ordinals are
    # 1 (mod 7), so the round-trip landed on the previous Sunday.
    monday = date(2026, 9, 28)
    assert monday.strftime("%A") == "Monday"
    ordinal = dates.period_ordinal(monday, "weekly")
    assert dates.period_start(ordinal, "weekly") == monday


def test_daily_period_start_round_trips():
    day = date(2026, 9, 28)
    assert dates.period_start(dates.period_ordinal(day, "daily"), "daily") == day


def test_weekly_label_spans_monday_to_sunday():
    monday = date(2026, 9, 28)
    ordinal = dates.period_ordinal(monday, "weekly")
    assert dates.period_label(ordinal, "weekly") == "Sep 28–Oct 4"
