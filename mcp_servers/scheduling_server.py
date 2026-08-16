"""
Scheduling MCP Server

Owns orientation and manager-1:1 booking for new hires, including real
conflict detection against existing calendar entries. Backed by
data/calendar.json (stands in for a real calendar service).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastmcp import FastMCP
from storage import read_json, write_json

mcp = FastMCP("Scheduling")

CALENDAR_FILE = "calendar.json"
DEFAULT_ORIENTATION_SLOT = "10:00-11:00"
DEFAULT_1ON1_SLOT = "09:00-10:00"


def _has_conflict(calendar: dict, date: str, slot: str) -> str | None:
    for busy in calendar["busy_slots"]:
        if busy["date"] == date and busy["slot"] == slot:
            return busy["reason"]
    return None


@mcp.tool()
def check_calendar_conflicts(date: str, slot: str = DEFAULT_ORIENTATION_SLOT) -> dict:
    """
    Check whether the given date + time slot (e.g. "2026-08-17", "10:00-11:00")
    already has something booked. Always call this before booking.
    """
    calendar = read_json(CALENDAR_FILE)
    conflict_reason = _has_conflict(calendar, date, slot)
    return {
        "date": date,
        "slot": slot,
        "conflict": conflict_reason is not None,
        "reason": conflict_reason,
    }


@mcp.tool()
def book_orientation(employee_id: str, date: str, slot: str = DEFAULT_ORIENTATION_SLOT) -> dict:
    """
    Book an orientation session for the employee at the given date/slot.
    Refuses to double-book a slot that already has a conflict -
    call check_calendar_conflicts first and pick a free slot.
    """
    calendar = read_json(CALENDAR_FILE)
    conflict_reason = _has_conflict(calendar, date, slot)
    if conflict_reason:
        return {
            "success": False,
            "error": f"Slot {date} {slot} is unavailable: {conflict_reason}. "
                     f"Choose a different slot and try again.",
        }

    calendar["busy_slots"].append({"date": date, "slot": slot, "reason": f"Orientation - {employee_id}"})
    bookings = calendar["bookings"].setdefault(employee_id, {})
    bookings["orientation"] = {"date": date, "slot": slot, "event_id": f"orient-{employee_id.lower()}"}
    write_json(CALENDAR_FILE, calendar)

    return {"success": True, "event_id": bookings["orientation"]["event_id"], "date": date, "slot": slot}


@mcp.tool()
def book_manager_1on1(employee_id: str, date: str, slot: str = DEFAULT_1ON1_SLOT) -> dict:
    """
    Book a manager introduction 1:1 for the employee at the given date/slot.
    Refuses to double-book - call check_calendar_conflicts first.
    """
    calendar = read_json(CALENDAR_FILE)
    conflict_reason = _has_conflict(calendar, date, slot)
    if conflict_reason:
        return {
            "success": False,
            "error": f"Slot {date} {slot} is unavailable: {conflict_reason}. "
                     f"Choose a different slot and try again.",
        }

    calendar["busy_slots"].append({"date": date, "slot": slot, "reason": f"Manager 1:1 - {employee_id}"})
    bookings = calendar["bookings"].setdefault(employee_id, {})
    bookings["manager_1on1"] = {"date": date, "slot": slot, "event_id": f"1on1-{employee_id.lower()}"}
    write_json(CALENDAR_FILE, calendar)

    return {"success": True, "event_id": bookings["manager_1on1"]["event_id"], "date": date, "slot": slot}


@mcp.tool()
def get_schedule_status(employee_id: str) -> dict:
    """Return whatever has been booked so far for this employee."""
    calendar = read_json(CALENDAR_FILE)
    bookings = calendar["bookings"].get(employee_id, {})
    return {
        "employee_id": employee_id,
        "orientation_booked": "orientation" in bookings,
        "manager_1on1_booked": "manager_1on1" in bookings,
        "bookings": bookings,
    }


if __name__ == "__main__":
    mcp.run()
