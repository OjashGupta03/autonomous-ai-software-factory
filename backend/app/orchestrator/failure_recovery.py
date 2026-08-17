"""
Failure recovery policy (docs/12-failure-recovery.md).

Two deterministic decisions live here, both made with zero LLM calls:

1. classify_error(): turn raw stderr/output into an ErrorCategory using
   pattern matching. This is intentionally simple regex/substring logic -
   it does not need to be perfect, it needs to be fast, free, and good
   enough to route the *next* decision correctly.

2. decide_recovery(): given the category and how many times this task has
   already been attempted, decide whether to blindly retry, hand the task
   to the Debug Agent (diagnose-then-fix, not a blind re-roll), or stop
   and ask a human. This is what prevents the infinite-retry-loop
   anti-pattern called out in the project brief.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.core.constants import ErrorCategory

# Ordered: first pattern that matches wins, so more specific categories
# (e.g. a missing third-party package) are checked before generic ones
# (e.g. any ImportError) that would otherwise shadow them.
_CLASSIFICATION_PATTERNS: list[tuple[ErrorCategory, re.Pattern]] = [
    (ErrorCategory.DEPENDENCY_MISSING, re.compile(r"no matching distribution|could not find a version|ModuleNotFoundError.*(?:'|\")(?!app\.)", re.I)),
    (ErrorCategory.TIMEOUT, re.compile(r"timed?\s?out|timeout", re.I)),
    (ErrorCategory.RESOURCE_LIMIT, re.compile(r"out of memory|oom|memoryerror|killed.*signal|resource.*limit", re.I)),
    (ErrorCategory.SYNTAX_ERROR, re.compile(r"SyntaxError|IndentationError|unexpected indent|invalid syntax", re.I)),
    (ErrorCategory.IMPORT_ERROR, re.compile(r"ImportError|ModuleNotFoundError", re.I)),
    (ErrorCategory.TYPE_ERROR, re.compile(r"TypeError", re.I)),
    (ErrorCategory.ASSERTION_FAILURE, re.compile(r"AssertionError|assert .* ==|FAILED.*assert", re.I)),
]


def classify_error(message: str) -> ErrorCategory:
    if not message:
        return ErrorCategory.UNKNOWN
    for category, pattern in _CLASSIFICATION_PATTERNS:
        if pattern.search(message):
            return category
    return ErrorCategory.UNKNOWN


_TRANSIENT_RETRY_CATEGORIES = {ErrorCategory.TIMEOUT, ErrorCategory.RESOURCE_LIMIT}
_ONE_SHOT_RETRY_CATEGORIES = {ErrorCategory.DEPENDENCY_MISSING}

RecoveryAction = Literal["retry", "escalate_to_debugger", "human_approval"]


@dataclass(frozen=True)
class RecoveryDecision:
    action: RecoveryAction
    reason: str
    backoff_seconds: float = 0.0


def compute_backoff(attempt_number: int, base_seconds: float, max_seconds: float) -> float:
    """Exponential backoff: base * 2^(attempt-1), capped. attempt_number
    is 1-indexed (the attempt about to be made)."""
    delay = base_seconds * (2 ** max(0, attempt_number - 1))
    return min(delay, max_seconds)


def decide_recovery(
    category: ErrorCategory,
    attempt_count: int,
    max_attempts: int,
    backoff_base_seconds: float = 2.0,
    backoff_max_seconds: float = 60.0,
) -> RecoveryDecision:
    """`attempt_count` = number of attempts already made (the one that
    just failed). Returns what should happen next."""
    if attempt_count >= max_attempts:
        return RecoveryDecision(
            action="human_approval",
            reason=(
                f"Task has failed {attempt_count} time(s), reaching max_attempts={max_attempts}. "
                "Stopping autonomous execution and requesting human review "
                "(spec: 'after three unsuccessful attempts, stop and ask the user')."
            ),
        )

    next_attempt = attempt_count + 1
    backoff = compute_backoff(next_attempt, backoff_base_seconds, backoff_max_seconds)

    if category in _TRANSIENT_RETRY_CATEGORIES:
        return RecoveryDecision(
            action="retry",
            reason=f"'{category.value}' is treated as transient - retrying with backoff.",
            backoff_seconds=backoff,
        )

    if category in _ONE_SHOT_RETRY_CATEGORIES and attempt_count == 1:
        return RecoveryDecision(
            action="retry",
            reason=f"'{category.value}' on first attempt may be transient - retrying once before escalating.",
            backoff_seconds=backoff,
        )

    return RecoveryDecision(
        action="escalate_to_debugger",
        reason=(
            f"'{category.value}' requires diagnosis, not a blind retry - "
            "routing to the Debug Agent so the fix is informed by the actual failure."
        ),
    )
