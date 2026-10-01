"""Tests for the SQLite persistence layer."""

from datetime import date

import pytest

from habitforge.db import DuplicateCheckin, HabitDB, HabitNotFound


def test_add_and_get_habit(db):
    habit = db.add_habit("Read 20 minutes", "daily", 1)
    assert habit.id > 0
    assert db.get_habit(habit.id).name == "Read 20 minutes"
    assert db.get_habit("read 20 MINUTES").id == habit.id  # case-insensitive


def test_add_duplicate_name_rejected(db):
    db.add_habit("Meditate")
    with pytest.raises(ValueError, match="already exists"):
        db.add_habit("meditate")


def test_add_validates_frequency_and_target(db):
    with pytest.raises(ValueError):
        db.add_habit("X", "monthly", 1)
    with pytest.raises(ValueError):
        db.add_habit("Y", "daily", 3)  # daily habits: one check-in per day
    weekly = db.add_habit("Gym", "weekly", 3)
    assert weekly.target == 3


def test_log_checkin_and_idempotency(db):
    habit = db.add_habit("Journal")
    checkin = db.log_checkin(habit.id, date(2026, 10, 1), note="morning pages")
    assert checkin.date == "2026-10-01"
    assert checkin.note == "morning pages"
    with pytest.raises(DuplicateCheckin):
        db.log_checkin("Journal", date(2026, 10, 1))


def test_log_checkin_unknown_habit(db):
    with pytest.raises(HabitNotFound):
        db.log_checkin("does not exist")


def test_checkin_dates_range(db):
    habit = db.add_habit("Walk")
    for day in (1, 2, 3, 10):
        db.log_checkin(habit.id, date(2026, 9, day))
    dates = db.checkin_dates(habit.id, date(2026, 9, 2), date(2026, 9, 9))
    assert dates == [date(2026, 9, 2), date(2026, 9, 3)]
    assert db.checkin_count(habit.id) == 4


def test_remove_habit_cascades_checkins(db):
    habit = db.add_habit("Temp")
    db.log_checkin(habit.id, date(2026, 10, 1))
    db.remove_habit("temp")
    assert db.list_habits() == []
    with pytest.raises(HabitNotFound):
        db.get_habit(habit.id)


def test_db_file_created_and_reopened(tmp_path):
    path = tmp_path / "sub" / "habits.db"
    first = HabitDB(path)
    first.add_habit("Persistent")
    first.close()
    second = HabitDB(path)
    try:
        assert [h.name for h in second.list_habits()] == ["Persistent"]
    finally:
        second.close()
