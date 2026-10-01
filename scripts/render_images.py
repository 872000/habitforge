"""Render the README images by running the real HabitForge code.

- docs/hero.png:        project banner (stylized, programmatic).
- docs/screenshot.png:  real streak/stats chart computed from demo data
                        seeded through habitforge.demo.seed_demo.

Run:  python scripts/render_images.py
Requires: matplotlib (dev tooling only; the app itself is stdlib-only).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from habitforge import dates as d  # noqa: E402
from habitforge.core import consistency_score, habit_stats  # noqa: E402
from habitforge.db import HabitDB  # noqa: E402
from habitforge.demo import seed_demo  # noqa: E402

BG = "#0d1117"
CARD = "#161b22"
GREEN = "#39d353"
GREEN_DIM = "#0e4429"
ORANGE = "#f0883e"
TEXT = "#e6edf3"
MUTED = "#8b949e"

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def demo_stats():
    """Seed a throwaway DB and return per-habit stats from real code."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = HabitDB(tmp.name)
    try:
        seed_demo(db)
        ref = d.today()
        stats = [
            habit_stats(
                h.id, h.name, h.frequency, h.target, db.checkin_dates(h.id), ref
            )
            for h in db.list_habits()
        ]
        return stats, consistency_score(stats)
    finally:
        db.close()


def render_hero(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 4.2))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 4.2)
    ax.axis("off")

    # Subtle glow bar on the left.
    for i, alpha in enumerate([0.10, 0.06, 0.03]):
        ax.add_patch(
            Rectangle((0.15 + i * 0.35, 0.2), 0.22, 3.8,
                      facecolor=GREEN, alpha=alpha, edgecolor="none")
        )

    ax.text(1.1, 2.75, "HabitForge", fontsize=52, weight="bold", color=TEXT,
            va="center", family="sans-serif")
    ax.text(1.15, 2.05,
            "Local-first habit tracking — streaks, stats & an offline dashboard.",
            fontsize=15, color=MUTED, va="center")
    ax.text(1.15, 1.35, "Python  •  SQLite  •  Zero-config  •  Works offline",
            fontsize=12, color=GREEN, va="center", family="monospace")

    # Heatmap motif on the right.
    rng_rows, rng_cols = 7, 10
    import random
    rng = random.Random(7)
    for r in range(rng_rows):
        for c in range(rng_cols):
            x, y = 8.6 + c * 0.30, 0.75 + r * 0.30
            lit = rng.random()
            color = BG if lit < 0.35 else (GREEN_DIM if lit < 0.7 else GREEN)
            ax.add_patch(Rectangle((x, y), 0.24, 0.24, facecolor=color,
                                   edgecolor="none", alpha=0.95))

    fig.tight_layout(pad=0.4)
    fig.savefig(path, dpi=110, facecolor=BG)
    plt.close(fig)


def render_screenshot(path: Path, stats, score: float) -> None:
    names = [s.name for s in stats]
    current = [s.current_streak for s in stats]
    longest = [s.longest_streak for s in stats]
    rates = [s.rate_30d * 100 for s in stats]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6.2))
    fig.patch.set_facecolor(BG)
    for ax in (ax1, ax2):
        ax.set_facecolor(BG)
        ax.tick_params(colors=MUTED)
        for spine in ax.spines.values():
            spine.set_color("#30363d")

    y = range(len(names))
    ax1.barh(y, longest, height=0.55, color="#30363d", label="longest")
    ax1.barh(y, current, height=0.55, color=GREEN, label="current")
    ax1.set_yticks(list(y))
    ax1.set_yticklabels(names, color=TEXT, fontsize=10)
    ax1.invert_yaxis()
    ax1.set_xlabel("periods", color=MUTED)
    ax1.set_title("Streaks per habit", color=TEXT, fontsize=13, weight="bold", pad=12)
    ax1.legend(frameon=False, labelcolor=MUTED, loc="lower right")
    for i, (c, b) in enumerate(zip(current, longest)):
        ax1.text(max(c, b) + 0.3, i, f"{c} / {b}", color=MUTED, va="center", fontsize=9)

    bars = ax2.barh(y, rates, height=0.55, color=ORANGE)
    ax2.set_yticks(list(y))
    ax2.set_yticklabels(names, color=TEXT, fontsize=10)
    ax2.invert_yaxis()
    ax2.set_xlim(0, 105)
    ax2.set_xlabel("completion %", color=MUTED)
    ax2.set_title("30-day completion rate", color=TEXT, fontsize=13, weight="bold", pad=12)
    for bar, rate in zip(bars, rates):
        ax2.text(rate + 1.5, bar.get_y() + bar.get_height() / 2, f"{rate:.0f}%",
                 color=MUTED, va="center", fontsize=9)

    fig.suptitle(
        f"HabitForge — live stats from demo data   ·   consistency score {score}/100",
        color=TEXT, fontsize=14, weight="bold", y=0.97,
    )
    fig.text(0.5, 0.02,
             "Rendered by scripts/render_images.py from real habitforge output (habitforge.demo.seed_demo + habitforge.core)",
             ha="center", color=MUTED, fontsize=8, style="italic")
    fig.tight_layout(rect=[0, 0.05, 1, 0.92])
    fig.savefig(path, dpi=110, facecolor=BG)
    plt.close(fig)


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    stats, score = demo_stats()
    hero = DOCS / "hero.png"
    shot = DOCS / "screenshot.png"
    render_hero(hero)
    render_screenshot(shot, stats, score)
    print(f"Wrote {hero} ({hero.stat().st_size // 1024} KB)")
    print(f"Wrote {shot} ({shot.stat().st_size // 1024} KB)")
    print(f"Stats source: {len(stats)} habits, consistency score {score}/100")


if __name__ == "__main__":
    main()
