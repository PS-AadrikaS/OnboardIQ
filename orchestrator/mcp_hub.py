"""
MCP Hub

Connects to all 3 specialist MCP servers (Provisioning, Scheduling,
Compliance) at once, and presents them to the orchestrator as a single
flat list of tools - prefixed by server name so the model always knows
which specialist agent a tool belongs to (e.g. "provisioning__create_account").
"""
from pathlib import Path
from fastmcp import Client

SERVERS_DIR = Path(__file__).resolve().parent.parent / "mcp_servers"

SERVER_PATHS = {
    "provisioning": SERVERS_DIR / "provisioning_server.py",
    "scheduling": SERVERS_DIR / "scheduling_server.py",
    "compliance": SERVERS_DIR / "compliance_server.py",
}


class MCPHub:
    """
    Async context manager. Holds one live Client connection per MCP server
    and exposes a unified tool list + a single call() entrypoint that routes
    to the right server automatically.
    """

    def __init__(self):
        self._clients = {}
        self._tool_owner = {}  # "provisioning__create_account" -> ("provisioning", "create_account")

    async def __aenter__(self):
        for server_name, path in SERVER_PATHS.items():
            client = Client(str(path))
            await client.__aenter__()
            self._clients[server_name] = client
        return self

    async def __aexit__(self, exc_type, exc, tb):
        for client in self._clients.values():
            await client.__aexit__(exc_type, exc, tb)

    async def get_groq_tools(self) -> list[dict]:
        """
        Returns every tool from every connected server, in OpenAI / Groq tool format.
        Tool names are namespaced as "<server>__<tool>" for regex & API safety.
        """
        groq_tools = []
        for server_name, client in self._clients.items():
            tools = await client.list_tools()
            for tool in tools:
                namespaced_name = f"{server_name}__{tool.name}"
                dot_name = f"{server_name}.{tool.name}"
                self._tool_owner[namespaced_name] = (server_name, tool.name)
                self._tool_owner[dot_name] = (server_name, tool.name)

                params = tool.inputSchema if isinstance(tool.inputSchema, dict) else {}
                if "type" not in params:
                    params["type"] = "object"

                groq_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": namespaced_name,
                            "description": f"[{server_name} agent] {tool.description or ''}",
                            "parameters": params,
                        },
                    }
                )
        return groq_tools

    # Alias for backward compatibility
    get_anthropic_tools = get_groq_tools

    async def call(self, namespaced_tool_name: str, arguments: dict) -> dict:
        """
        Call a tool by its namespaced name (e.g. "scheduling__book_orientation").
        Returns the tool's structured result dict.
        """
        if not self._tool_owner:
            await self.get_groq_tools()  # lazily populate the registry if not done yet

        if namespaced_tool_name not in self._tool_owner:
            return {"success": False, "error": f"Unknown tool: {namespaced_tool_name}"}

        server_name, real_tool_name = self._tool_owner[namespaced_tool_name]
        client = self._clients[server_name]
        result = await client.call_tool(real_tool_name, arguments)
        return result.data

