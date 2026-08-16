"""
Tiny JSON-file storage helper.

Each MCP server treats a JSON file as its "database" - this stands in for a
real system (an IT directory, a calendar service, an HR platform). Swapping
these for real API calls later does not require changing any tool signatures.
"""
import json
from pathlib import Path
from threading import Lock

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_lock = Lock()


def read_json(filename: str) -> dict:
    path = DATA_DIR / filename
    with _lock:
        with open(path, "r") as f:
            return json.load(f)


def write_json(filename: str, data: dict) -> None:
    path = DATA_DIR / filename
    with _lock:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
