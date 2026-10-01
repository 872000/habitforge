"""Self-contained offline HTML dashboard generator.

Produces a single HTML file with inline CSS — no external assets, no
JavaScript, no network.  Double-click to open anywhere.
"""

from __future__ import annotations

import html
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from . import dates as d
from .core import completed_periods, consistency_score, habit_stats

if TYPE_CHECKING:
    from .db import HabitDB

CSS = """
:root {
  --bg: #0d1117; --card: #161b22; --border: #30363d;
  --text: #e6edf3; --muted: #8b949e;
  --green-1: #0e4429; --green-2: #006d32; --green-3: #26a641; --green-4: #39d353;
  --empty: #21262d; --accent: #f0883e;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 32px 20px 60px;
  background: var(--bg); color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}
.wrap { max-width: 1080px; margin: 0 auto; }
header.hero { text-align: center; margin-bottom: 28px; }
header.hero h1 { font-size: 2.4rem; margin: 0 0 6px; letter-spacing: -0.5px; }
header.hero h1 .flame { color: var(--accent); }
header.hero p { color: var(--muted); margin: 0; }
.score-card {
  display: flex; gap: 24px; align-items: center; justify-content: center;
  background: var(--card); border: 1px solid var(--border);
  border-radius: 12px; padding: 20px; margin-bottom: 28px;
}
.score-num { font-size: 3rem; font-weight: 700; color: var(--green-4); }
.score-label { color: var(--muted); font-size: 0.9rem; }
.score-meta { color: var(--muted); font-size: 0.85rem; line-height: 1.7; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 18px; }
.card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 12px; padding: 18px;
}
.card h2 { font-size: 1.05rem; margin: 0 0 2px; }
.card .sub { color: var(--muted); font-size: 0.8rem; margin-bottom: 12px; }
.badges { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.badge {
  font-size: 0.8rem; padding: 4px 10px; border-radius: 999px;
  border: 1px solid var(--border); background: var(--bg);
}
.badge.hot { border-color: var(--accent); color: var(--accent); }
.badge.best { border-color: var(--green-3); color: var(--green-4); }
.meter { margin: 8px 0; font-size: 0.8rem; color: var(--muted); }
.meter .bar { height: 6px; background: var(--empty); border-radius: 3px; margin-top: 4px; }
.meter .fill { height: 100%; border-radius: 3px; background: var(--green-3); }
.heatmap { display: flex; gap: 3px; margin-top: 12px; }
.hm-col { display: flex; flex-direction: column; gap: 3px; }
.cell {
  width: 14px; height: 14px; border-radius: 3px; background: var(--empty);
}
.cell.future { opacity: 0.35; }
.cell.l1 { background: var(--green-1); } .cell.l2 { background: var(--green-2); }
.cell.l3 { background: var(--green-3); } .cell.l4 { background: var(--green-4); }
.legend { display: flex; gap: 4px; align-items: center; margin-top: 10px;
          font-size: 0.72rem; color: var(--muted); }
.legend .cell { width: 11px; height: 11px; }
footer { text-align: center; color: var(--muted); font-size: 0.8rem; margin-top: 36px; }
.section-title { font-size: 1.2rem; margin: 0 0 14px; }
"""

WEEKDAY_LABELS = ["M", "T", "W", "T", "F", "S", "S"]


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _heatmap_cells(
    checkin_days: set[date], frequency: str, target: int, weeks: int, ref: date
) -> str:
    """Heatmap HTML: one column per week (daily habits: 7 day-cells)."""
    if frequency == "weekly":
        cols = []
        monday = d.week_monday(ref) - timedelta(weeks=weeks - 1)
        for w in range(weeks):
            week_start = monday + timedelta(weeks=w)
            count = sum(
                1
                for day in checkin_days
                if d.week_monday(day) == week_start
            )
            ratio = min(count / target, 1.0) if target else 0
            level = 0 if count == 0 else 1 + int(ratio * 3.999) if ratio < 1 else 4
            future = " future" if week_start > ref else ""
            title = f"{week_start.strftime('%b %-d')}: {count}/{target} check-ins"
            cols.append(
                f'<div class="hm-col"><div class="cell l{level}{future}" '
                f'title="{_esc(title)}"></div></div>'
            )
        return f'<div class="heatmap">{"".join(cols)}</div>'
    # daily
    end_monday = d.week_monday(ref)
    start_monday = end_monday - timedelta(weeks=weeks - 1)
    cols = []
    for w in range(weeks):
        week_start = start_monday + timedelta(weeks=w)
        cells = []
        for i in range(7):
            day = week_start + timedelta(days=i)
            done = day in checkin_days
            future = " future" if day > ref else ""
            level = " l4" if done else ""
            title = f"{day.strftime('%a %b %-d')}: {'done' if done else 'missed'}"
            cells.append(
                f'<div class="cell{level}{future}" title="{_esc(title)}"></div>'
            )
        cols.append(f'<div class="hm-col">{"".join(cells)}</div>')
    return f'<div class="heatmap">{"".join(cols)}</div>'


