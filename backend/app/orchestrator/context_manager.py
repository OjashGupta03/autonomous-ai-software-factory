"""
Context Manager - the core token-saving mechanism (docs/06-context-engineering.md).

The rule this module enforces: an agent receives the task at hand, a short
architecture excerpt, references to what its dependencies produced, the
handful of files actually relevant to *this* task, and (if this is a
retry) the specific error it needs to fix. It never receives the full
project history, other agents' conversations, or unrelated files.

Everything here is pure / synchronous and DB-agnostic: callers (services,
orchestrator nodes) fetch rows and pass plain data in, this module never
issues a query itself. That keeps it trivially unit-testable
(backend/tests/unit/test_context_manager.py) and reusable outside a
request/task context (e.g. from a CLI or a notebook).

Budget discipline: the ONLY thing this function guarantees is never
dropped is the task title + description - that is the minimum viable ask
for an agent to do anything useful. Every other section (architecture,
files, dependency summaries, contract, current issue) is included only if
it fits in whatever budget remains, in priority order. If the caller
passes a budget smaller than the task description itself, `truncated`
will be True and most sections will be empty - that is correct behaviour,
not a bug: it means the configured budget is genuinely too small for this
task, and callers should look at `estimated_tokens` vs `budget_tokens` in
the result rather than assume the budget was silently honoured.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

try:  # pragma: no cover - exercised implicitly by estimate_tokens tests
    import tiktoken

    _ENCODING = tiktoken.get_encoding("cl100k_base")
except Exception:  # tiktoken not installed, or no cached encoding file available
    _ENCODING = None

_PATH_PATTERN = re.compile(r"[A-Za-z0-9_\-./]+\.[A-Za-z0-9]{1,5}")

# Rough fallback used when tiktoken (and its downloaded BPE tables) are not
# available - this environment's agent runs without a live tiktoken cache
# should not silently produce a budget of 0. 4 chars/token is the
# widely-used English-text approximation; it is intentionally conservative
# (it tends to slightly *overestimate* token count for code, which is
# safer than underestimating and blowing the real budget).
_CHARS_PER_TOKEN_FALLBACK = 4

# Below this many remaining tokens, don't bother including a truncated
# file head - the snippet would be too small to be useful, so just
# reference the path instead (near-zero cost, agent can still ask a tool
# to read it in full).
_MIN_USEFUL_FILE_SNIPPET_TOKENS = 20


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    if _ENCODING is not None:
        return len(_ENCODING.encode(text))
    return max(1, len(text) // _CHARS_PER_TOKEN_FALLBACK)


def extract_mentioned_paths(text: str) -> list[str]:
    """Very deliberately dumb: a regex over filename-shaped tokens. This is
    a *cheap deterministic heuristic* the context manager uses to bias file
    selection - it is not a substitute for the dependency-graph-based
    relevance below, just a cheap first signal."""
    return sorted(set(_PATH_PATTERN.findall(text)))


@dataclass
class FileSnippet:
    path: str
    content: str
    included: bool = True
    truncated: bool = False


@dataclass
class TaskContextInput:
    """Everything the caller has fetched from the DB, handed to the
    context manager as plain data. Nothing in here is fetched by this
    module - see orchestrator/runner.py for the fetch side."""

    task_title: str
    task_description: str
    task_type: str
    architecture_summary: str | None = None
    api_contract_excerpt: str | None = None
    dependency_summaries: list[str] = field(default_factory=list)
    candidate_files: list[FileSnippet] = field(default_factory=list)
    current_issue: str | None = None
    budget_tokens: int = 4000


@dataclass
class TaskContext:
    task_title: str
    task_description: str
    architecture_excerpt: str | None
    dependency_summaries: list[str]
    files: list[FileSnippet]
    api_contract_excerpt: str | None
    current_issue: str | None
    budget_tokens: int
    estimated_tokens: int
    truncated: bool

    def to_prompt(self) -> str:
        """Renders the assembled context as the compact block agents
        actually see - deliberately close to the example in the project
        brief (section 8): task, architecture, files, contract, issue.
        No conversation transcript, no unrelated project state."""
        parts = [f"Task:\n{self.task_title}\n{self.task_description}".strip()]

        if self.architecture_excerpt:
            parts.append(f"Relevant architecture:\n{self.architecture_excerpt}")

        included_files = [f for f in self.files if f.included]
        if included_files:
            file_lines = []
            for f in included_files:
                if f.content:
                    marker = " (truncated)" if f.truncated else ""
                    file_lines.append(f"--- {f.path}{marker} ---\n{f.content}")
                else:
                    file_lines.append(f.path)
            parts.append("Relevant files:\n" + "\n".join(file_lines))

        if self.dependency_summaries:
            parts.append(
                "Prior task outputs (reference only):\n"
                + "\n".join(f"- {s}" for s in self.dependency_summaries)
            )

        if self.api_contract_excerpt:
            parts.append(f"Relevant API contract:\n{self.api_contract_excerpt}")

        if self.current_issue:
            parts.append(f"Relevant current issue:\n{self.current_issue}")

        return "\n\n".join(parts)


def build_task_context(data: TaskContextInput) -> TaskContext:
    truncated = False
    budget = data.budget_tokens
    remaining = budget

    # 1. Task description is never dropped or truncated, even in the edge
    #    case where it alone exceeds the budget - it is the minimum
    #    viable ask. Everything below only runs if there is budget left.
    task_tokens = estimate_tokens(data.task_title) + estimate_tokens(data.task_description)
    remaining -= task_tokens
    if remaining < 0:
        truncated = True

    # 2. Current issue (retry context) - next-highest priority: without
    #    it a Debug Agent is blind to what actually failed.
    current_issue = None
    if data.current_issue and remaining > 0:
        issue_tokens = estimate_tokens(data.current_issue)
        if issue_tokens <= remaining:
            current_issue = data.current_issue
            remaining -= issue_tokens
        else:
            char_budget = max(0, remaining * _CHARS_PER_TOKEN_FALLBACK)
            current_issue = data.current_issue[:char_budget] or None
            truncated = True
            remaining = 0
    elif data.current_issue:
        truncated = True

    # 3. Architecture excerpt - capped hard regardless of remaining
    #    budget. A coding agent needs "React + TypeScript, REST over
    #    /api/v1", not the full architecture document.
    architecture_excerpt = None
    if data.architecture_summary and remaining > 0:
        capped = data.architecture_summary[:600]
        if capped != data.architecture_summary:
            truncated = True
        arch_tokens = estimate_tokens(capped)
        if arch_tokens <= remaining:
            architecture_excerpt = capped
            remaining -= arch_tokens
        else:
            truncated = True
    elif data.architecture_summary:
        truncated = True

    # 4. API contract excerpt - small, high value, included if it fits.
    api_contract_excerpt = None
    if data.api_contract_excerpt and remaining > 0:
        contract_tokens = estimate_tokens(data.api_contract_excerpt)
        if contract_tokens <= remaining:
            api_contract_excerpt = data.api_contract_excerpt
            remaining -= contract_tokens
        else:
            truncated = True
    elif data.api_contract_excerpt:
        truncated = True

    # 5. Dependency summaries - one line each, cheap, high value (this is
    #    what replaces "give the agent the other agents' full transcript").
    dependency_summaries: list[str] = []
    for summary in data.dependency_summaries:
        if remaining <= 0:
            truncated = True
            break
        cost = estimate_tokens(summary)
        if cost > remaining:
            truncated = True
            break
        dependency_summaries.append(summary)
        remaining -= cost

    # 6. Files - the biggest lever. Greedy-pack smallest-first so more
    #    distinct relevant files fit before we start dropping any.
    files: list[FileSnippet] = []
    ordered_candidates = sorted(data.candidate_files, key=lambda f: len(f.content))
    for snippet in ordered_candidates:
        cost = estimate_tokens(snippet.content)
        if remaining <= 0:
            files.append(FileSnippet(path=snippet.path, content="", included=True, truncated=True))
            truncated = True
            continue
        if cost <= remaining:
            files.append(FileSnippet(path=snippet.path, content=snippet.content, included=True))
            remaining -= cost
        elif remaining >= _MIN_USEFUL_FILE_SNIPPET_TOKENS:
            # Not enough room for the whole file - include a truncated
            # head so the agent at least knows the file exists and how it
            # starts, rather than being silently unaware of it.
            char_budget = remaining * _CHARS_PER_TOKEN_FALLBACK
            files.append(
                FileSnippet(
                    path=snippet.path,
                    content=snippet.content[:char_budget],
                    included=True,
                    truncated=True,
                )
            )
            remaining = 0
            truncated = True
        else:
            # No room at all - still reference the path (near-zero cost)
            # so the agent knows it exists and can ask a tool to read it,
            # rather than being invisible.
            files.append(FileSnippet(path=snippet.path, content="", included=True, truncated=True))
            truncated = True

    estimated = estimate_tokens_of_context(
        data.task_title, data.task_description, architecture_excerpt, files,
        dependency_summaries, api_contract_excerpt, current_issue,
    )
    return TaskContext(
        task_title=data.task_title,
        task_description=data.task_description,
        architecture_excerpt=architecture_excerpt,
        dependency_summaries=dependency_summaries,
        files=files,
        api_contract_excerpt=api_contract_excerpt,
        current_issue=current_issue,
        budget_tokens=data.budget_tokens,
        estimated_tokens=estimated,
        truncated=truncated,
    )


def estimate_tokens_of_context(
    title: str,
    description: str,
    architecture_excerpt: str | None,
    files: list[FileSnippet],
    dependency_summaries: list[str],
    api_contract_excerpt: str | None,
    current_issue: str | None,
) -> int:
    total = estimate_tokens(title) + estimate_tokens(description)
    if architecture_excerpt:
        total += estimate_tokens(architecture_excerpt)
    for f in files:
        total += estimate_tokens(f.content)
    for s in dependency_summaries:
        total += estimate_tokens(s)
    if api_contract_excerpt:
        total += estimate_tokens(api_contract_excerpt)
    if current_issue:
        total += estimate_tokens(current_issue)
    return total
