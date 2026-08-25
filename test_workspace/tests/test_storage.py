import pytest
from pathlib import Path
from src.storage import (
    sanitize_path,
    load_habits,
    read_progress,
    write_progress,
)

def test_sanitize_path(tmp_path):
    # Valid path inside base_dir
    resolved = sanitize_path(tmp_path, "sub/file.txt")
    assert resolved == (tmp_path / "sub" / "file.txt").resolve()

    # Path traversal outside base_dir should raise ValueError
    with pytest.raises(ValueError, match="Path traversal detected"):
        sanitize_path(tmp_path, "../outside.txt")

def test_load_habits_non_existent(tmp_path):
    habits_file = tmp_path / "non_existent.txt"
    habits = load_habits(habits_file)
    assert habits == []

def test_load_habits_valid_file(tmp_path):
    habits_file = tmp_path / "habits.txt"
    habits_file.write_text(
        "# This is a comment\n"
        "\n"
        "Exercise, daily, 1, Morning workout, 2023-01-01\n"
        "Meditation, weekly, 3\n"
        "Read Book\n",
        encoding="utf-8"
    )

    habits = load_habits(habits_file)
    assert len(habits) == 3

    # Habit 1: Fully structured
    assert habits[0]["name"] == "Exercise"
    assert habits[0]["frequency"] == "daily"
    assert habits[0]["targetCount"] == 1
    assert habits[0]["description"] == "Morning workout"
    assert habits[0]["startDate"] == "2023-01-01"

    # Habit 2: Partially structured
    assert habits[1]["name"] == "Meditation"
    assert habits[1]["frequency"] == "weekly"
    assert habits[1]["targetCount"] == 3
    assert habits[1]["description"] == ""

    # Habit 3: Simple name
    assert habits[2]["name"] == "Read Book"
    assert habits[2]["frequency"] == "daily"
    assert habits[2]["targetCount"] == 1

def test_read_progress_non_existent(tmp_path):
    progress_file = tmp_path / "progress.json"
    data = read_progress(progress_file)
    assert data == {}

def test_read_progress_empty_file(tmp_path):
    progress_file = tmp_path / "progress.json"
    progress_file.write_text("   ", encoding="utf-8")
    data = read_progress(progress_file)
    assert data == {}

def test_read_progress_invalid_json(tmp_path):
    progress_file = tmp_path / "progress.json"
    progress_file.write_text("invalid json content {", encoding="utf-8")
    data = read_progress(progress_file)
    assert data == {}

def test_save_and_read_progress(tmp_path):
    progress_file = tmp_path / "progress.json"
    progress_data = {
        "habitId": "123e4567-e89b-12d3-a456-426614174000",
        "date": "2023-10-01",
        "count": 2,
        "notes": "Good progress"
    }

    write_progress(progress_data, progress_file)
    read_data = read_progress(progress_file)
    assert read_data == progress_data

def test_save_progress_creates_parent_dirs(tmp_path):
    progress_file = tmp_path / "nested" / "dir" / "progress.json"
    progress_data = [{"habitId": "abc", "count": 1}]

    write_progress(progress_data, progress_file)
    assert progress_file.exists()
    assert read_progress(progress_file) == progress_data
