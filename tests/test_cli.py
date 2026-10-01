"""End-to-end CLI tests plus dashboard and demo coverage."""

import os
from pathlib import Path

import pytest

from habitforge.cli import main
from habitforge.dashboard import generate_dashboard
from habitforge.db import HabitDB
from habitforge.demo import seed_demo


@pytest.fixture()
def cli_db(tmp_path, monkeypatch):
    path = tmp_path / "cli.db"
    monkeypatch.setenv("HABITFORGE_DB", str(path))
    return path


def run_cli(*argv, capsys):
    code = main(list(argv))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_add_checkin_today_flow(cli_db, capsys):
    assert run_cli("add", "Read 20 minutes", capsys=capsys)[0] == 0
    code, out, _ = run_cli("checkin", "Read 20 minutes", capsys=capsys)
    assert code == 0 and "Checked in" in out
    code, out, _ = run_cli("today", capsys=capsys)
    assert code == 0 and "Read 20 minutes" in out and "done" in out


def test_checkin_twice_is_idempotent(cli_db, capsys):
    run_cli("add", "Meditate", capsys=capsys)
    run_cli("checkin", "Meditate", capsys=capsys)
    code, out, err = run_cli("checkin", "Meditate", capsys=capsys)
    assert code == 0 and "already checked in" in err


def test_checkin_unknown_habit_fails(cli_db, capsys):
    code, _, err = run_cli("checkin", "nope", capsys=capsys)
    assert code == 1 and "no habit" in err


def test_streaks_and_stats_commands(cli_db, capsys):
    run_cli("add", "Exercise", "--frequency", "weekly", "--target", "3", capsys=capsys)
    code, out, _ = run_cli("streaks", capsys=capsys)
    assert code == 0 and "Exercise" in out
    code, out, _ = run_cli("stats", capsys=capsys)
    assert code == 0 and "Consistency score" in out


def test_list_and_remove(cli_db, capsys, monkeypatch):
    run_cli("add", "Temp habit", capsys=capsys)
    code, out, _ = run_cli("list", capsys=capsys)
    assert code == 0 and "Temp habit" in out
    monkeypatch.setattr("builtins.input", lambda _: "y")
    code, out, _ = run_cli("remove", "Temp habit", capsys=capsys)
    assert code == 0 and "Removed" in out


def test_dashboard_command_generates_file(cli_db, tmp_path, capsys):
    run_cli("add", "Read", capsys=capsys)
    run_cli("checkin", "Read", capsys=capsys)
    out_file = tmp_path / "dash.html"
    code, out, _ = run_cli("dashboard", "-o", str(out_file), capsys=capsys)
    assert code == 0 and out_file.exists()
    html_text = out_file.read_text()
    assert "Read" in html_text and "HabitForge" in html_text


def test_demo_command_seeds_data(cli_db, capsys):
    code, out, _ = run_cli("demo", capsys=capsys)
    assert code == 0 and "Seeded" in out
    db = HabitDB(os.environ["HABITFORGE_DB"])
    try:
        assert len(db.list_habits()) == 6
        assert sum(db.checkin_count(h.id) for h in db.list_habits()) > 50
    finally:
        db.close()


def test_generate_dashboard_offline_and_complete(tmp_path):
    db_path = tmp_path / "d.db"
    db = HabitDB(db_path)
    try:
        summary = seed_demo(db)
        assert summary["checkins"] > 50
        out = generate_dashboard(db, tmp_path / "out.html", weeks=12)
        text = out.read_text(encoding="utf-8")
    finally:
        db.close()
    # Self-contained: no external assets, scripts, or links.
    assert "<link" not in text
    assert "src=" not in text
    assert "http" not in text
    for name in ("Read 20 minutes", "Exercise", "Meditate", "Journal"):
        assert name in text
    assert "consistency / 100" in text


def test_seed_demo_is_deterministic(tmp_path):
    first = HabitDB(tmp_path / "a.db")
    second = HabitDB(tmp_path / "b.db")
    try:
        seed_demo(first)
        seed_demo(second)
        a = sorted(
            (h.name, d.isoformat())
            for h in first.list_habits()
            for d in first.checkin_dates(h.id)
        )
        b = sorted(
            (h.name, d.isoformat())
            for h in second.list_habits()
            for d in second.checkin_dates(h.id)
        )
    finally:
        first.close()
        second.close()
    assert a == b and len(a) > 50
