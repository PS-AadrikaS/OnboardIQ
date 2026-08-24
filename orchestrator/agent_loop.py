"""
Orchestrator Agent Loop (Groq API Edition)

This is the "brain" of OnboardIQ. It is a goal-based agent: given a single
goal ("onboard this employee"), it repeatedly reasons about the current
state, picks one action (an MCP tool call), observes the result, and decides
the next action - until the goal is complete or it needs to hand off to a
human.

Cost-reduction techniques implemented here:
  1. Routine decisions run on a cheap, ultra-fast model (CHEAP_MODEL). Only once the
     agent hits a real problem (a failed/conflicting tool call) does it
     escalate to a stronger reasoning model (EXPENSIVE_MODEL) for that step.
  2. The model only ever sees a small structured message history (the goal
     + tool calls/results so far) - never a growing wall of raw text - so
     each call stays cheap regardless of how many steps the process takes.
  3. Every tool that doesn't require judgment (creating an account, booking
     a slot, updating a checklist) is a deterministic function call with
     zero LLM cost - the LLM is only ever used to decide *what* to call next.
"""
import json
import time
from dataclasses import dataclass, field

from groq import AsyncGroq

from mcp_hub import MCPHub

CHEAP_MODEL = "qwen/qwen3.6-27b"
EXPENSIVE_MODEL = "openai/gpt-oss-120b"
MAX_ITERATIONS = 20
FAILURE_ESCALATION_THRESHOLD = 1  # escalate after this many tool failures in a row

CONTROL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "control__finish",
            "description": (
                "Call this when every onboarding step is verified complete: "
                "account created, access assigned, orientation booked, manager "
                "1:1 booked, and all required documents submitted. Do not call "
                "this until you have actually verified each of these."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Short summary of what was completed."}
                },
                "required": ["summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "control__escalate",
            "description": (
                "Call this if onboarding cannot proceed automatically and needs "
                "a human decision - for example, a document is missing and there "
                "is no automated way to obtain it, or a tool keeps failing for "
                "reasons outside your control."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Clear explanation of what is blocking progress."}
                },
                "required": ["reason"],
            },
        },
    },
]

SYSTEM_PROMPT_TEMPLATE = """You are the onboarding orchestrator agent for OnboardIQ.

Your goal: fully onboard the following new employee by using the tools
available to you. You must reason step by step and only take ONE action
(one tool call) per turn, then observe its result before deciding the next
action. Do not assume a tool succeeded - always check the result.

Employee to onboard:
{employee_json}

Required outcome, all of which must be true before you call control__finish:
1. provisioning__create_account has succeeded
2. provisioning__assign_access has succeeded (requires an account to exist first)
3. scheduling__book_orientation has succeeded (check scheduling__check_calendar_conflicts
   first, and if a slot conflicts, try a different slot)
4. scheduling__book_manager_1on1 has succeeded (check for conflicts first, different
   time from orientation)
5. compliance__check_document_status shows all_complete = true. If documents are
   missing, you cannot submit them yourself - if they are still missing after
   checking, call control__escalate and explain exactly which documents are missing.

If any tool call fails, read the error message, decide the right response
(retry with different parameters, or escalate), and continue. Do not repeat
the exact same failing call more than once.

When everything is verified complete, call control__finish with a short summary.
If you get blocked in a way you cannot resolve, call control__escalate.
"""


@dataclass
class RunResult:
    status: str  # "complete" | "escalated" | "max_iterations_reached"
    summary: str
    decision_log: list = field(default_factory=list)
    cost_log: list = field(default_factory=list)


