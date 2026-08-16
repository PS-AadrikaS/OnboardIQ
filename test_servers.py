"""
Quick sanity check: connects to each MCP server as a real client,
lists its tools, and exercises a couple of calls end to end.
Run this before touching the orchestrator - if this fails, nothing above it will work.
"""
import asyncio
from fastmcp import Client

SERVERS = {
    "Provisioning": "mcp_servers/provisioning_server.py",
    "Scheduling": "mcp_servers/scheduling_server.py",
    "Compliance": "mcp_servers/compliance_server.py",
}


async def test_server(name, path):
    print(f"\n=== {name} ===")
    async with Client(path) as client:
        tools = await client.list_tools()
        print(f"Tools exposed: {[t.name for t in tools]}")

        if name == "Provisioning":
            r1 = await client.call_tool("create_account", {"employee_id": "EMP001"})
            print("create_account ->", r1.data)
            r2 = await client.call_tool("assign_access", {"employee_id": "EMP001"})
            print("assign_access ->", r2.data)
            r3 = await client.call_tool("check_provisioning_status", {"employee_id": "EMP001"})
            print("check_provisioning_status ->", r3.data)

        if name == "Scheduling":
            r1 = await client.call_tool("check_calendar_conflicts", {"date": "2026-08-17", "slot": "10:00-11:00"})
            print("check_calendar_conflicts (should conflict) ->", r1.data)
            r2 = await client.call_tool("book_orientation", {"employee_id": "EMP001", "date": "2026-08-17", "slot": "14:00-15:00"})
            print("book_orientation (free slot) ->", r2.data)

        if name == "Compliance":
            r1 = await client.call_tool("check_document_status", {"employee_id": "EMP001"})
            print("check_document_status ->", r1.data)


async def main():
    for name, path in SERVERS.items():
        await test_server(name, path)


if __name__ == "__main__":
    asyncio.run(main())
