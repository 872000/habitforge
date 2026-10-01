"""Tests for completion rates and the consistency score."""

from datetime import timedelta

import pytest

from habitforge import dates as d
from habitforge.core import (
    completed_periods,
    completion_rate,
    consistency_score,
    habit_stats,
)


def test_daily_rate_counts_current_day(ref):
    checkins = [ref - timedelta(days=i) for i in range(7)]  # perfect week
    done = completed_periods(checkins, "daily", 1)
    assert completion_rate(done, "daily", 7, ref) == 1.0


def test_daily_rate_partial(ref):
    checkins = [ref - timedelta(days=i) for i in (0, 2, 4)]  # 3 of 7
    done = completed_periods(checkins, "daily", 1)
    assert completion_rate(done, "daily", 7, ref) == 3 / 7


def test_rate_zero_when_nothing_done(ref):
    assert completion_rate(set(), "daily", 30, ref) == 0.0


def test_weekly_rate_uses_weeks_not_days(ref):
    # Two full weeks completed inside a 14-day window -> 2 of 2 (or 3) weeks.
    monday = d.week_monday(ref)
    checkins = [monday - timedelta(weeks=w) for w in (0, 1)]
    done = completed_periods(checkins, "weekly", 1)
    rate = completion_rate(done, "weekly", 14, ref)
    assert rate == pytest.approx(2 / 3)  # 14-day window touches 3 ISO weeks


def test_consistency_score_averages_habits():
    stats = [
        habit_stats(1, "a", "daily", 1, [], None),
        habit_stats(2, "b", "daily", 1, [], None),
    ]
    assert consistency_score(stats) == 0.0
    assert consistency_score([]) == 0.0


def test_habit_stats_shape(db, ref):
    habit = db.add_habit("Read", "daily", 1)
    for i in range(5):
        db.log_checkin(habit.id, ref - timedelta(days=i))
    stats = habit_stats(
        habit.id, habit.name, habit.frequency, habit.target,
        db.checkin_dates(habit.id), ref,
    )
    assert stats.current_streak == 5
    assert stats.longest_streak == 5
    assert stats.rate_7d == pytest.approx(5 / 7, abs=1e-3)
    assert stats.period_complete is True
    assert stats.done_this_period == 1


def test_habit_stats_pending_today(db, ref):
    habit = db.add_habit("Run", "daily", 1)
    db.log_checkin(habit.id, ref - timedelta(days=1))
    stats = habit_stats(
        habit.id, habit.name, habit.frequency, habit.target,
        db.checkin_dates(habit.id), ref,
    )
    assert stats.period_complete is False
    assert stats.done_this_period == 0
    assert stats.current_streak == 1  # yesterday's streak still alive
