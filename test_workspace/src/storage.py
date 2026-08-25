import os
import json
from pathlib import Path
from typing import List, Dict, Any, Union

def sanitize_path(base_dir: Union[str, Path], file_path: Union[str, Path]) -> Path:
    """
    Safely resolve a file path within a base directory to prevent directory traversal attacks.
    """
    base = Path(base_dir).resolve()
    target = (base / file_path).resolve()
    if not target.is_relative_to(base):
        raise ValueError(f"Path traversal detected: {file_path} is outside of {base_dir}")
    return target

def load_habits(file_path: Union[str, Path] = "habits.txt") -> List[Dict[str, Any]]:
    """
    Load habits from a text file (habits.txt).
    Each line represents a habit definition or name. Empty lines and lines starting with '#' are ignored.
    Depending on format, lines can be simple habit names or structured (e.g. name, frequency, etc.).
    Returns a list of habit dicts.
    """
    path = Path(file_path)
    if not path.exists():
        return []
    
    habits = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            
            # Support comma-separated or simple text lines
            parts = [p.strip() for p in stripped.split(",")]
            habit_data = {
                "id": str(line_num), # or generated UUID / fallback
                "name": parts[0],
                "frequency": parts[1].lower() if len(parts) > 1 and parts[1].lower() in ["daily", "weekly", "monthly"] else "daily",
                "targetCount": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1,
                "description": parts[3] if len(parts) > 3 else "",
                "startDate": parts[4] if len(parts) > 4 else "",
                "createdAt": "",
                "updatedAt": ""
            }
            habits.append(habit_data)
    return habits

def read_progress(file_path: Union[str, Path] = "progress.json") -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Read progress data from progress.json.
    Returns parsed JSON data (dict or list), or empty dict/list if file doesn't exist or is invalid.
    """
    path = Path(file_path)
    if not path.exists():
        return {}
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, IOError):
        return {}

def write_progress(data: Union[List[Dict[str, Any]], Dict[str, Any]], file_path: Union[str, Path] = "progress.json") -> None:
    """
    Write progress data to progress.json safely (using atomic write / temporary file if needed, or direct write).
    """
    path = Path(file_path)
    # Ensure parent directory exists
    if path.parent and str(path.parent) != ".":
        path.parent.mkdir(parents=True, exist_ok=True)
    
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_path.replace(path)
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise e
