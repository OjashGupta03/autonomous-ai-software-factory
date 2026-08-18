"""
Shared tool-calling agent loop (docs/09-agent-design.md).

Every specialized agent (planner, coder, reviewer, debugger, tester,
documenter) is a thin configuration of `ToolCallingAgent`: a system
prompt + a bound tool set + a model tier. None of them hand-roll their
own prompting loop - that loop lives here, once, so behaviour like the
iteration cap and tool-error handling is consistent everywhere.

The loop is a standard ReAct-style cycle: send messages (+ tool specs) to
the LLM, and if it requests tool calls, execute each one for real (via
the Tool abstraction - never fabricated), append the results as tool
messages, and loop. It stops when the model responds with no further tool
calls, or after `max_iterations` (config: AGENT_TOOL_LOOP_MAX_ITERATIONS)
- whichever comes first, so a confused agent can never loop forever.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.orchestrator.llm_clients import ChatMessage, LLMClient, LLMUsage
from app.tools.base import Tool, ToolResult


@dataclass
class ToolCallRecord:
    tool_name: str
    args: dict
    result: ToolResult


@dataclass
class AgentRunResult:
    final_content: str
    tool_calls_made: list[ToolCallRecord]
    usage: LLMUsage
    model: str
    iterations: int
    hit_iteration_limit: bool


def _tool_result_to_message_content(result: ToolResult) -> str:
    payload = {"success": result.success}
    if result.success:
        payload["output"] = result.output
    else:
        payload["error"] = result.error
    try:
        return json.dumps(payload)[:6000]  # bound what goes back into context
    except TypeError:
        return json.dumps({"success": result.success, "output": str(result.output)})[:6000]


class ToolCallingAgent:
    def __init__(
        self,
        system_prompt: str,
        tools: list[Tool],
        llm_client: LLMClient,
        max_iterations: int = 8,
    ):
        self.system_prompt = system_prompt
        self.tools = tools
        self.llm_client = llm_client
        self.max_iterations = max_iterations
        self._tools_by_name = {t.name: t for t in tools}

    async def run(self, task_prompt: str) -> AgentRunResult:
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=self.system_prompt),
            ChatMessage(role="user", content=task_prompt),
        ]
        tool_specs = [t.to_langchain_tool_spec() for t in self.tools]
        total_usage = LLMUsage(input_tokens=0, output_tokens=0)
        calls_made: list[ToolCallRecord] = []

        for iteration in range(1, self.max_iterations + 1):
            result = await self.llm_client.acomplete(messages, tools=tool_specs or None)
            total_usage.input_tokens += result.usage.input_tokens
            total_usage.output_tokens += result.usage.output_tokens

            if not result.tool_calls:
                return AgentRunResult(
                    final_content=result.content,
                    tool_calls_made=calls_made,
                    usage=total_usage,
                    model=result.model,
                    iterations=iteration,
                    hit_iteration_limit=False,
                )

            tc_dicts = [tc.raw for tc in result.tool_calls]
            messages.append(ChatMessage(role="assistant", content=result.content or "", tool_calls=tc_dicts, additional_kwargs=result.additional_kwargs, raw_message=getattr(result, "raw_message", None)))
            for tc in result.tool_calls:
                tool = self._tools_by_name.get(tc.name)
                if tool is None:
                    tool_result = ToolResult(success=False, error=f"Unknown tool '{tc.name}'.")
                else:
                    try:
                        tool_result = await tool.run(**tc.args)
                    except TypeError as e:
                        tool_result = ToolResult(success=False, error=f"Bad arguments for '{tc.name}': {e}")
                    except Exception as e:  # a tool crashing must not crash the agent loop
                        tool_result = ToolResult(success=False, error=f"Tool '{tc.name}' raised: {e}")
                calls_made.append(ToolCallRecord(tool_name=tc.name, args=tc.args, result=tool_result))
                messages.append(
                    ChatMessage(
                        role="tool",
                        content=_tool_result_to_message_content(tool_result),
                        tool_call_id=tc.id,
                        name=tc.name,
                    )
                )

        return AgentRunResult(
            final_content="[max tool-loop iterations reached without a final answer]",
            tool_calls_made=calls_made,
            usage=total_usage,
            model=self.llm_client.model_name,
            iterations=self.max_iterations,
            hit_iteration_limit=True,
        )
