from pathlib import Path
from datetime import date, timedelta
from typing import List, Dict, Any, Union, Optional
from src.storage import read_progress
from src.habits import get_habit_by_id, get_all_habits, Habit

def _parse_records_for_habit(habit_id: str, progress_data: Union[List[Dict[str, Any]], Dict[str, Any], None] = None, progress_file: Union[str, Path] = "progress.json") -> List[Dict[str, Any]]:
    """
    Helper to extract and normalize progress records for a given habit_id from progress data or storage.
    Supports list of record dicts, dict mapping habit_id to lists/dicts, or dict of records.
    """
    if progress_data is None:
        progress_data = read_progress(progress_file)

    records = []
    if isinstance(progress_data, list):
        for r in progress_data:
            if isinstance(r, dict) and (r.get("habitId") == habit_id or r.get("habit_id") == habit_id):
                records.append(r)
    elif isinstance(progress_data, dict):
        if habit_id in progress_data:
            val = progress_data[habit_id]
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        # Ensure habitId is set
                        if "habitId" not in item and "habit_id" not in item:
                            item = {**item, "habitId": habit_id}
                        records.append(item)
            elif isinstance(val, dict):
                # e.g., {"2023-01-01": 1} or full record dicts
                for k, v in val.items():
                    if isinstance(v, dict):
                        rec = dict(v)
                        if "date" not in rec:
                            rec["date"] = k
                        if "habitId" not in rec and "habit_id" not in rec:
                            rec["habitId"] = habit_id
                        records.append(rec)
                    else:
                        records.append({"habitId": habit_id, "date": k, "count": v})
        else:
            for k, v in progress_data.items():
                if isinstance(v, dict):
                    if v.get("habitId") == habit_id or v.get("habit_id") == habit_id:
                        records.append(v)
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict) and (item.get("habitId") == habit_id or item.get("habit_id") == habit_id):
                            records.append(item)
    return records


