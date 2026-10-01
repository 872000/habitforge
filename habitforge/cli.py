"""Command-line interface for HabitForge."""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, Sequence

from . import dates as d
from .core import completed_periods, consistency_score, habit_stats, streaks
from .db import (
    DuplicateCheckin,
    Habit,
    HabitDB,
    HabitNotFound,
    default_db_path,
)

CHECK = "✓"
TODO = "○"
FIRE = "🔥"
TROPHY = "🏆"


def _db(args: argparse.Namespace) -> HabitDB:
    return HabitDB(args.db or default_db_path())


def _parse_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid date {value!r}; use YYYY-MM-DD"
        ) from None


# -- commands -----------------------------------------------------------
def cmd_add(args: argparse.Namespace) -> int:
    with _db(args) as db:
        try:
            habit = db.add_habit(args.name, args.frequency, args.target)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    target_txt = f", target {habit.target}x/week" if habit.frequency == "weekly" else ""
    print(f"Added habit #{habit.id}: {habit.name} ({habit.frequency}{target_txt})")
    return 0


def cmd_checkin(args: argparse.Namespace) -> int:
    with _db(args) as db:
        try:
            checkin = db.log_checkin(args.habit, args.date, args.note or "")
        except HabitNotFound as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        except DuplicateCheckin as exc:
            print(f"Note: {exc}", file=sys.stderr)
            return 0
        habit = db.get_habit(checkin.habit_id)
        completed = completed_periods(
            db.checkin_dates(habit.id), habit.frequency, habit.target
        )
        current, longest = streaks(completed, habit.frequency)
    print(f"{CHECK} Checked in {habit.name!r} for {checkin.date} — streak {FIRE} {current} (best {longest})")
    return 0


def cmd_today(args: argparse.Namespace) -> int:
    ref = d.today()
    with _db(args) as db:
        habits = db.list_habits()
        if not habits:
            print("No habits yet. Add one with: habitforge add \"Read 20 minutes\"")
            return 0
        print(f"Today — {ref.strftime('%a %b %-d, %Y')}\n")
        for habit in habits:
            days = db.checkin_dates(habit.id)
            stats = habit_stats(habit.id, habit.name, habit.frequency, habit.target, days, ref)
            current_period = d.period_ordinal(ref, habit.frequency)
            period_name = "today" if habit.frequency == "daily" else "this week"
            if stats.period_complete:
                status = f"{CHECK} done"
            else:
                status = f"{TODO} {stats.done_this_period}/{habit.target} {period_name}"
            streak_txt = f"  {FIRE} {stats.current_streak}" if stats.current_streak else "  streak 0"
            print(f"  {status:28} {habit.name}{streak_txt}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    with _db(args) as db:
        habits = db.list_habits()
        if not habits:
            print("No habits yet.")
            return 0
        print(f"{'ID':>3}  {'Name':32} {'Cadence':10} {'Check-ins'}")
        print("-" * 60)
        for habit in habits:
            n = db.checkin_count(habit.id)
            cadence = habit.frequency if habit.frequency == "daily" else f"weekly x{habit.target}"
            print(f"{habit.id:>3}  {habit.name[:30]:32} {cadence:10} {n}")
    return 0


def cmd_streaks(args: argparse.Namespace) -> int:
    ref = d.today()
    with _db(args) as db:
        habits = db.list_habits()
        if not habits:
            print("No habits yet.")
            return 0
        print(f"{'Habit':32} {'Current':>8} {'Best':>6}")
        print("-" * 52)
        for habit in habits:
            stats = habit_stats(
                habit.id, habit.name, habit.frequency, habit.target,
                db.checkin_dates(habit.id), ref,
            )
            unit = "days" if habit.frequency == "daily" else "wks"
            fire = f" {FIRE}" if stats.current_streak > 0 else ""
            print(f"{habit.name[:30]:32} {stats.current_streak:>5} {unit}{fire} {stats.longest_streak:>4} {unit}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    ref = d.today()
    with _db(args) as db:
        habits = db.list_habits()
        if not habits:
            print("No habits yet.")
            return 0
        rows = [
            habit_stats(
                h.id, h.name, h.frequency, h.target, db.checkin_dates(h.id), ref
            )
            for h in habits
        ]
        score = consistency_score(rows)
        print(f"Consistency score (30d): {score}/100\n")
        print(f"{'Habit':32} {'7-day':>7} {'30-day':>7} {'Streak':>8}")
        print("-" * 60)
        for s in rows:
            fire = f"{FIRE} " if s.current_streak else ""
            print(
                f"{s.name[:30]:32} {s.rate_7d:>6.0%} {s.rate_30d:>6.0%} "
                f"{fire}{s.current_streak:>3} (best {s.longest_streak})"
            )
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    from .dashboard import generate_dashboard

    out = Path(args.output or "habitforge-dashboard.html")
    with _db(args) as db:
        generate_dashboard(db, out, weeks=args.weeks)
    print(f"Dashboard written to {out.resolve()}")
    print("Open it in any browser — it works fully offline.")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    from .demo import seed_demo

    with _db(args) as db:
        summary = seed_demo(db, reset=args.reset)
    print(f"Seeded {summary['habits']} habits with {summary['checkins']} check-ins "
          f"across {summary['days']} days of sample history.")
    print("Try: habitforge today   •   habitforge stats   •   habitforge dashboard")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    with _db(args) as db:
        try:
            habit = db.get_habit(args.habit)
        except HabitNotFound as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        if not args.yes:
            answer = input(f"Remove {habit.name!r} and all its check-ins? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                print("Cancelled.")
                return 0
        db.remove_habit(habit.id)
    print(f"Removed {habit.name!r}.")
    return 0


# -- parser -------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="habitforge",
        description="HabitForge — a local-first habit tracker with streaks, "
                    "stats and an offline dashboard.",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="path to the SQLite database file "
             f"(default: {default_db_path()}, or $HABITFORGE_DB)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add", help="add a new habit")
    p.add_argument("name", help="habit name, e.g. \"Read 20 minutes\"")
    p.add_argument("--frequency", choices=["daily", "weekly"], default="daily")
    p.add_argument("--target", type=int, default=1,
                   help="check-ins per week for weekly habits (default: 1)")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("checkin", help="log a check-in")
    p.add_argument("habit", help="habit name or id")
    p.add_argument("--date", type=_parse_day, default=None,
                   help="check-in date as YYYY-MM-DD (default: today)")
    p.add_argument("--note", default="", help="optional note")
    p.set_defaults(func=cmd_checkin)

    p = sub.add_parser("today", help="show today's habit list")
    p.set_defaults(func=cmd_today)

    p = sub.add_parser("list", help="list all habits")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("streaks", help="show current and longest streaks")
    p.set_defaults(func=cmd_streaks)

    p = sub.add_parser("stats", help="show completion rates and consistency score")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("dashboard", help="generate the offline HTML dashboard")
    p.add_argument("-o", "--output", default=None,
                   help="output HTML file (default: habitforge-dashboard.html)")
    p.add_argument("--weeks", type=int, default=12,
                   help="weeks of history in the heatmap (default: 12)")
    p.set_defaults(func=cmd_dashboard)

    p = sub.add_parser("demo", help="seed realistic sample data")
    p.add_argument("--reset", action="store_true",
                   help="wipe existing habits before seeding")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("remove", help="remove a habit and its check-ins")
    p.add_argument("habit", help="habit name or id")
    p.add_argument("--yes", action="store_true", help="skip confirmation")
    p.set_defaults(func=cmd_remove)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
