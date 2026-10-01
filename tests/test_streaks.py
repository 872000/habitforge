"""Tests for the streak engine: daily vs weekly cadence, missed periods."""

from datetime import date, timedelta

import pytest

from habitforge import dates as d
from habitforge.core import completed_periods, streaks


def days(ref, *offsets):
    """Check-in dates `offset` days before ref."""
    return [ref - timedelta(days=o) for o in offsets]


def weeks_of(ref, *week_offsets):
    """One check-in (Monday) per given week offset before ref's week."""
    monday = d.week_monday(ref)
    return [monday - timedelta(weeks=o) for o in week_offsets]


class TestDailyStreaks:
    def test_empty(self, ref):
        assert streaks(set(), "daily", ref) == (0, 0)

    def test_run_ending_today(self, ref):
        done = completed_periods(days(ref, 0, 1, 2, 3, 4), "daily", 1)
        assert streaks(done, "daily", ref) == (5, 5)

    def test_run_ending_yesterday_stays_alive(self, ref):
        # Today not logged yet, but nothing missed: streak is alive.
        done = completed_periods(days(ref, 1, 2, 3), "daily", 1)
        assert streaks(done, "daily", ref) == (3, 3)

    def test_missed_yesterday_breaks_streak(self, ref):
        done = completed_periods(days(ref, 2, 3, 4), "daily", 1)
        current, longest = streaks(done, "daily", ref)
        assert current == 0
        assert longest == 3

    def test_gap_splits_runs(self, ref):
        # Days ago: 0,1,2,4,5,6 -> trailing run of 3, longest run of 3.
        done = completed_periods(days(ref, 0, 1, 2, 4, 5, 6), "daily", 1)
        assert streaks(done, "daily", ref) == (3, 3)

    def test_longest_survives_break(self, ref):
        # Old 10-day run, then a gap, then 2 fresh days.
        old = list(range(12, 22))
        done = completed_periods(days(ref, 0, 1, *old), "daily", 1)
        current, longest = streaks(done, "daily", ref)
        assert (current, longest) == (2, 10)

    def test_single_checkin_long_ago(self, ref):
        done = completed_periods(days(ref, 30), "daily", 1)
        assert streaks(done, "daily", ref) == (0, 1)


class TestWeeklyStreaks:
    def test_three_week_run(self, ref):
        done = completed_periods(weeks_of(ref, 0, 1, 2), "weekly", 1)
        assert streaks(done, "weekly", ref) == (3, 3)

    def test_current_week_pending_stays_alive(self, ref):
        done = completed_periods(weeks_of(ref, 1, 2), "weekly", 1)
        assert streaks(done, "weekly", ref) == (2, 2)

    def test_missed_week_breaks_streak(self, ref):
        done = completed_periods(weeks_of(ref, 2, 3), "weekly", 1)
        current, longest = streaks(done, "weekly", ref)
        assert current == 0
        assert longest == 2

    def test_target_must_be_met(self, ref):
        # Only 1 of 2 required check-ins in the latest week -> not complete.
        monday = d.week_monday(ref)
        checkins = [monday, monday - timedelta(weeks=1), monday - timedelta(weeks=1, days=-1)]
        done = completed_periods(checkins, "weekly", 2)
        current, longest = streaks(done, "weekly", ref)
        assert current == 1      # last week's completion still alive; this week pending
        assert longest == 1

    def test_target_met_counts(self, ref):
        monday = d.week_monday(ref)
        checkins = [
            monday, monday + timedelta(days=1),
            monday - timedelta(weeks=1), monday - timedelta(weeks=1) + timedelta(days=3),
        ]
        done = completed_periods(checkins, "weekly", 2)
        assert streaks(done, "weekly", ref) == (2, 2)

    def test_week_boundary_sunday_monday(self):
        # Sunday and the next day (Monday) belong to different weeks.
        sunday = date(2026, 10, 4)
        monday = date(2026, 10, 5)
        assert d.period_ordinal(sunday, "weekly") + 1 == d.period_ordinal(monday, "weekly")
        done = completed_periods([sunday, monday], "weekly", 1)
        assert streaks(done, "weekly", ref=monday) == (2, 2)
