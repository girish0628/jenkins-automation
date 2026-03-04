import json
import traceback
from pathlib import Path
from typing import Any, Dict

class TestResult:
    def __init__(self, name, success, message="", details=None):
        self.name = name
        self.success = success
        self.message = message
        self.details = details or {}

    def to_dict(self):
        return {
            "name": self.name,
            "success": self.success,
            "message": self.message,
            "details": self.details
        }

def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_report(report: Dict[str, Any], out_path: Path) -> None:
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def run_check_safely(name, fn):
    try:
        data = fn()
        # data can be a dict result or list of results
        if isinstance(data, list):
            # wrap list into a single check output
            return {
                "name": name,
                "success": all(x.get("success", False) for x in data),
                "message": "",
                "details": data
            }
        return {
            "name": name,
            "success": bool(data.get("success", False)),
            "message": data.get("message", ""),
            "details": data.get("details", {})
        }
    except Exception as e:
        return {
            "name": name,
            "success": False,
            "message": f"Exception: {e}",
            "details": {"traceback": traceback.format_exc()}
        }