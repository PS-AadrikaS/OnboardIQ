"""
Reads the current ground-truth onboarding status straight from the 3 MCP
servers. This never involves the LLM - it's used to render the dashboard
before/after a run, and costs nothing to call.
"""
from mcp_hub import MCPHub


async def get_employee_status(employee_id: str) -> dict:
    async with MCPHub() as hub:
        await hub.get_groq_tools()  # populates the tool registry used by call()
        provisioning = await hub.call("provisioning__check_provisioning_status", {"employee_id": employee_id})
        schedule = await hub.call("scheduling__get_schedule_status", {"employee_id": employee_id})
        documents = await hub.call("compliance__check_document_status", {"employee_id": employee_id})

    return {
        "provisioning": provisioning,
        "schedule": schedule,
        "documents": documents,
    }
