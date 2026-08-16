"""
Resets provisioning, calendar, and checklist state back to the original demo
data. Run this before each fresh demo run:

    python reset_data.py
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

PROVISIONING_RESET = {
    "role_access_map": {
        "Backend Engineer": ["source-control", "cloud-console", "ci-cd-pipeline", "issue-tracker"],
        "Sales Executive": ["crm", "email", "sales-dashboard"],
        "HR Coordinator": ["hris", "email", "payroll-view"],
        "default": ["email", "intranet"],
    },
    "employees": {},
}

CALENDAR_RESET = {
    "busy_slots": [
        {"date": "2026-08-17", "slot": "10:00-11:00", "reason": "All-hands meeting"},
        {"date": "2026-08-18", "slot": "09:00-10:00", "reason": "Sales team standup"},
    ],
    "bookings": {},
}

CHECKLIST_RESET = {
    "required_documents": {
        "default": ["Government ID", "Signed Offer Letter", "Tax Form", "NDA"],
        "Engineering": ["Government ID", "Signed Offer Letter", "Tax Form", "NDA", "Security Policy Acknowledgement"],
        "Human Resources": ["Government ID", "Signed Offer Letter", "Tax Form", "NDA", "Confidentiality Agreement"],
    },
    "employee_documents": {
        "EMP001": {
            "Government ID": "submitted",
            "Signed Offer Letter": "submitted",
            "Tax Form": "missing",
            "NDA": "submitted",
            "Security Policy Acknowledgement": "missing",
        },
        "EMP002": {
            "Government ID": "submitted",
            "Signed Offer Letter": "submitted",
            "Tax Form": "submitted",
            "NDA": "submitted",
        },
        "EMP003": {
            "Government ID": "missing",
            "Signed Offer Letter": "submitted",
            "Tax Form": "missing",
            "NDA": "missing",
            "Confidentiality Agreement": "missing",
        },
    },
}


def main():
    with open(DATA_DIR / "provisioning_state.json", "w") as f:
        json.dump(PROVISIONING_RESET, f, indent=2)
    with open(DATA_DIR / "calendar.json", "w") as f:
        json.dump(CALENDAR_RESET, f, indent=2)
    with open(DATA_DIR / "checklist.json", "w") as f:
        json.dump(CHECKLIST_RESET, f, indent=2)
    print("Data reset to initial demo state.")


if __name__ == "__main__":
    main()
