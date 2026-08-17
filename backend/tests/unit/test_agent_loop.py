"""
ToolCallingAgent loop tests (app/agents/base.py), using StubLLMClient so
no network/API key is needed. These mirror exactly the scenarios that
were manually verified while building this repository.
"""
from __future__ import annotations

import pytest

from app.agents.base import ToolCallingAgent
from app.orchestrator.llm_clients import LLMResult, LLMUsage, StubLLMClient, ToolCallRequest
from app.tools.base import Tool, ToolResult


class EchoTool(Tool):
    name = "echo"
    description = "Echoes back whatever text is given."
    parameters_schema = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}

    async def run(self, text: str) -> ToolResult:
        return ToolResult(success=True, output={"echoed": text})


class AlwaysFailTool(Tool):
    name = "boom"
    description = "Always raises, to test agent-loop resilience."
    parameters_schema = {"type": "object", "properties": {}}

    async def run(self) -> ToolResult:
        raise RuntimeError("simulated crash")


@pytest.mark.asyncio
async def test_zero_tool_calls_terminates_in_one_iteration():
    stub = StubLLMClient(responder=lambda msgs, tools: LLMResult(
        content="done, no tools needed", tool_calls=[], usage=LLMUsage(10, 5), model="stub-model"))
    agent = ToolCallingAgent(system_prompt="sys", tools=[EchoTool()], llm_client=stub, max_iterations=5)
    result = await agent.run("do something simple")
    assert result.iterations == 1
    assert result.hit_iteration_limit is False
    assert result.final_content == "done, no tools needed"


@pytest.mark.asyncio
async def test_real_tool_call_executes_and_accumulates_usage():
    state = {"n": 0}

    def responder(msgs, tools):
        state["n"] += 1
        if state["n"] == 1:
            return LLMResult(content="", tool_calls=[ToolCallRequest(id="tc1", name="echo", args={"text": "hello"})],
                              usage=LLMUsage(20, 8), model="stub-model")
        return LLMResult(content="Done after using the tool.", tool_calls=[], usage=LLMUsage(15, 6), model="stub-model")

    stub = StubLLMClient(responder=responder)
    agent = ToolCallingAgent(system_prompt="sys", tools=[EchoTool()], llm_client=stub, max_iterations=5)
    result = await agent.run("please echo hello")

    assert result.iterations == 2
    assert len(result.tool_calls_made) == 1
    assert result.tool_calls_made[0].result.success is True
    assert result.tool_calls_made[0].result.output == {"echoed": "hello"}
    assert result.usage.input_tokens == 35  # 20 + 15
    assert result.usage.output_tokens == 14  # 8 + 6


@pytest.mark.asyncio
async def test_iteration_cap_prevents_infinite_loop():
    stub = StubLLMClient(responder=lambda msgs, tools: LLMResult(
        content="", tool_calls=[ToolCallRequest(id="x", name="echo", args={"text": "loop"})],
        usage=LLMUsage(5, 2), model="stub-model"))
    agent = ToolCallingAgent(system_prompt="sys", tools=[EchoTool()], llm_client=stub, max_iterations=3)
    result = await agent.run("infinite tool user")
    assert result.hit_iteration_limit is True
    assert result.iterations == 3
    assert len(result.tool_calls_made) == 3


@pytest.mark.asyncio
async def test_a_raising_tool_is_caught_not_propagated():
    def responder(msgs, tools):
        if not any(m.role == "tool" for m in msgs):
            return LLMResult(content="", tool_calls=[ToolCallRequest(id="b1", name="boom", args={})],
                              usage=LLMUsage(5, 2), model="stub-model")
        return LLMResult(content="Recovered after tool error.", tool_calls=[], usage=LLMUsage(5, 2), model="stub-model")

    stub = StubLLMClient(responder=responder)
    agent = ToolCallingAgent(system_prompt="sys", tools=[AlwaysFailTool()], llm_client=stub, max_iterations=5)
    result = await agent.run("trigger a crash")
    assert result.tool_calls_made[0].result.success is False
    assert "simulated crash" in result.tool_calls_made[0].result.error
    assert result.final_content == "Recovered after tool error."


@pytest.mark.asyncio
async def test_unknown_tool_name_handled_gracefully():
    calls = {"n": 0}

    def responder(msgs, tools):
        calls["n"] += 1
        if calls["n"] == 1:
            return LLMResult(content="", tool_calls=[ToolCallRequest(id="u1", name="does_not_exist", args={})],
                              usage=LLMUsage(1, 1), model="stub-model")
        return LLMResult(content="ok", tool_calls=[], usage=LLMUsage(1, 1), model="stub-model")

    stub = StubLLMClient(responder=responder)
    agent = ToolCallingAgent(system_prompt="sys", tools=[EchoTool()], llm_client=stub, max_iterations=5)
    result = await agent.run("call an unbound tool")
    assert result.tool_calls_made[0].result.success is False
    assert "Unknown tool" in result.tool_calls_made[0].result.error