def calculate_streak(
    habit_id: str,
    progress_data: Union[List[Dict[str, Any]], Dict[str, Any], None] = None,
    progress_file: Union[str, Path] = "progress.json",
    habit: Optional[Habit] = None,
    as_of_date: Optional[date] = None
) -> int:
    """
    Calculate the current completion streak for a given habit based on progress records and frequency.
    
    Supports:
    - Frequency: daily, weekly, monthly.
    - Target count per frequency period (default 1).
    - Date handling and consecutive period matching.
    """
    if habit is None:
        habit = get_habit_by_id(habit_id)
    
    frequency = "daily"
    target_count = 1
    start_date_str = None
    if habit:
        frequency = habit.frequency.lower()
        target_count = habit.target_count
        start_date_str = habit.start_date

    records = _parse_records_for_habit(habit_id, progress_data, progress_file)
    if not records:
        return 0

    if as_of_date is None:
        as_of_date = date.today()

    if frequency == "daily":
        # Map date -> total count
        counts_by_date: Dict[str, int] = {}
        for rec in records:
            d_str = rec.get("date")
            cnt = rec.get("count", 0)
            if d_str:
                counts_by_date[d_str] = counts_by_date.get(d_str, 0) + cnt

        # Check if today is completed; if not, check if yesterday was completed to start streak,
        # or if today has 0 count and yesterday is checked, streak can be active from yesterday.
        # Standard convention:
        # If today's count >= target_count, streak includes today and goes backwards.
        # If today's count < target_count, check yesterday. If yesterday completed, streak is as of yesterday (so we don't break active streak just because today hasn't been logged yet). If yesterday not completed, streak is 0.
        
        check_date = as_of_date
        today_str = as_of_date.isoformat()
        today_count = counts_by_date.get(today_str, 0)

        if today_count < target_count:
            yesterday = as_of_date - timedelta(days=1)
            yesterday_str = yesterday.isoformat()
            if counts_by_date.get(yesterday_str, 0) >= target_count:
                check_date = yesterday
            else:
                # If neither today nor yesterday meets target, check if there are any records at all, or return 0
                # Wait, if today is not met and yesterday is not met, but today is day 1 and habit started today?
                if today_count > 0 and start_date_str == today_str:
                    return 1 # partial today
                return 0

        streak = 0
        curr = check_date
        while True:
            curr_str = curr.isoformat()
            if start_date_str and curr_str < start_date_str:
                break
            cnt = counts_by_date.get(curr_str, 0)
            if cnt >= target_count:
                streak += 1
                curr -= timedelta(days=1)
            else:
                break
        return streak

    elif frequency == "weekly":
        # Weekly streaks: periods defined by ISO weeks or week intervals.
        # Let's map (year, week_number) -> total count
        counts_by_week: Dict[tuple, int] = {}
        for rec in records:
            d_str = rec.get("date")
            cnt = rec.get("count", 0)
            if d_str:
                try:
                    d = date.fromisoformat(d_str)
                    yr, wk, _ = d.isocalendar()
                    counts_by_week[(yr, wk)] = counts_by_week.get((yr, wk), 0) + cnt
                except ValueError:
                    continue

        current_yr, current_wk, _ = as_of_date.isocalendar()
        check_wk_tuple = (current_yr, current_wk)
        
        if counts_by_week.get(check_wk_tuple, 0) < target_count:
            # Check previous week
            prev_date = as_of_date - timedelta(weeks=1)
            prev_yr, prev_wk, _ = prev_date.isocalendar()
            if counts_by_week.get((prev_yr, prev_wk), 0) >= target_count:
                check_wk_tuple = (prev_yr, prev_wk)
                current_date_ref = prev_date
            else:
                if counts_by_week.get(check_wk_tuple, 0) > 0:
                    return 1
                return 0
        else:
            current_date_ref = as_of_date

        streak = 0
        curr_date = current_date_ref
        while True:
            yr, wk, _ = curr_date.isocalendar()
            if start_date_str:
                try:
                    start_d = date.fromisoformat(start_date_str)
                    start_yr, start_wk, _ = start_d.isocalendar()
                    if (yr, wk) < (start_yr, start_wk):
                        break
                except ValueError:
                    pass

            if counts_by_week.get((yr, wk), 0) >= target_count:
                streak += 1
                curr_date -= timedelta(weeks=1)
            else:
                break
        return streak

    elif frequency == "monthly":
        # Monthly streaks: (year, month) -> total count
        counts_by_month: Dict[tuple, int] = {}
        for rec in records:
            d_str = rec.get("date")
            cnt = rec.get("count", 0)
            if d_str:
                try:
                    d = date.fromisoformat(d_str)
                    counts_by_month[(d.year, d.month)] = counts_by_month.get((d.year, d.month), 0) + cnt
                except ValueError:
                    continue

        curr_yr, curr_mo = as_of_date.year, as_of_date.month
        check_mo_tuple = (curr_yr, curr_mo)

        if counts_by_month.get(check_mo_tuple, 0) < target_count:
            # Check previous month
            if curr_mo == 1:
                prev_yr, prev_mo = curr_yr - 1, 12
            else:
                prev_yr, prev_mo = curr_yr, curr_mo - 1
            if counts_by_month.get((prev_yr, prev_mo), 0) >= target_count:
                check_mo_tuple = (prev_yr, prev_mo)
            else:
                if counts_by_month.get(check_mo_tuple, 0) > 0:
                    return 1
                return 0

        streak = 0
        y, m = check_mo_tuple
        while True:
            if start_date_str:
                try:
                    start_d = date.fromisoformat(start_date_str)
                    if (y, m) < (start_d.year, start_d.month):
                        break
                except ValueError:
                    pass

            if counts_by_month.get((y, m), 0) >= target_count:
                streak += 1
                if m == 1:
                    y, m = y - 1, 12
                else:
                    m -= 1
            else:
                break
        return streak

    return 0


def calculate_all_streaks(
    progress_data: Union[List[Dict[str, Any]], Dict[str, Any], None] = None,
    progress_file: Union[str, Path] = "progress.json",
    habits_file: Union[str, Path] = "habits.txt",
    as_of_date: Optional[date] = None
) -> Dict[str, int]:
    """
    Calculate current streaks for all habits.
    Returns a dictionary mapping habit_id (or habit name if id not present) to streak count.
    """
    habits = get_all_habits(habits_file)
    streaks = {}
    for habit in habits:
        s = calculate_streak(habit.id, progress_data=progress_data, progress_file=progress_file, habit=habit, as_of_date=as_of_date)
        streaks[habit.id] = s
        # Also store by name for convenience if needed
        streaks[habit.name] = s
    return streaks
