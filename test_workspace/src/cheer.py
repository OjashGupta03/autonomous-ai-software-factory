"""
src/cheer.py

Produces encouraging messages when streaks continue or are achieved,
integrating with habits, progress tracking, and streak calculation.
"""

import random
from datetime import date
from typing import List, Dict, Any, Optional, Union
from pathlib import Path

from src.habits import Habit, get_all_habits, get_habit_by_id
from src.streak import calculate_streak, calculate_all_streaks
from src.storage import read_progress


# Milestone / streak length thresholds that trigger special celebratory messages
MILESTONE_THRESHOLDS = {
    3: [
        "🔥 3-day streak! You're building solid momentum!",
        "Three days in a row! The habit train is leaving the station! 🚂",
        "3 days down! Consistency is your superpower."
    ],
    7: [
        "🎉 One full week streak! Incredible dedication!",
        "7 days straight! You've officially completed a full week of consistency!",
        "A 7-day streak! Look at you go, habit master! 🌟"
    ],
    14: [
        "🚀 2-week streak! Habits are becoming second nature!",
        "Fourteen days in a row! Your commitment is inspiring!",
        "2 weeks strong! You're unstoppable! 💪"
    ],
    21: [
        "🏆 21-day streak! The classic milestone of habit formation!",
        "Three weeks straight! You've built a powerful routine!",
        "21 days! This is where lasting transformation happens. 🌟"
    ],
    30: [
        "👑 30-day milestone! A whole month of unwavering dedication!",
        "One full month streak! Absolute legend status unlocked! 🏆",
        "30 days! You proved you can stick to your goals long-term!"
    ],
    50: [
        "⚡ 50-day streak! Half a century of winning days!",
        "50 days straight! Your discipline is breathtaking!",
        "50-day milestone reached! You are a titan of habit tracking! 🏅"
    ],
    100: [
        "💯 ONE HUNDRED DAY STREAK! Legendary achievement!",
        "100 days of consistency! You are an absolute inspiration! 👑✨",
        "Century mark reached! 100 days straight of showing up for yourself!"
    ]
}

GENERAL_CONTINUED_MESSAGES = [
    "🔥 Streak continued! Keep up the fantastic work!",
    "Another day, another victory! Your streak lives on! ✨",
    "Consistency pays off. Great job keeping your streak alive!",
    "You showed up again today! Streak sustained! 🚀",
    "Way to keep the momentum rolling!",
    "Every step counts, and your streak keeps growing! 🌟",
    "Incredible job staying on track today!"
]

NEW_STREAK_MESSAGES = [
    "🌱 New streak started! Plant the seeds of success today!",
    "Day one of your new streak! You've got this! 💪",
    "The journey of a thousand miles begins with a single step. Great start!",
    "New habit spark ignited! Let's keep this going! ✨"
]

ZERO_STREAK_MESSAGES = [
    "Ready to start a new streak? Today is a great day to begin! 🌅",
    "Every day is a fresh start. Jump back in whenever you're ready! 💪",
    "No active streak right now, but the next victory is just one action away!"
]


def get_cheer_message(
    habit_identifier: Optional[str] = None,
    streak: Optional[int] = None,
    habit: Optional[Habit] = None,
    progress_data: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None,
    progress_file: Union[str, Path] = "progress.json",
    habits_file: Union[str, Path] = "habits.txt"
) -> str:
    """
    Generate an encouraging cheer message based on a habit's current streak.

    - If habit_identifier or habit is provided, computes or checks streak for that habit.
    - If specific milestone streaks are reached (e.g., 3, 7, 14, 21, 30, 50, 100), returns milestone praise.
    - If streak > 1, returns continued streak encouragement.
    - If streak == 1, returns new streak encouragement.
    - If streak == 0, returns restart/encouragement message.
    - If no habit is specified, gives general encouragement or picks a random active habit's status.
    """
    if habit is None and habit_identifier is not None:
        habit = get_habit_by_id(habit_identifier, habits_file=habits_file)

    if habit is not None:
        if streak is None:
            streak = calculate_streak(
                habit_id=habit.id,
                progress_data=progress_data,
                progress_file=progress_file,
                habit=habit
            )
        habit_name = habit.name
    else:
        if habit_identifier is not None:
            habit_name = habit_identifier
        else:
            habit_name = "Your habit"

        if streak is None:
            # If no specific habit, check all habits or default to 0/general
            all_habits = get_all_habits(habits_file=habits_file)
            if all_habits:
                # pick one or check max streak
                streaks = calculate_all_streaks(progress_data=progress_data, progress_file=progress_file, habits_file=habits_file)
                if streaks:
                    best_hid = max(streaks, key=streaks.get)
                    streak = streaks[best_hid]
                    h_obj = get_habit_by_id(best_hid, habits_file=habits_file)
                    if h_obj:
                        habit_name = h_obj.name
                else:
                    streak = 0
            else:
                streak = 0

    # Select message category
    message = ""
    if streak in MILESTONE_THRESHOLDS:
        message = random.choice(MILESTONE_THRESHOLDS[streak])
    elif streak > 1:
        message = random.choice(GENERAL_CONTINUED_MESSAGES)
    elif streak == 1:
        message = random.choice(NEW_STREAK_MESSAGES)
    else:
        message = random.choice(ZERO_STREAK_MESSAGES)

    if habit_name and habit_name != "Your habit":
        return f"[{habit_name} - Streak: {streak}] {message}"
    else:
        return f"[Streak: {streak}] {message}"


def cheer_all(
    progress_data: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None,
    progress_file: Union[str, Path] = "progress.json",
    habits_file: Union[str, Path] = "habits.txt"
) -> List[str]:
    """
    Generate cheer messages for all active habits based on their current streaks.
    """
    habits = get_all_habits(habits_file=habits_file)
    if not habits:
        return [get_cheer_message(streak=0)]

    streaks = calculate_all_streaks(progress_data=progress_data, progress_file=progress_file, habits_file=habits_file)
    messages = []
    for habit in habits:
        streak = streaks.get(habit.id, 0)
        msg = get_cheer_message(habit=habit, streak=streak)
        messages.append(msg)
    return messages
