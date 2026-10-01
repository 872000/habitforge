"""Shared pytest fixtures."""

from datetime import date

import pytest

from habitforge.db import HabitDB


@pytest.fixture()
def db(tmp_path):
    database = HabitDB(tmp_path / "test.db")
    yield database
    database.close()


@pytest.fixture()
def ref():
    # A fixed Wednesday, so streak/period math is deterministic.
    return date(2026, 10, 7)
