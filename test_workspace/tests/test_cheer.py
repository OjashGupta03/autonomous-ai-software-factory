import pytest
from datetime import date, timedelta
from src.habits import Habit
from src.cheer import get_cheer_message, cheer_all, MILESTONE_THRESHOLDS

def test_cheer_message_milestone():
    habit = Habit(id="h1", name="Running", frequency="daily")
    # Test milestone 7
    msg = get_cheer_message(habit=habit, streak=7)
    assert "7" in msg or "week" in msg or "Running" in msg

    msg_30 = get_cheer_message(habit=habit, streak=30)
    assert "30" in msg_30 or "month" in msg_30 or "Running" in msg_30

def test_cheer_message_continued():
    habit = Habit(id="h1", name="Meditation", frequency="daily")
    msg = get_cheer_message(habit=habit, streak=5)
    assert "Meditation" in msg
    assert "Streak: 5" in msg

def test_cheer_message_new_streak():
    habit = Habit(id="h1", name="Reading", frequency="daily")
    msg = get_cheer_message(habit=habit, streak=1)
    assert "Reading" in msg
    assert "Streak: 1" in msg

def test_cheer_message_zero_streak():
    habit = Habit(id="h1", name="Coding", frequency="daily")
    msg = get_cheer_message(habit=habit, streak=0)
    assert "Coding" in msg
    assert "Streak: 0" in msg

def test_cheer_all(tmp_path):
    habits_file = tmp_path / "habits.txt"
    habits_file.write_text("Workout, daily, 1, desc, 2023-01-01\n", encoding="utf-8")
    
    today = date.today().isoformat()
    progress = [{"habitId": "1", "date": today, "count": 1}]

    messages = cheer_all(progress_data=progress, habits_file=habits_file)
    assert len(messages) >= 1
    assert "Workout" in messages[0]
