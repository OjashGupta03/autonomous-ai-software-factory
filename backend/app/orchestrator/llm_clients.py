"""
LLM provider abstraction.

`ModelRouter` (model_router.py) decides *which tier* a task should use,
in pure Python with no dependency on this file. This module turns that
decision into an actual callable client. It is the only place in the
codebase that imports langchain_openai / langchain_anthropic, so provider
SDK churn stays contained to one file.

Includes `StubLLMClient`, a deterministic, zero-network test double. It is
used in two legitimate places: (1) the test suite, and (2) an explicit
"dry run" mode (MODEL_PROVIDER_*=stub in .env) that lets an operator
exercise the full orchestration graph - scheduling, context assembly,
tool calls, retries - with zero API cost, to validate wiring before
spending real money. It is never silently substituted for a real
provider; if a real provider is configured but misconfigured (missing
API key), client construction raises instead of falling back to the stub.
"""
from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.core.constants import ModelTier
from app.orchestrator.model_router import RoutingDecision

if TYPE_CHECKING:
    # Import-time only: this module (and everything that depends on it,
    # notably app/agents/base.py) should not require pydantic/pydantic-
    # settings to be installed just to exercise the LLM-client and
    # agent-loop *logic* - `Settings` is only ever used here as a type
    # hint, never instantiated or introspected at runtime. Combined with
    # `from __future__ import annotations` above, this keeps the runtime
    # import graph light.
    from app.core.config import Settings


@dataclass
class LLMUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class ToolCallRequest:
    id: str
    name: str
    args: dict[str, Any]


@dataclass
class LLMResult:
    content: str
    tool_calls: list[ToolCallRequest]
    usage: LLMUsage
    model: str
    finish_reason: str = "stop"


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    tool_call_id: str | None = None
    name: str | None = None


class LLMClient(ABC):
    model_name: str
    provider: str

    @abstractmethod
    async def acomplete(
        self, messages: list[ChatMessage], tools: list[dict] | None = None
    ) -> LLMResult:
        ...


