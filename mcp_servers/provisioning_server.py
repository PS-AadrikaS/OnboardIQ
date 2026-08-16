"""
Provisioning MCP Server

Owns everything related to a new hire's system accounts and access levels.
Backed by data/provisioning_state.json (stands in for a real IT directory).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastmcp import FastMCP
from storage import read_json, write_json

mcp = FastMCP("Provisioning")

STATE_FILE = "provisioning_state.json"
EMPLOYEES_FILE = "employees.json"


def _get_employee(employee_id: str) -> dict | None:
    employees = read_json(EMPLOYEES_FILE)
    return employees.get(employee_id)


@mcp.tool()
def create_account(employee_id: str) -> dict:
    """
    Create a system account for the given employee_id.
    Fails if the employee record does not exist. Idempotent - calling it
    again on an already-created account simply confirms it exists.
    """
    employee = _get_employee(employee_id)
    if not employee:
        return {"success": False, "error": f"No employee record found for {employee_id}"}

    state = read_json(STATE_FILE)
    record = state["employees"].setdefault(employee_id, {})

    if record.get("account_created"):
        return {"success": True, "already_existed": True, "account_id": record["account_id"]}

    account_id = f"acct-{employee_id.lower()}"
    record["account_created"] = True
    record["account_id"] = account_id
    write_json(STATE_FILE, state)

    return {"success": True, "already_existed": False, "account_id": account_id}


@mcp.tool()
def assign_access(employee_id: str) -> dict:
    """
    Assign role-appropriate system access to the employee.
    Requires that create_account has already succeeded for this employee.
    """
    employee = _get_employee(employee_id)
    if not employee:
        return {"success": False, "error": f"No employee record found for {employee_id}"}

    state = read_json(STATE_FILE)
    record = state["employees"].get(employee_id)

    if not record or not record.get("account_created"):
        return {
            "success": False,
            "error": "Cannot assign access before an account has been created. "
                     "Call create_account first.",
        }

    if record.get("access_assigned"):
        return {"success": True, "already_assigned": True, "access": record["access_list"]}

    role_map = state["role_access_map"]
    access_list = role_map.get(employee["role"], role_map["default"])

    record["access_assigned"] = True
    record["access_list"] = access_list
    write_json(STATE_FILE, state)

    return {"success": True, "already_assigned": False, "access": access_list}


@mcp.tool()
def check_provisioning_status(employee_id: str) -> dict:
    """
    Return the current provisioning state for an employee:
    whether an account exists and whether access has been assigned.
    """
    state = read_json(STATE_FILE)
    record = state["employees"].get(employee_id, {})
    return {
        "employee_id": employee_id,
        "account_created": record.get("account_created", False),
        "access_assigned": record.get("access_assigned", False),
        "account_id": record.get("account_id"),
        "access": record.get("access_list", []),
    }


if __name__ == "__main__":
    mcp.run()
