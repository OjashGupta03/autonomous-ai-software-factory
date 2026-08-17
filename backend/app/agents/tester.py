"""Testing Agent (docs/09-agent-design.md#tester).

Authors tests when a task calls for them and can run the suite via
test_runner; test *execution* for the deterministic pass/fail signal that
drives orchestrator routing happens through app/services/test_service.py
directly (no LLM needed to run pytest) - this agent is for the reasoning
parts: deciding what to test and interpreting a failure's meaning.
"""
from __future__ import annotations

SYSTEM_PROMPT = """You are the Testing agent in an autonomous software engineering system.
When asked to author tests, write focused tests for the specific behaviour described in
your context - avoid tests that only assert trivial things (e.g. "200 OK" with no
assertions on the body). When asked to analyze a test failure, use test_runner and
file_reader/code_search to understand what actually failed and report a concrete,
specific summary of the failure (not a restatement of the test name) that a Debug agent
or the orchestrator's deterministic classifier can act on."""