def _cache_key(model: str, messages: list[ChatMessage], tools: list[dict] | None) -> str:
    """Deterministic cache key for identical (model, messages, tools)
    triples. Used by the ResultCache (services/cache_service.py) to skip
    a repeat LLM call entirely - see docs/07-token-optimization.md,
    "result caching"."""
    payload = json.dumps(
        {
            "model": model,
            "messages": [(m.role, m.content, m.name) for m in messages],
            "tools": [t.get("name") for t in (tools or [])],
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


class LangChainClient(LLMClient):
    """Thin adapter over a LangChain chat model. Works with any
    `BaseChatModel` that supports `.bind_tools()` and `.ainvoke()`, which
    covers both ChatOpenAI and ChatAnthropic without provider-specific
    logic here."""

    def __init__(self, chat_model: Any, model_name: str, provider: str):
        self._chat_model = chat_model
        self.model_name = model_name
        self.provider = provider

    def _to_lc_messages(self, messages: list[ChatMessage]) -> list[Any]:
        from langchain_core.messages import (
            AIMessage,
            HumanMessage,
            SystemMessage,
            ToolMessage,
        )

        lc_messages: list[Any] = []
        for m in messages:
            if m.role == "system":
                lc_messages.append(SystemMessage(content=m.content))
            elif m.role == "user":
                lc_messages.append(HumanMessage(content=m.content))
            elif m.role == "assistant":
                lc_messages.append(AIMessage(content=m.content))
            elif m.role == "tool":
                lc_messages.append(
                    ToolMessage(content=m.content, tool_call_id=m.tool_call_id or "", name=m.name)
                )
        return lc_messages

    async def acomplete(
        self, messages: list[ChatMessage], tools: list[dict] | None = None
    ) -> LLMResult:
        model = self._chat_model.bind_tools(tools) if tools else self._chat_model
        response = await model.ainvoke(self._to_lc_messages(messages))

        content = response.content if isinstance(response.content, str) else str(response.content)
        tool_calls = [
            ToolCallRequest(id=tc.get("id", ""), name=tc.get("name", ""), args=tc.get("args", {}) or {})
            for tc in (getattr(response, "tool_calls", None) or [])
        ]

        usage = self._extract_usage(response)
        return LLMResult(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            model=self.model_name,
            finish_reason="tool_calls" if tool_calls else "stop",
        )

    @staticmethod
    def _extract_usage(response: Any) -> LLMUsage:
        # LangChain has carried usage in a couple of different places
        # across versions; check the modern attribute first and fall back
        # gracefully rather than raising, since token accounting should
        # degrade, never crash, an otherwise-successful agent run.
        usage_meta = getattr(response, "usage_metadata", None)
        if usage_meta:
            return LLMUsage(
                input_tokens=usage_meta.get("input_tokens", 0),
                output_tokens=usage_meta.get("output_tokens", 0),
            )
        resp_meta = getattr(response, "response_metadata", None) or {}
        usage = resp_meta.get("usage") or resp_meta.get("token_usage") or {}
        return LLMUsage(
            input_tokens=usage.get("prompt_tokens", usage.get("input_tokens", 0)),
            output_tokens=usage.get("completion_tokens", usage.get("output_tokens", 0)),
        )


class StubLLMClient(LLMClient):
    """Deterministic, offline test double. Never makes a network call.

    `responder` lets a test control exactly what comes back for a given
    call; the default responder returns a short canned "done" response
    with no tool calls, which is enough to drive the graph/scheduler
    tests without asserting anything about real model behaviour.
    """

    def __init__(self, model_name: str = "stub-model", responder=None):
        self.model_name = model_name
        self.provider = "stub"
        self._responder = responder
        self.calls: list[list[ChatMessage]] = []

    async def acomplete(
        self, messages: list[ChatMessage], tools: list[dict] | None = None
    ) -> LLMResult:
        self.calls.append(messages)
        if self._responder is not None:
            return self._responder(messages, tools)
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return LLMResult(
            content=f"[stub] acknowledged task context ({len(last_user)} chars).",
            tool_calls=[],
            usage=LLMUsage(input_tokens=len(last_user) // 4, output_tokens=10),
            model=self.model_name,
        )


def build_llm_client(routing: RoutingDecision, settings: Settings, model_name: str, provider: str) -> LLMClient | None:
    """Factory used by agents (app/agents/base.py). Returns None for the
    DETERMINISTIC tier - callers must not attempt to build a client for a
    task the router has already said needs no LLM."""
    if routing.tier == ModelTier.DETERMINISTIC:
        return None

    if provider == "stub":
        return StubLLMClient(model_name=model_name)

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set but an OpenAI-routed task was requested.")
        chat = ChatOpenAI(model=model_name, api_key=settings.OPENAI_API_KEY, temperature=0.2)
        return LangChainClient(chat, model_name=model_name, provider="openai")

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not set but an Anthropic-routed task was requested.")
        chat = ChatAnthropic(model=model_name, api_key=settings.ANTHROPIC_API_KEY, temperature=0.2)
        return LangChainClient(chat, model_name=model_name, provider="anthropic")

    raise ValueError(f"Unknown model provider: {provider}")


def resolve_model_for_tier(tier: ModelTier, settings: Settings) -> tuple[str, str]:
    """Reads the env-configured model name + provider for a tier. This is
    the ONLY place tier -> concrete-model-name resolution happens, so
    changing a model is always a one-line .env edit (spec section 7)."""
    mapping = {
        ModelTier.CHEAP: (settings.MODEL_CHEAP, settings.MODEL_PROVIDER_CHEAP),
        ModelTier.CODING: (settings.MODEL_CODING, settings.MODEL_PROVIDER_CODING),
        ModelTier.REASONING: (settings.MODEL_REASONING, settings.MODEL_PROVIDER_REASONING),
        ModelTier.FALLBACK: (settings.MODEL_FALLBACK, settings.MODEL_PROVIDER_FALLBACK),
    }
    if tier not in mapping:
        raise ValueError(f"Tier {tier} has no configured model (or is DETERMINISTIC, which needs none).")
    return mapping[tier]
