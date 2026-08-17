"""Context Manager tests (app/orchestrator/context_manager.py)."""
from __future__ import annotations

from app.orchestrator.context_manager import (
    FileSnippet,
    TaskContextInput,
    build_task_context,
    estimate_tokens,
    extract_mentioned_paths,
)


def test_generous_budget_includes_everything_untruncated():
    ctx = build_task_context(TaskContextInput(
        task_title="Implement login UI",
        task_description="Add a login form that posts to /auth/login and handles 401 responses.",
        task_type="frontend_implementation",
        architecture_summary="React + TypeScript frontend, FastAPI backend, JWT auth over REST.",
        api_contract_excerpt="POST /auth/login -> { access_token, token_type }",
        dependency_summaries=["T3 (backend auth) completed: added POST /auth/login."],
        candidate_files=[FileSnippet(path="src/pages/Login.tsx", content="export function Login() {}\n")],
        current_issue="401 handling is missing.",
        budget_tokens=4000,
    ))
    assert ctx.truncated is False
    assert ctx.architecture_excerpt is not None
    assert ctx.current_issue == "401 handling is missing."
    assert len(ctx.files) == 1
    assert "Task:" in ctx.to_prompt()
    assert "Relevant files:" in ctx.to_prompt()


def test_tiny_budget_still_respected_and_never_drops_task_description():
    ctx = build_task_context(TaskContextInput(
        task_title="X", task_description="Y",
        task_type="bugfix",
        architecture_summary="a" * 2000,
        candidate_files=[FileSnippet(path="big.py", content="z" * 5000)],
        current_issue="issue text " * 100,
        budget_tokens=10,
    ))
    assert ctx.truncated is True
    assert ctx.task_title == "X"
    assert ctx.task_description == "Y"
    assert ctx.estimated_tokens <= 10 + 5  # small slack for the never-dropped task description itself


def test_zero_budget_still_includes_task_description():
    ctx = build_task_context(TaskContextInput(task_title="X", task_description="Y", task_type="bugfix", budget_tokens=0))
    assert ctx.to_prompt() == "Task:\nX\nY"


def test_context_never_includes_unrelated_project_history():
    # This is the behavioural contract the whole module exists to
    # enforce: nothing outside what's explicitly passed in ever leaks in.
    ctx = build_task_context(TaskContextInput(
        task_title="Implement signup form",
        task_description="Build the signup form.",
        task_type="frontend_implementation",
        budget_tokens=4000,
    ))
    prompt = ctx.to_prompt()
    assert "unrelated" not in prompt.lower()
    assert len(ctx.dependency_summaries) == 0
    assert len(ctx.files) == 0


def test_extract_mentioned_paths_finds_filenames():
    paths = extract_mentioned_paths("See Login.tsx and src/api/authApi.ts for context, ignore README.")
    assert "Login.tsx" in paths
    assert "src/api/authApi.ts" in paths


def test_estimate_tokens_monotonic_in_length():
    short = estimate_tokens("hello")
    long = estimate_tokens("hello " * 1000)
    assert long > short
    assert estimate_tokens("") == 0
