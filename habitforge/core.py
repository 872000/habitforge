"""Streak and statistics engine.

A habit is "complete" for a period when its check-in count in that period
meets its target (e.g. 3 check-ins in the week for a 3x/week habit).

Streak rules:
- *Current streak*: length of the trailing run of completed periods ending
  at the most recent completed period.  It stays alive while the current
  period is still in progress (you haven't missed anything yet).  If a full
  period has passed with no completion, the streak is broken and reads 0.
- *Longest streak*: the longest run of consecutive completed periods ever.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

from . import dates as d


def completed_periods(
    checkin_days: list[date], frequency: str, target: int
) -> set[int]:
    """Period ordinals in which the target was met."""
    counts: Counter[int] = Counter(
        d.period_ordinal(day, frequency) for day in checkin_days
    )
    return {ordinal for ordinal, n in counts.items() if n >= target}


def streaks(
    completed: set[int], frequency: str, ref: date | None = None
) -> tuple[int, int]:
    """Return (current_streak, longest_streak) for completed period ordinals."""
    ref = ref or d.today()
    current_period = d.period_ordinal(ref, frequency)
    if not completed:
        return (0, 0)

    ordered = sorted(completed)

    longest = 0
    run = 0
    prev: int | None = None
    for ordinal in ordered:
        run = run + 1 if prev is not None and ordinal == prev + 1 else 1
        longest = max(longest, run)
        prev = ordinal

    latest = ordered[-1]
    if current_period - latest > 1:
        # At least one full period elapsed with no completion: streak broken.
        return (0, longest)

    current = 0
    ordinal = latest
    while ordinal in completed:
        current += 1
        ordinal -= 1
    return (current, longest)


@dataclass
class HabitStats:
    habit_id: int
    name: str
    frequency: str
    target: int
    current_streak: int
    longest_streak: int
    rate_7d: float   # 0.0 – 1.0
    rate_30d: float  # 0.0 – 1.0
    done_this_period: int  # check-ins logged in the current period
    period_complete: bool


def completion_rate(
    completed: set[int],
    frequency: str,
    days: int,
    ref: date | None = None,
) -> float:
    """Fraction of periods completed over the trailing `days` days.

    The current in-progress period counts, so a weekly habit checked on
    Wednesday already shows this week as complete.
    """
    ref = ref or d.today()
    start = ref - timedelta(days=days - 1)
    periods = d.periods_between(start, ref, frequency)
    if not periods:
        return 0.0
    done = sum(1 for ordinal in periods if ordinal in completed)
    return done / len(periods)


def consistency_score(stats: list[HabitStats]) -> float:
    """Overall 0–100 score: the mean 30-day completion rate across habits."""
    if not stats:
        return 0.0
    return round(sum(s.rate_30d for s in stats) / len(stats) * 100, 1)


def habit_stats(
    habit_id: int,
    name: str,
    frequency: str,
    target: int,
    checkin_days: list[date],
    ref: date | None = None,
) -> HabitStats:
    """Build the full stats row for one habit as of `ref` (default: today)."""
    ref = ref or d.today()
    completed = completed_periods(checkin_days, frequency, target)
    current, longest = streaks(completed, frequency, ref)
    current_period = d.period_ordinal(ref, frequency)
    done_this_period = sum(
        1 for day in checkin_days if d.period_ordinal(day, frequency) == current_period
    )
    return HabitStats(
        habit_id=habit_id,
        name=name,
        frequency=frequency,
        target=target,
        current_streak=current,
        longest_streak=longest,
        rate_7d=round(completion_rate(completed, frequency, 7, ref), 3),
        rate_30d=round(completion_rate(completed, frequency, 30, ref), 3),
        done_this_period=done_this_period,
        period_complete=current_period in completed,
    )
