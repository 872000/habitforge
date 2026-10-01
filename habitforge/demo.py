"""Deterministic demo data: a few weeks of realistic sample check-ins.

The generator uses a fixed random seed so every run produces the same
lively-looking history — streaks in progress, one broken streak, a weekly
habit with a target, and realistic gaps.  Perfect for trying the CLI and
making the dashboard look alive on first open.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import TYPE_CHECKING

from . import dates as d

if TYPE_CHECKING:
    from .db import HabitDB

# (name, frequency, target, daily_probability)
DEMO_HABITS: list[tuple[str, str, int, float]] = [
    ("Read 20 minutes", "daily", 1, 0.85),
    ("Exercise", "weekly", 3, 0.62),
    ("Meditate", "daily", 1, 0.70),
    ("No sugary drinks", "daily", 1, 0.78),
    ("Call family", "weekly", 1, 0.80),
    ("Journal", "daily", 1, 0.45),
]

DEMO_DAYS = 42
SEED = 20261001


def seed_demo(db: "HabitDB", reset: bool = False, seed: int = SEED) -> dict:
    """Seed the database with sample habits and check-ins.

    Returns a summary dict with habit / check-in / day counts.
    """
    rng = random.Random(seed)
    ref = d.today()

    if reset:
        for habit in db.list_habits():
            db.remove_habit(habit.id)

    existing = {h.name.lower(): h for h in db.list_habits()}
    habits = []
    for name, frequency, target, _ in DEMO_HABITS:
        habit = existing.get(name.lower())
        if habit is None:
            habit = db.add_habit(name, frequency, target)
        habits.append(habit)

    checkins = 0
    start = ref - timedelta(days=DEMO_DAYS - 1)
    for habit, (_, frequency, target, prob) in zip(habits, DEMO_HABITS):
        # Weekly habits: pick `target` days per week with jitter so the
        # target is sometimes missed (real life happens).
        for offset in range(DEMO_DAYS):
            day = start + timedelta(days=offset)
            if day > ref:
                continue
            if frequency == "weekly":
                monday = d.week_monday(day)
                if monday < start:
                    continue
                # Decide once per week, on its Monday.
                if day != monday:
                    continue
                week_days = [monday + timedelta(days=i) for i in range(7)
                             if monday + timedelta(days=i) <= ref]
                want = target if rng.random() < 0.82 else max(0, target - 1)
                picked = rng.sample(week_days, k=min(want, len(week_days)))
                for pick in picked:
                    try:
                        db.log_checkin(habit.id, pick)
                        checkins += 1
                    except Exception:
                        pass
            else:
                # Daily habits: skip a day here and there; occasionally
                # fall off for a few days so streaks tell a story.
                slump = rng.random() < 0.06
                if slump:
                    continue
                if rng.random() < prob:
                    try:
                        db.log_checkin(habit.id, day)
                        checkins += 1
                    except Exception:
                        pass

    return {"habits": len(habits), "checkins": checkins, "days": DEMO_DAYS}
