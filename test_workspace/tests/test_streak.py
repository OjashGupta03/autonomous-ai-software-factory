import pytest
from datetime import date, timedelta
from src.streak import calculate_streak, calculate_all_streaks
from src.habits import Habit

def test_calculate_streak_daily_basic(tmp_path):
    today = date.today()
    d1 = (today - timedelta(days=2)).isoformat()
    d2 = (today - timedelta(days=1)).isoformat()
    d3 = today.isoformat()

    habit = Habit(id="h1", name="Exercise", frequency="daily", target_count=1, start_date=d1)
    progress = [
        {"habitId": "h1", "date": d1, "count": 1},
        {"habitId": "h1", "date": d2, "count": 1},
        {"habitId": "h1", "date": d3, "count": 1},
    ]

    streak = calculate_streak("h1", progress_data=progress, habit=habit, as_of_date=today)
    assert streak == 3

def test_calculate_streak_missing_today(tmp_path):
    today = date.today()
    d1 = (today - timedelta(days=2)).isoformat()
    d2 = (today - timedelta(days=1)).isoformat()

    habit = Habit(id="h1", name="Exercise", frequency="daily", target_count=1, start_date=d1)
    progress = [
        {"habitId": "h1", "date": d1, "count": 1},
        {"habitId": "h1", "date": d2, "count": 1},
        # today not logged yet
    ]

    streak = calculate_streak("h1", progress_data=progress, habit=habit, as_of_date=today)
    # Since yesterday was logged, streak should be 2 (active)
    assert streak == 2

def test_calculate_streak_broken(tmp_path):
    today = date.today()
    d1 = (today - timedelta(days=5)).isoformat()
    d2 = (today - timedelta(days=4)).isoformat()
    # gap on days-3 and days-2, day-1 not logged either

    habit = Habit(id="h1", name="Exercise", frequency="daily", target_count=1, start_date=d1)
    progress = [
        {"habitId": "h1", "date": d1, "count": 1},
        {"habitId": "h1", "date": d2, "count": 1},
    ]

    streak = calculate_streak("h1", progress_data=progress, habit=habit, as_of_date=today)
    assert streak == 0

def test_calculate_streak_weekly(tmp_path):
    today = date.today()
    # Test weekly streak
    habit = Habit(id="h2", name="Reading", frequency="weekly", target_count=2, start_date="2023-01-01")
    
    # We can test with specific progress records or current week
    yr, wk, _ = today.isocalendar()
    curr_week_date = today.isoformat()
    prev_week_date = (today - timedelta(weeks=1)).isoformat()

    progress = [
        {"habitId": "h2", "date": prev_week_date, "count": 2},
        {"habitId": "h2", "date": curr_week_date, "count": 2},
    ]

    streak = calculate_streak("h2", progress_data=progress, habit=habit, as_of_date=today)
    assert streak == 2

def test_calculate_all_streaks(tmp_path):
    habits_file = tmp_path / "habits.txt"
    habits_file.write_text("TestHabit, daily, 1, desc, 2023-01-01\n", encoding="utf-8")

    today = date.today().isoformat()
    progress = [{"habitId": "5ccb75f3-5942-589a-aaea-9e813d36f016", "date": today, "count": 1}]

    streaks = calculate_all_streaks(progress_data=progress, habits_file=habits_file)
    assert streaks.get("5ccb75f3-5942-589a-aaea-9e813d36f016") == 1 or streaks.get("TestHabit") == 1
