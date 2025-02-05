import json
from pathlib import Path


def load_cog_strings(cog_path: Path) -> dict:
    """Load localized strings from JSON file"""
    strings_path = cog_path / "strings.json"
    try:
        with open(strings_path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "errors": {
                "missing_strings": "String resources not found"
            }
        } 