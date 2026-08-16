"""
CLI entry point.

Usage:
    python orchestrator/run_onboarding.py EMP001

Requires GROQ_API_KEY to be set (in your environment or a .env file).
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
from agent_loop import run_onboarding, CHEAP_MODEL, EXPENSIVE_MODEL
from evaluator import evaluate_run

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_employee(employee_id: str) -> dict:
    with open(DATA_DIR / "employees.json") as f:
        employees = json.load(f)
    if employee_id not in employees:
        raise SystemExit(f"Unknown employee_id '{employee_id}'. Options: {list(employees.keys())}")
    return employees[employee_id]


async def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python orchestrator/run_onboarding.py <EMPLOYEE_ID>")

    if not os.getenv("GROQ_API_KEY"):
        raise SystemExit(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or export it in your shell."
        )

    employee_id = sys.argv[1]
    employee = load_employee(employee_id)

    print(f"Starting onboarding for {employee['name']} ({employee_id})...\n")
    result = await run_onboarding(employee)

    print(f"\n=== RESULT: {result.status.upper()} ===")
    print(result.summary)

    print(f"\n=== DECISION LOG ({len(result.decision_log)} steps) ===")
    for step in result.decision_log:
        print(f"[{step['iteration']}] ({step['model']}) action={step['action']}")
        if step.get("reasoning"):
            print(f"    reasoning: {step['reasoning']}")
        if "result" in step:
            print(f"    result: {step['result']}")

    total_input = sum(c["input_tokens"] for c in result.cost_log)
    total_output = sum(c["output_tokens"] for c in result.cost_log)
    cheap_calls = sum(1 for c in result.cost_log if c["model"] == CHEAP_MODEL)
    expensive_calls = len(result.cost_log) - cheap_calls

    print(f"\n=== COST SUMMARY ===")
    print(f"Total LLM calls: {len(result.cost_log)}  (cheap [{CHEAP_MODEL}]: {cheap_calls}, escalated [{EXPENSIVE_MODEL}]: {expensive_calls})")
    print(f"Total tokens: {total_input} in / {total_output} out")

    eval_report = evaluate_run(result)
    print(f"\n=== AGENT EVALUATION REPORT ===")
    print(f"Task Success Rate: {int(eval_report.task_success_rate * 100)}%")
    print(f"Tool Selection Accuracy: {int(eval_report.tool_selection_accuracy * 100)}%")
    print(f"Trajectory Accuracy: {int(eval_report.trajectory_accuracy * 100)}%")
    print(f"Conflict Recovery Rate: {int(eval_report.conflict_recovery_rate * 100)}%")
    print(f"Groundedness Score: {int(eval_report.groundedness_score * 100)}%")
    print(f"Evaluation report saved to: logs/eval_report.json")


if __name__ == "__main__":
    asyncio.run(main())