def _habit_card(db: "HabitDB", habit, weeks: int, ref: date) -> str:
    days = db.checkin_dates(habit.id)
    stats = habit_stats(habit.id, habit.name, habit.frequency, habit.target, days, ref)
    day_set = set(days)

    cadence = "daily" if habit.frequency == "daily" else f"{habit.target}x per week"
    streak_badge = (
        f'<span class="badge hot">🔥 {stats.current_streak} streak</span>'
        if stats.current_streak
        else '<span class="badge">streak —</span>'
    )
    best_badge = f'<span class="badge best">🏆 best {stats.longest_streak}</span>'
    heat = _heatmap_cells(day_set, habit.frequency, habit.target, weeks, ref)
    unit = "day" if habit.frequency == "daily" else "week"

    def meter(label: str, rate: float) -> str:
        pct = int(rate * 100)
        return (
            f'<div class="meter">{label}: <strong>{pct}%</strong>'
            f'<div class="bar"><div class="fill" style="width:{pct}%"></div></div></div>'
        )

    return f"""
    <div class="card">
      <h2>{_esc(habit.name)}</h2>
      <div class="sub">{cadence} · {len(days)} total check-ins</div>
      <div class="badges">{streak_badge}{best_badge}</div>
      {meter("Last 7 days", stats.rate_7d)}
      {meter("Last 30 days", stats.rate_30d)}
      {heat}
      <div class="legend">Less
        <div class="cell"></div><div class="cell l1"></div><div class="cell l2"></div>
        <div class="cell l3"></div><div class="cell l4"></div> More
        <span style="margin-left:auto">streaks in {unit}s</span>
      </div>
    </div>"""


def generate_dashboard(
    db: "HabitDB", output: Path | str, weeks: int = 12, ref: date | None = None
) -> Path:
    """Render the dashboard HTML and write it to `output`."""
    ref = ref or d.today()
    habits = db.list_habits()
    all_stats = [
        habit_stats(
            h.id, h.name, h.frequency, h.target, db.checkin_dates(h.id), ref
        )
        for h in habits
    ]
    score = consistency_score(all_stats)
    total_checkins = sum(db.checkin_count(h.id) for h in habits)
    active_streaks = sum(1 for s in all_stats if s.current_streak > 0)

    cards = "\n".join(_habit_card(db, h, weeks, ref) for h in habits)
    if not cards:
        cards = (
            '<div class="card"><h2>No habits yet</h2>'
            '<div class="sub">Run <code>habitforge demo</code> to seed sample data, '
            'or <code>habitforge add "Your habit"</code> to start.</div></div>'
        )

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HabitForge Dashboard</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <header class="hero">
    <h1><span class="flame">🔥</span> HabitForge</h1>
    <p>Local-first habit tracking · generated {ref.strftime('%b %-d, %Y')} · works offline</p>
  </header>

  <div class="score-card">
    <div><div class="score-num">{score}</div><div class="score-label">consistency / 100</div></div>
    <div class="score-meta">
      {len(habits)} habits tracked<br>
      {total_checkins} total check-ins<br>
      {active_streaks} active streaks
    </div>
  </div>

  <h2 class="section-title">Habits</h2>
  <div class="grid">
{cards}
  </div>

  <footer>Generated by HabitForge · your data never leaves this machine.</footer>
</div>
</body>
</html>"""

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")
    return out