async def run_onboarding(employee: dict, api_key: str | None = None, step_callback=None) -> RunResult:
    client = AsyncGroq(api_key=api_key) if api_key else AsyncGroq()

    decision_log = []
    cost_log = []
    consecutive_failures = 0

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(employee_json=json.dumps(employee, indent=2))

    async with MCPHub() as hub:
        mcp_tools = await hub.get_groq_tools()
        all_tools = mcp_tools + CONTROL_TOOLS

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Begin onboarding for {employee['name']} ({employee['employee_id']}).",
            },
        ]

        for iteration in range(1, MAX_ITERATIONS + 1):
            # --- cost-reduction technique 2: escalate model only after real trouble ---
            model_for_this_step = EXPENSIVE_MODEL if consecutive_failures >= FAILURE_ESCALATION_THRESHOLD else CHEAP_MODEL

            start = time.time()
            try:
                response = await client.chat.completions.create(
                    model=model_for_this_step,
                    messages=messages,
                    tools=all_tools,
                    tool_choice="auto",
                    temperature=0.1,
                )
            except Exception as err:
                err_str = str(err).lower()
                if "429" in err_str or "rate_limit" in err_str or "output_parse_failed" in err_str or "parsing failed" in err_str:
                    fallback_model = EXPENSIVE_MODEL
                    print(f"[FALLBACK RECOVERY] {model_for_this_step} error. Retrying automatically with {fallback_model}...")
                    model_for_this_step = fallback_model
                    response = await client.chat.completions.create(
                        model=model_for_this_step,
                        messages=messages,
                        tools=all_tools,
                        tool_choice="auto",
                        temperature=0.1,
                    )
                else:
                    raise err

            elapsed = round(time.time() - start, 2)

            usage = response.usage
            input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
            output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0

            cost_log.append(
                {
                    "iteration": iteration,
                    "model": model_for_this_step,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "seconds": elapsed,
                }
            )

            message = response.choices[0].message
            reasoning_text = (message.content or "").strip()
            tool_calls = message.tool_calls or []

            # Append assistant message to context
            assistant_msg_dict = {"role": "assistant", "content": message.content}
            if tool_calls:
                assistant_msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tool_calls
                ]
            messages.append(assistant_msg_dict)

            if not tool_calls:
                decision_log.append(
                    {
                        "iteration": iteration,
                        "model": model_for_this_step,
                        "reasoning": reasoning_text,
                        "action": None,
                        "result": "No tool call produced - reminding agent to take an action.",
                    }
                )
                messages.append(
                    {
                        "role": "user",
                        "content": "Please perform the next step by invoking one of the available tools.",
                    }
                )
                continue

            # Process the primary action (one tool per turn)
            tool_call = tool_calls[0]
            tool_name = tool_call.function.name
            try:
                tool_args = json.loads(tool_call.function.arguments or "{}")
            except Exception:
                tool_args = {}

            # Handle control finish/escalate tools
            if tool_name in ("control__finish", "control.finish"):
                decision_log.append(
                    {
                        "iteration": iteration,
                        "model": model_for_this_step,
                        "reasoning": reasoning_text,
                        "action": "control__finish",
                        "input": tool_args,
                        "result": "Onboarding complete.",
                    }
                )
                return RunResult("complete", tool_args.get("summary", "Onboarding complete."), decision_log, cost_log)

            if tool_name in ("control__escalate", "control.escalate"):
                decision_log.append(
                    {
                        "iteration": iteration,
                        "model": model_for_this_step,
                        "reasoning": reasoning_text,
                        "action": "control__escalate",
                        "input": tool_args,
                        "result": "Escalated to human.",
                    }
                )
                return RunResult("escalated", tool_args.get("reason", "Escalated."), decision_log, cost_log)

            # --- real MCP tool call ---
            tool_result = await hub.call(tool_name, tool_args)
            succeeded = tool_result.get("success", True)  # read-only queries default to success
            consecutive_failures = 0 if succeeded else consecutive_failures + 1

            total_step_tokens = input_tokens + output_tokens
            step_entry = {
                "iteration": iteration,
                "model": model_for_this_step,
                "reasoning": reasoning_text,
                "action": tool_name,
                "input": tool_args,
                "result": tool_result,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_step_tokens,
            }
            decision_log.append(step_entry)
            print(f"[LIVE OBSERVABILITY] Step {iteration} ({model_for_this_step}) -> Tool: {tool_name}\n   Tokens Used: {total_step_tokens} ({input_tokens} in / {output_tokens} out)\n   Reasoning: {reasoning_text}\n   Observation: {json.dumps(tool_result)}\n")
            if step_callback:
                step_callback(step_entry)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result),
                }
            )

        return RunResult("max_iterations_reached", "Stopped after reaching the iteration limit.", decision_log, cost_log)
