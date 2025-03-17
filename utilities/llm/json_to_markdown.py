"""
Convert JSON weather data to Markdown using the external MarkItDown library.
This implementation replaces the legacy custom markdown conversion logic.
"""

import json
import os
import sys
import tempfile
from typing import Any

try:
    from markitdown import MarkItDown
except ImportError:
    sys.exit(1)


def json_to_markdown_weather_summary(weather_json: dict[str, Any]) -> str:
    if not weather_json or "all_cities" not in weather_json:
        return ""

    json_str = json.dumps(weather_json)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8") as tmp:
        tmp.write(json_str)
        tmp.flush()
        tmp_filename = tmp.name
    try:
        md = MarkItDown(enable_plugins=False)
        result = md.convert(tmp_filename, input_format="json")
        markdown = result.text_content
    finally:
        os.remove(tmp_filename)
    return markdown
