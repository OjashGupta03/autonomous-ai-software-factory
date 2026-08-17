"""Failure classification + retry/escalation policy tests."""
from __future__ import annotations

from app.core.constants import ErrorCategory
from app.orchestrator.failure_recovery import classify_error, compute_backoff, decide_recovery


def test_classify_common_error_patterns():
    cases = {
        "SyntaxError: invalid syntax (line 4)": ErrorCategory.SYNTAX_ERROR,
        "ModuleNotFoundError: No module named 'requests'": ErrorCategory.DEPENDENCY_MISSING,
        "TimeoutError: command timed out after 60s": ErrorCategory.TIMEOUT,
        "AssertionError: assert 1 == 2": ErrorCategory.ASSERTION_FAILURE,
        "TypeError: unsupported operand type(s)": ErrorCategory.TYPE_ERROR,
        "totally unrecognized garbage": ErrorCategory.UNKNOWN,
        "": ErrorCategory.UNKNOWN,
    }
    for message, expected in cases.items():
        assert classify_error(message) == expected, f"{message!r} -> expected {expected}"


def test_transient_categories_retry_with_backoff():
    decision = decide_recovery(ErrorCategory.TIMEOUT, attempt_count=1, max_attempts=3)
    assert decision.action == "retry"
    assert decision.backoff_seconds > 0


def test_code_level_errors_escalate_to_debugger_not_blind_retry():
    # This is the core anti-infinite-retry-loop guarantee: a syntax error
    # must not just be retried identically - it needs diagnosis.
    decision = decide_recovery(ErrorCategory.SYNTAX_ERROR, attempt_count=1, max_attempts=3)
    assert decision.action == "escalate_to_debugger"


def test_dependency_missing_retries_once_then_escalates():
    first = decide_recovery(ErrorCategory.DEPENDENCY_MISSING, attempt_count=1, max_attempts=3)
    assert first.action == "retry"

    second = decide_recovery(ErrorCategory.DEPENDENCY_MISSING, attempt_count=2, max_attempts=3)
    assert second.action == "escalate_to_debugger"


def test_max_attempts_reached_requires_human_regardless_of_category():
    decision = decide_recovery(ErrorCategory.TIMEOUT, attempt_count=3, max_attempts=3)
    assert decision.action == "human_approval"
    decision2 = decide_recovery(ErrorCategory.SYNTAX_ERROR, attempt_count=5, max_attempts=3)
    assert decision2.action == "human_approval"


def test_backoff_grows_exponentially_and_is_capped():
    values = [compute_backoff(n, base_seconds=2.0, max_seconds=60.0) for n in range(1, 8)]
    assert values == sorted(values)  # non-decreasing
    assert values[0] == 2.0
    assert values[1] == 4.0
    assert values[-1] <= 60.0
    assert max(values) == 60.0  # eventually hits the cap given enough attempts
