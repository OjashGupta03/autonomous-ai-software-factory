# Habit Tracker & Streak Cheer

A lightweight, robust Python system for tracking daily, weekly, and monthly habits, computing streaks, and receiving celebratory encouragement ("cheers") as you build lasting routines.

---

## Features

- **Habit Definitions**: Define habits with configurable frequencies (`daily`, `weekly`, `monthly`), target counts, descriptions, start/end dates, and unique identifiers.
- **Progress Tracking**: Record completions and counts in JSON storage with robust validation and schema support.
- **Streak Calculation**: Accurately calculate current and historical streaks across different frequencies and targets.
- **Cheer & Milestone Encouragement**: Generate motivational messages and celebrate milestone achievements (e.g. 3, 7, 14, 21, 30, 50, 100 days).
- **Secure Storage**: Safe file handling with path traversal protection and atomic writes for progress data.

---

## Project Structure & Module Purpose

```
habit_tracker/
├── schemas/
│   └── habit_and_progress.json   # JSON schema for habit definitions and progress records
├── src/
│   ├── habits.py                 # Core Habit dataclass, parsing, retrieval, and entity management
│   ├── storage.py                # Safe file loading/writing (habits.txt, progress.json) with security checks
│   ├── streak.py                 # Streak calculation engine for daily, weekly, and monthly frequencies
│   └── cheer.py                  # Motivational messaging and milestone celebration generator
├── tests/
│   ├── test_cheer.py             # Unit tests for cheer generation and milestones
│   ├── test_storage.py           # Unit tests for storage read/write and path sanitization
│   └── test_streak.py            # Unit tests for streak calculations
├── habits.txt                    # Predefined habits list file
├── progress.json                 # Progress tracking data store
└── README.md
```

### Module Breakdown

- **`src/habits.py`**: Defines the `Habit` dataclass with serialization (`to_dict`/`from_dict`) and utilities for parsing predefined habits (`habits.txt`) and querying habits by ID or name.
- **`src/storage.py`**: Handles reading and writing data files (`habits.txt`, `progress.json`). Implements path sanitization to prevent directory traversal attacks and atomic file writing for progress updates.
- **`src/streak.py`**: Contains the streak computation algorithms supporting `daily`, `weekly`, and `monthly` habits, accounting for custom target counts and missing logs.
- **`src/cheer.py`**: Provides motivational feedback (`get_cheer_message`), selecting custom encouragement based on streak length and hitting milestone thresholds (3, 7, 14, 21, 30, 50, 100 days).

---

## Installation

### Prerequisites
- Python 3.8 or higher.

### Setup
1. Clone the repository or navigate to the project directory:
   ```bash
   cd habit_tracker
   ```
2. (Optional) Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies or test runners if needed (standard library is used; `pytest` is recommended for running tests):
   ```bash
   pip install pytest
   ```

---

## Usage

### 1. Defining Habits (`habits.txt`)
Add your habits to `habits.txt` (one per line, comma-separated format: `Name, frequency, target_count, description, start_date`):
```text
# Example habits.txt
Morning Jog, daily, 1, 30 minutes of cardio, 2023-01-01
Read Book, daily, 20, Read 20 pages, 2023-01-01
Weekly Review, weekly, 1, Plan out the week
```

### 2. Python API Examples

#### Loading Habits and Checking Streaks
```python
from src.habits import get_all_habits, get_habit_by_id
from src.streak import calculate_streak
from src.storage import read_progress

# Load all habits defined in habits.txt
habits = get_all_habits()
for habit in habits:
    print(f"- {habit.name} ({habit.frequency}, target: {habit.target_count})")

# Calculate streak for a specific habit
habit = get_habit_by_id("Morning Jog")
if habit:
    streak = calculate_streak(habit.id)
    print(f"Current streak for {habit.name}: {streak} days")
```

#### Getting Cheer Messages
```python
from src.cheer import get_cheer_message

# Get a motivational cheer message for a specific habit
message = get_cheer_message(habit_identifier="Morning Jog")
print(message)
```

---

## Running Tests

Run the test suite using `pytest`:
```bash
pytest
```

---

## Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork the Repository & Create a Branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. **Write Clean Code**: Follow PEP 8 style guidelines and include type hints where appropriate.
3. **Add Tests**: Ensure new features or bug fixes are covered by unit tests under `tests/`.
4. **Run the Test Suite**: Verify all tests pass successfully (`pytest`).
5. **Submit a Pull Request**: Describe your changes clearly in the PR description.

---

## License

This project is licensed under the MIT License.
