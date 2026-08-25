from dataclasses import dataclass, field
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
import uuid

from src.storage import load_habits, read_progress, write_progress

@dataclass
class Habit:
    """
    Represents a Habit definition corresponding to HabitDefinition schema.
    """
    id: str
    name: str
    frequency: str = "daily"  # "daily", "weekly", "monthly"
    target_count: int = 1
    description: str = ""
    start_date: str = field(default_factory=lambda: date.today().isoformat())
    end_date: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert habit object to a dictionary matching storage/schema expectations."""
        d = {
            "id": self.id,
            "name": self.name,
            "frequency": self.frequency,
            "targetCount": self.target_count,
            "description": self.description,
            "startDate": self.start_date,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }
        if self.end_date is not None:
            d["endDate"] = self.end_date
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Habit":
        """Create a Habit instance from a dictionary representation."""
        return cls(
            id=data.get("id") or str(uuid.uuid4()),
            name=data.get("name", "Unnamed Habit"),
            frequency=data.get("frequency", "daily"),
            target_count=data.get("targetCount", data.get("target_count", 1)),
            description=data.get("description", ""),
            start_date=data.get("startDate", data.get("start_date", date.today().isoformat())),
            end_date=data.get("endDate", data.get("end_date")),
            created_at=data.get("createdAt", data.get("created_at", datetime.now(timezone.utc).isoformat())),
            updated_at=data.get("updatedAt", data.get("updated_at", datetime.now(timezone.utc).isoformat())),
        )


def parse_predefined_habits(file_path: Union[str, Path] = "habits.txt") -> List[Habit]:
    """
    Parse predefined list of habits from habits.txt (or given file path) using src.storage.load_habits
    and return a list of Habit objects.
    """
    raw_habits = load_habits(file_path)
    habits = []
    for raw in raw_habits:
        hid = raw.get("id")
        if not hid or not _is_valid_uuid(str(hid)):
            hid = str(uuid.uuid5(uuid.NAMESPACE_DNS, raw.get("name", "habit")))
        
        now = datetime.now(timezone.utc).isoformat()
        habit = Habit(
            id=hid,
            name=raw.get("name", ""),
            frequency=raw.get("frequency", "daily"),
            target_count=raw.get("targetCount", 1),
            description=raw.get("description", ""),
            start_date=raw.get("startDate") or date.today().isoformat(),
            end_date=raw.get("endDate"),
            created_at=raw.get("createdAt") or now,
            updated_at=raw.get("updatedAt") or now,
        )
        habits.append(habit)
    return habits


def get_all_habits(habits_file: Union[str, Path] = "habits.txt") -> List[Habit]:
    """
    Retrieve all habits. Parses from habits.txt.
    """
    return parse_predefined_habits(habits_file)


def get_habit_by_id(habit_id: str, habits_file: Union[str, Path] = "habits.txt") -> Optional[Habit]:
    """
    Find a specific habit by its ID or name substring.
    """
    habits = get_all_habits(habits_file)
    for habit in habits:
        if habit.id == habit_id or habit.name.lower() == habit_id.lower():
            return habit
    # Also check prefix match on ID or partial name match if exact match fails
    for habit in habits:
        if habit.id.startswith(habit_id) or habit_id.lower() in habit.name.lower():
            return habit
    return None


def calculate_streak(
    habit_id: str, 
    progress_data: Union[List[Dict[str, Any]], Dict[str, Any], None] = None, 
    progress_file: Union[str, Path] = "progress.json"
) -> int:
    """
    Calculate the current completion streak for a given habit based on progress records.
    """
    if progress_data is None:
        progress_data = read_progress(progress_file)

    records = []
    if isinstance(progress_data, list):
        records = [r for r in progress_data if r.get("habitId") == habit_id]
    elif isinstance(progress_data, dict):
        if habit_id in progress_data:
            val = progress_data[habit_id]
            if isinstance(val, list):
                records = val
            elif isinstance(val, dict):
                records = [{"date": k, "count": v} for k, v in val.items()]
        else:
            for k, v in progress_data.items():
                if isinstance(v, dict) and "habitId" in v and v.get("habitId") == habit_id:
                    records.append(v)
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict) and item.get("habitId") == habit_id:
                            records.append(item)

    if not records:
        return 0

    completed_dates = set()
    for rec in records:
        d_str = rec.get("date")
        cnt = rec.get("count", 0)
        if d_str and cnt > 0:
            completed_dates.add(d_str)

    if not completed_dates:
        return 0

    today = date.today()
    current_date = today
    streak = 0

    date_str = current_date.isoformat()
    if date_str not in completed_dates:
        current_date = today - timedelta(days=1)
        date_str = current_date.isoformat()
        if date_str not in completed_dates:
            return 0

    while True:
        d_str = current_date.isoformat()
        if d_str in completed_dates:
            streak += 1
            current_date -= timedelta(days=1)
        else:
            break

    return streak


def _is_valid_uuid(val: str) -> bool:
    try:
        uuid.UUID(val)
        return True
    except ValueError:
        return False
