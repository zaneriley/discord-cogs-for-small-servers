import re

from cogs.utilities.text_formatting_utils import (
    calculate_display_width,
    format_row,
    get_max_widths,
    pad_string,
)


def test_pad_string_right_alignment():
    """Test right alignment of strings with pad_string function."""
    # Test basic right alignment
    assert pad_string("test", 8, "right") == "    test"

    # Test with empty string
    assert pad_string("", 5, "right") == "     "

    # Test with exact width (no padding needed)
    assert pad_string("test", 4, "right") == "test"


def test_pad_string_left_alignment():
    """Test left alignment of strings with pad_string function."""
    # Test basic left alignment
    assert pad_string("test", 8, "left") == "test    "

    # Test with empty string
    assert pad_string("", 5, "left") == "     "

    # Test with exact width (no padding needed)
    assert pad_string("test", 4, "left") == "test"


def test_right_alignment_with_numbers():
    """Test right alignment of numerical values with sign."""
    # Test with mixed positive and negative numbers
    assert pad_string("42", 5, "right") == "   42"
    assert pad_string("-42", 5, "right") == "  -42"  # Same width, but negative takes one more character

    # Test with equal display width but different char count
    assert pad_string("10", 4, "right") == "  10"
    assert pad_string("-9", 4, "right") == "  -9"  # Should align with "10" visually

    # Test with temperature format
    assert pad_string("5°", 5, "right") == "   5°"
    assert pad_string("10°", 5, "right") == "  10°"
    assert pad_string("-5°", 5, "right") == "  -5°"


def test_format_row_alignment():
    """Test formatting a row with mixed alignments."""
    row = {
        "city": "New York",
        "high": "28°",
        "low": "-5°",
        "precip": "30%"
    }
    keys = ["city", "high", "low", "precip"]
    widths = {"city": 10, "high": 5, "low": 5, "precip": 5}

    # Test with all left alignment
    alignments = ["left"] * 4
    left_result = format_row(row, keys, widths, alignments)
    assert "New York" in left_result
    assert "28°" in left_result
    assert "-5°" in left_result

    # Test with mixed alignment (city left, temps right, precip left)
    alignments = ["left", "right", "right", "left"]
    mixed_result = format_row(row, keys, widths, alignments)
    assert "New York" in mixed_result
    assert "  28°" in mixed_result  # Should have leading spaces
    assert "  -5°" in mixed_result  # Should have leading spaces

    # Return both results for visual inspection
    return {
        "left_aligned": left_result,
        "mixed_aligned": mixed_result
    }


def test_alignment_with_weather_data():
    """Test alignment with realistic weather data including negative temps."""
    weather_rows = [
        {
            "ᴄɪᴛʏ": "Seattle",
            "ʜ°ᴄ": "14°",
            "ʟ°ᴄ": "8°",
            "ᴘʀᴇᴄɪᴘ": "70%"
        },
        {
            "ᴄɪᴛʏ": "NYC",
            "ʜ°ᴄ": "7°",
            "ʟ°ᴄ": "-1°",
            "ᴘʀᴇᴄɪᴘ": "0%"
        },
        {
            "ᴄɪᴛʏ": "Tokyo",
            "ʜ°ᴄ": "5°",
            "ʟ°ᴄ": "1°",
            "ᴘʀᴇᴄɪᴘ": "100%"
        }
    ]

    keys = ["ᴄɪᴛʏ", "ʜ°ᴄ", "ʟ°ᴄ", "ᴘʀᴇᴄɪᴘ"]

    # Calculate widths
    widths = get_max_widths(weather_rows, keys)

    # Temperature columns should be wide enough for all values
    assert widths["ʜ°ᴄ"] >= len("14°")
    assert widths["ʟ°ᴄ"] >= len("-1°")  # Make sure negative values are accounted for

    # Test with all left alignment (current implementation)
    alignments_left = ["left"] * len(keys)
    rows_left = [format_row(row, keys, widths, alignments_left) for row in weather_rows]

    # Test with temperature columns right-aligned (potential improvement)
    alignments_mixed = ["left", "right", "right", "left"]
    rows_mixed = [format_row(row, keys, widths, alignments_mixed) for row in weather_rows]

    # Return both for visual inspection
    return {
        "current_left_aligned": "\n".join(rows_left),
        "improved_mixed_aligned": "\n".join(rows_mixed)
    }


def test_calculate_display_width():
    """Test that display width calculation handles special characters properly."""
    # Regular ASCII characters
    assert calculate_display_width("test") == 4

    # With numbers and symbols
    assert calculate_display_width("100%") == 4
    assert calculate_display_width("-5°") == 3

    # With Unicode characters
    assert calculate_display_width("☀") == 1  # Weather icon
    assert calculate_display_width("🌧") == 1  # Emoji width depends on terminal/font


def test_right_alignment_spacing_pattern():
    """Test that right alignment produces the correct spacing pattern for numbers of different lengths."""
    # Test with spaces before single and double-digit numbers
    single_digit = pad_string("5°", 5, "right")
    double_digit = pad_string("25°", 5, "right")
    negative_digit = pad_string("-5°", 5, "right")

    # Print for visual verification

    # With right alignment, single digits should have more leading spaces than double digits
    single_spaces = len(single_digit) - len(single_digit.lstrip())
    double_spaces = len(double_digit) - len(double_digit.lstrip())

    # For numbers of different lengths to be right-aligned:
    # 1. Single digits should have more leading spaces than double digits
    assert single_spaces > double_spaces, "Single digits should have more leading spaces than double digits when right-aligned"

    # 2. The difference in leading spaces should equal the difference in digit count
    # "5°" vs "25°" → difference is 1 character, so should have 1 more space
    assert single_spaces - double_spaces == 1, "Space difference should match digit count difference"

    # 3. Check negative number alignment - digits should align, not the minus sign
    # For proper right alignment, the digit in negative numbers should align with
    # the digit in positive numbers of the same magnitude

    # Using regex to check spacing pattern:
    # We want: `  5°` and ` 25°` and ` -5°` (digits aligned, not minus sign)

    # This pattern checks if the rightmost digit is at the same position from the right
    single_digit_pattern = r"^\s+\d°$"  # spaces followed by single digit and degree
    double_digit_pattern = r"^\s+\d\d°$"  # spaces followed by double digit and degree
    negative_digit_pattern = r"^\s+-\d°$"  # spaces followed by minus, digit, and degree

    assert re.match(single_digit_pattern, single_digit), f"Single digit '{single_digit}' doesn't follow right-alignment pattern"
    assert re.match(double_digit_pattern, double_digit), f"Double digit '{double_digit}' doesn't follow right-alignment pattern"
    assert re.match(negative_digit_pattern, negative_digit), f"Negative digit '{negative_digit}' doesn't follow right-alignment pattern"

    # In a properly right-aligned sequence, the digit position from the right should be consistent
    # For all these numbers with same total space, the digit should be at position 2 from the right
    assert single_digit[-2] == "5", "Digit should be at consistent position from the right"
    assert double_digit[-3] == "2", "First digit of double digit number should be correctly positioned"
    assert negative_digit[-2] == "5", "Digit in negative number should align with positive digits"
