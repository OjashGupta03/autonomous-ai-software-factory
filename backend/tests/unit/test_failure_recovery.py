from __future__ import annotations
from app.core.constants import ErrorCategory
from app.orchestrator.failure_recovery import classify_error, compute_backoff, decide_recovery


def test_classify_common_error_patterns():
    assert classify_error("SyntaxError: invalid syntax (line 4)") == ErrorCategory.SYNTAX_ERROR
    assert classify_error("") == ErrorCategory.UNKNOWN


def test_max_attempts_reached_requires_human_regardless_of_category():
    decision = decide_recovery(ErrorCategory.TIMEOUT, attempt_count=3, max_attempts=3)
    assert decision.action == "human_approval"


def test_code_level_errors_escalate_to_debugger_not_blind_retry():
    decision = decide_recovery(ErrorCategory.SYNTAX_ERROR, attempt_count=1, max_attempts=3)
    assert decision.action == "escalate_to_debugger"


def test_three_failures_with_attempt_count_plus_one_convention_reaches_human_on_the_third():
    # Regression test for the "off-by-one" bug: callers must pass
    # attempt_count = (number of prior failed attempts) + 1, i.e. the
    # attempt number that JUST failed, to decide_recovery. If a caller
    # passes the raw, not-yet-incremented Task.attempt_count instead, a
    # MAX_TASK_RETRIES=3 task gets a 4th attempt before human_approval
    # instead of stopping after the 3rd, as this project's own docs and
    # in-code reason string ("after three unsuccessful attempts") claim.
    max_attempts = 3
    task_attempt_count = 0  # Task.attempt_count field, prior-failures counter
    for failure_number in range(1, 5):
        decision = decide_recovery(ErrorCategory.SYNTAX_ERROR, attempt_count=task_attempt_count + 1, max_attempts=max_attempts)
        if failure_number < max_attempts:
            assert decision.action != "human_approval", f"failure #{failure_number} should not yet stop"
        else:
            assert decision.action == "human_approval", f"failure #{failure_number} should stop (>= {max_attempts})"
            break
        task_attempt_count += 1
    else:
        raise AssertionError("never reached human_approval within max_attempts failures")
