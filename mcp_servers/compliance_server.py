"""
Compliance MCP Server

Owns document/paperwork tracking for new hires (ID, tax forms, NDA, etc).
Backed by data/checklist.json (stands in for a real HR document system).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastmcp import FastMCP
from storage import read_json, write_json

mcp = FastMCP("Compliance")

CHECKLIST_FILE = "checklist.json"
EMPLOYEES_FILE = "employees.json"


@mcp.tool()
def check_document_status(employee_id: str) -> dict:
    """
    Check which required documents are missing for this employee, based on
    their department's document requirements.
    """
    checklist = read_json(CHECKLIST_FILE)
    employees = read_json(EMPLOYEES_FILE)

    employee = employees.get(employee_id)
    if not employee:
        return {"success": False, "error": f"No employee record found for {employee_id}"}

    required = checklist["required_documents"].get(
        employee["department"], checklist["required_documents"]["default"]
    )
    current = checklist["employee_documents"].get(employee_id, {})

    missing = [doc for doc in required if current.get(doc, "missing") != "submitted"]

    return {
        "employee_id": employee_id,
        "required_documents": required,
        "missing_documents": missing,
        "all_complete": len(missing) == 0,
    }


@mcp.tool()
def update_checklist(employee_id: str, document_name: str, status: str) -> dict:
    """
    Update the status of a single document for an employee.
    status must be one of: "submitted", "missing".
    """
    if status not in ("submitted", "missing"):
        return {"success": False, "error": 'status must be "submitted" or "missing"'}

    checklist = read_json(CHECKLIST_FILE)
    employee_docs = checklist["employee_documents"].setdefault(employee_id, {})
    employee_docs[document_name] = status
    write_json(CHECKLIST_FILE, checklist)

    return {"success": True, "employee_id": employee_id, "document_name": document_name, "status": status}


@mcp.tool()
def get_checklist(employee_id: str) -> dict:
    """Return the full document checklist and current status for an employee."""
    checklist = read_json(CHECKLIST_FILE)
    return {
        "employee_id": employee_id,
        "documents": checklist["employee_documents"].get(employee_id, {}),
    }


if __name__ == "__main__":
    mcp.run()
