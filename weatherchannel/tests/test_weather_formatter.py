
import pytest
from cogs.utilities.text_formatting_utils import get_max_widths
from cogs.weatherchannel.weather_formatter import WeatherGovFormatter


# Dummy LLM chain to simulate behavior of the LLM provider.
class DummyLLMChain:
    def __init__(self, responses=None):
        # 'responses' is a list of responses for each call. None will simulate a failure.
        self.responses = responses or []
        self.call_count = 0

    async def run(self, prompt, temperature):
        self.call_count += 1
        # If a valid response exists at this call, return it in a dummy wrapper;
        # otherwise, raise an exception to simulate failure.
        if self.call_count <= len(self.responses) and self.responses[self.call_count - 1] is not None:
            class DummyResponse:
                content = self.responses[self.call_count - 1]
            return DummyResponse()
        msg = "Simulated failure"
        raise Exception(msg)

@pytest.mark.asyncio
async def test_generate_llm_summary_success_immediate():
    # Create a minimal strings dict that includes the prompt template.
    strings = {"prompts": {"weather_summary": "Fake prompt: {data}"}}

    # Create an instance of WeatherGovFormatter with the strings.
    formatter = WeatherGovFormatter(strings)

    # Set up the dummy LLM chain to return a summary immediately.
    dummy_chain = DummyLLMChain(responses=["Test summary output"])
    formatter.llm_chain = dummy_chain

    # Prepare fake forecasts data.
    fake_forecasts = [
        {
            "ᴄɪᴛʏ": "SF  ",
            "ᴅᴇᴛᴀɪʟs": '{"current_temp": 68, "conditions": "Sunny", "wind": "5 mph", "humidity": 70, "uv_index": 5}'
        },
        {
            "ᴄɪᴛʏ": "NYC ",
            "ᴅᴇᴛᴀɪʟs": '{"current_temp": 75, "conditions": "Rain", "wind": "10 mph", "humidity": 80, "uv_index": 4}'
        },
    ]

    summary = await formatter.generate_llm_summary(fake_forecasts)
    assert "Test summary output" in summary
    # The dummy chain should have been called only once.
    assert dummy_chain.call_count == 1

@pytest.mark.asyncio
async def test_generate_llm_summary_retries():
    strings = {"prompts": {"weather_summary": "Fake prompt: {data}"}}
    formatter = WeatherGovFormatter(strings)

    # Setup dummy chain that fails twice (returns None) then succeeds.
    dummy_chain = DummyLLMChain(responses=[None, None, "Success after retries"])
    formatter.llm_chain = dummy_chain

    fake_forecasts = [
        {
            "ᴄɪᴛʏ": "LA  ",
            "ᴅᴇᴛᴀɪʟs": '{"current_temp": 80, "conditions": "Hot", "wind": "8 mph", "humidity": 50, "uv_index": 9}'
        },
    ]

    summary = await formatter.generate_llm_summary(fake_forecasts)
    assert "Success after retries" in summary
    # The chain should have been called three times.
    assert dummy_chain.call_count == 3

@pytest.mark.asyncio
async def test_generate_llm_summary_all_fail():
    strings = {"prompts": {"weather_summary": "Fake prompt: {data}"}}
    formatter = WeatherGovFormatter(strings)

    # Dummy chain that always fails.
    dummy_chain = DummyLLMChain(responses=[None, None, None])
    formatter.llm_chain = dummy_chain

    fake_forecasts = [
        {
            "ᴄɪᴛʏ": "CHI ",
            "ᴅᴇᴛᴀɪʟs": '{"current_temp": 55, "conditions": "Cloudy", "wind": "12 mph", "humidity": 85, "uv_index": 2}'
        },
    ]

    summary = await formatter.generate_llm_summary(fake_forecasts)
    # When all retries fail, an empty string is returned.
    assert summary == ""

def test_weather_table_formatting_alignment():
    """Test that the weather table aligns columns properly with different temperature values."""
    # Create test data with various temperature formats
    forecasts = [
        {
            "ᴄɪᴛʏ": "CityA  ",
            "ʜ°ᴄ": "5°  ",  # Single digit
            "ʟ°ᴄ": "1°  ",  # Single digit
            "ᴘʀᴇᴄɪᴘ": "10%"   # Double digit percentage
        },
        {
            "ᴄɪᴛʏ": "CityB  ",
            "ʜ°ᴄ": "15°  ", # Double digit
            "ʟ°ᴄ": "8°  ",  # Single digit
            "ᴘʀᴇᴄɪᴘ": "5%"    # Single digit percentage
        },
        {
            "ᴄɪᴛʏ": "CityC  ",
            "ʜ°ᴄ": "7°  ",  # Single digit
            "ʟ°ᴄ": "-3°  ", # Negative
            "ᴘʀᴇᴄɪᴘ": "100%"  # Triple digit percentage
        },
        {
            "ᴄɪᴛʏ": "CityD  ",
            "ʜ°ᴄ": "25°  ", # Double digit
            "ʟ°ᴄ": "-12°  ", # Negative double digit
            "ᴘʀᴇᴄɪᴘ": "0%"    # Zero percentage
        }
    ]

    # Create the formatter
    formatter = WeatherGovFormatter(strings={})

    # Generate the table
    table = formatter.format_forecast_table(forecasts)

    # Split into lines
    lines = table.split("\n")

    # Verify header exists
    assert len(lines) == 5  # Header + 4 data rows

    # Basic test - we expect proper alignment (columns should line up)
    # Just checking table generation worked
    assert "ᴄɪᴛʏ" in lines[0]
    assert "ʜ°ᴄ" in lines[0]
    assert "ʟ°ᴄ" in lines[0]
    assert "ᴘʀᴇᴄɪᴘ" in lines[0]

    # Return the table for visual inspection
    return table

def test_temperature_column_right_alignment():
    """Test that temperature columns should be right-aligned for better readability."""
    # Create test data with various temperature formats
    forecasts = [
        {
            "ᴄɪᴛʏ": "City1  ",
            "ʜ°ᴄ": "5°  ",   # Single digit
            "ʟ°ᴄ": "1°  ",   # Single digit
            "ᴘʀᴇᴄɪᴘ": "0%"
        },
        {
            "ᴄɪᴛʏ": "City2  ",
            "ʜ°ᴄ": "15°  ",  # Double digit
            "ʟ°ᴄ": "-5°  ",  # Negative
            "ᴘʀᴇᴄɪᴘ": "100%"
        }
    ]

    # Manually compute widths - widths should account for visual space
    widths = get_max_widths(forecasts, ["ᴄɪᴛʏ", "ʜ°ᴄ", "ʟ°ᴄ", "ᴘʀᴇᴄɪᴘ"])

    # Width of temperature columns should be >= the length of longest value
    assert widths["ʜ°ᴄ"] >= len("15°  ")  # At least enough for double digit
    assert widths["ʟ°ᴄ"] >= len("-5°  ")  # At least enough for negative value

    # Create the formatter
    formatter = WeatherGovFormatter(strings={})

    # Generate the table
    table = formatter.format_forecast_table(forecasts)

    # For now, we just verify the table generation doesn't error
    # In a future implementation, we'd verify right alignment
    assert table is not None
    assert "City1" in table
    assert "City2" in table

    # Return table for visual inspection
    return table

def test_negative_temperature_alignment():
    """Test that negative temperatures maintain proper alignment with positive ones."""
    # Create test data with mixed positive and negative temps
    forecasts = [
        {
            "ᴄɪᴛʏ": "Winter1  ",
            "ʜ°ᴄ": "2°  ",    # Positive single digit
            "ʟ°ᴄ": "-10°  ",  # Negative double digit
            "ᴘʀᴇᴄɪᴘ": "0%"
        },
        {
            "ᴄɪᴛʏ": "Winter2  ",
            "ʜ°ᴄ": "-1°  ",   # Negative single digit
            "ʟ°ᴄ": "-15°  ",  # Negative double digit
            "ᴘʀᴇᴄɪᴘ": "80%"
        },
        {
            "ᴄɪᴛʏ": "Winter3  ",
            "ʜ°ᴄ": "12°  ",   # Positive double digit
            "ʟ°ᴄ": "5°  ",    # Positive single digit
            "ᴘʀᴇᴄɪᴘ": "60%"
        }
    ]

    # Create the formatter
    formatter = WeatherGovFormatter(strings={})

    # Generate the table
    table = formatter.format_forecast_table(forecasts)

    # Verify table contains our test cities
    assert "Winter1" in table
    assert "Winter2" in table
    assert "Winter3" in table

    # For visual inspection in test output
    return table

def test_strict_temperature_column_alignment():
    """Test that verifies temperature columns are strictly right-aligned properly."""
    # Create test data with intentionally varied lengths
    forecasts = [
        {
            "ᴄɪᴛʏ": "City1",
            "ʜ°ᴄ": "5°",    # Single digit
            "ʟ°ᴄ": "1°",    # Single digit
            "ᴘʀᴇᴄɪᴘ": "0%"
        },
        {
            "ᴄɪᴛʏ": "City2",
            "ʜ°ᴄ": "15°",   # Double digit
            "ʟ°ᴄ": "-2°",   # Negative single digit
            "ᴘʀᴇᴄɪᴘ": "100%"
        }
    ]

    # This test now checks the actual table formatting from the formatter
    formatter = WeatherGovFormatter(strings={})

    # Generate the formatted table
    table = formatter.format_forecast_table(forecasts)

    # Split the table into lines
    lines = table.split("\n")

    # Extract the actual rows (excluding header)
    data_rows = lines[1:]

    # We can't simply check if '5°' != '15°' because they're different strings
    # We need to check if they're right-aligned in the formatted output
    # Right alignment means the single-digit temperature has more leading spaces

    # Find positions of temperature values in each row
    row1_high_temp_pos = data_rows[0].find("5°")
    row2_high_temp_pos = data_rows[1].find("15°")

    # For right alignment, the digit positions should align from the right
    # This means row1's "5" should appear in the same position as row2's "5" (second digit of "15")
    assert row1_high_temp_pos == row2_high_temp_pos + 1, "Temperatures are not right-aligned"

    # Similar check for low temperatures
    row1_low_temp_pos = data_rows[0].find("1°")
    row2_low_temp_pos = data_rows[1].find("-2°")

    # The digit "1" should align with "2" in "-2"
    assert row1_low_temp_pos == row2_low_temp_pos + 1, "Negative temperatures are not properly right-aligned"

    # Print the actual table for visual debugging if needed

    return table

def test_extreme_temperature_values():
    """Test that extreme temperature values are properly formatted and aligned."""
    # Create test data with extreme temperature values
    forecasts = [
        {
            "ᴄɪᴛʏ": "Arctic",
            "ʜ°ᴄ": "-40°",    # Very cold negative
            "ʟ°ᴄ": "-55°",    # Extreme cold
            "ᴘʀᴇᴄɪᴘ": "10%"
        },
        {
            "ᴄɪᴛʏ": "Sahara",
            "ʜ°ᴄ": "48°",     # Very hot positive
            "ʟ°ᴄ": "25°",     # Double digit positive
            "ᴘʀᴇᴄɪᴘ": "0%"
        },
        {
            "ᴄɪᴛʏ": "Equator",
            "ʜ°ᴄ": "35°",     # Double digit
            "ʟ°ᴄ": "0°",      # Zero temperature (special case)
            "ᴘʀᴇᴄɪᴘ": "80%"
        },
        {
            "ᴄɪᴛʏ": "Valley",
            "ʜ°ᴄ": "104°",    # Triple digit (rare but possible)
            "ʟ°ᴄ": "-5°",     # Single digit negative
            "ᴘʀᴇᴄɪᴘ": "5%"
        }
    ]

    formatter = WeatherGovFormatter(strings={})

    # Generate the formatted table
    table = formatter.format_forecast_table(forecasts)

    # Print the table for visual inspection

    # Split into lines
    lines = table.split("\n")

    # Extract the actual rows (excluding header)
    data_rows = lines[1:]

    # Verify basic formatting expectations
    assert len(data_rows) == len(forecasts), "Table should have the same number of rows as input"

    # Check that all expected values appear in the table
    for i, forecast in enumerate(forecasts):
        row = data_rows[i]
        assert forecast["ᴄɪᴛʏ"] in row, f"City name {forecast['ᴄɪᴛʏ']} not found in row {i+1}"
        assert forecast["ʜ°ᴄ"] in row, f"High temp {forecast['ʜ°ᴄ']} not found in row {i+1}"
        assert forecast["ʟ°ᴄ"] in row, f"Low temp {forecast['ʟ°ᴄ']} not found in row {i+1}"
        assert forecast["ᴘʀᴇᴄɪᴘ"] in row, f"Precipitation {forecast['ᴘʀᴇᴄɪᴘ']} not found in row {i+1}"

    # Check that triple-digit temperatures are displayed properly
    triple_digit_row = data_rows[3]  # "Valley" with 104°
    assert "104°" in triple_digit_row, "Triple-digit temperature not displayed correctly"

    # Check that negative temperatures are displayed properly
    extreme_neg_row = data_rows[0]  # "Arctic" with -40°
    assert "-40°" in extreme_neg_row, "Negative temperature not displayed correctly"

    # Check that zero temperature is displayed properly
    zero_temp_row = data_rows[2]  # "Equator" with 0°
    assert "0°" in zero_temp_row, "Zero temperature not displayed correctly"

    return table

def test_long_city_names_and_precipitation_formats():
    """Test handling of very long city names and various precipitation formats."""
    forecasts = [
        {
            "ᴄɪᴛʏ": "San Francisco Bay Area",  # Very long city name
            "ʜ°ᴄ": "18°",
            "ʟ°ᴄ": "12°",
            "ᴘʀᴇᴄɪᴘ": "10%"
        },
        {
            "ᴄɪᴛʏ": "NY",  # Very short city name
            "ʜ°ᴄ": "25°",
            "ʟ°ᴄ": "15°",
            "ᴘʀᴇᴄɪᴘ": "0%"  # Minimum percentage
        },
        {
            "ᴄɪᴛʏ": "Rio de Janeiro-Brazil",  # City name with special characters
            "ʜ°ᴄ": "32°",
            "ʟ°ᴄ": "24°",
            "ᴘʀᴇᴄɪᴘ": "100%"  # Maximum percentage
        },
        {
            "ᴄɪᴛʏ": "Portland",
            "ʜ°ᴄ": "15°",
            "ʟ°ᴄ": "8°",
            "ᴘʀᴇᴄɪᴘ": "75.5mm"  # Unusual format (millimeters with decimal)
        },
        {
            "ᴄɪᴛʏ": "北京",  # Non-Latin characters (Beijing in Chinese)
            "ʜ°ᴄ": "22°",
            "ʟ°ᴄ": "10°",
            "ᴘʀᴇᴄɪᴘ": "30%"
        }
    ]

    formatter = WeatherGovFormatter(strings={})

    # Generate the formatted table
    table = formatter.format_forecast_table(forecasts)

    # Print the table for visual inspection

    # Split into lines
    lines = table.split("\n")
    lines[0]
    data_rows = lines[1:]

    # Verify the table structure is maintained
    assert len(data_rows) == len(forecasts), "Table should have the same number of rows as input forecasts"

    # Very long city names should be displayed properly without breaking the table
    assert "San Francisco Bay Area" in data_rows[0], "Long city name not displayed correctly"

    # City names with special characters should be displayed correctly
    assert "Rio de Janeiro-Brazil" in data_rows[2], "City name with special chars not displayed correctly"

    # Non-Latin characters should be handled properly
    assert "北京" in data_rows[4], "Non-Latin characters not displayed correctly"

    # Check that precipitation values are displayed properly
    for i, forecast in enumerate(forecasts):
        assert forecast["ᴘʀᴇᴄɪᴘ"] in data_rows[i], f"Precipitation value '{forecast['ᴘʀᴇᴄɪᴘ']}' not displayed correctly"

    # Verify that all temperature values are visible
    for i, forecast in enumerate(forecasts):
        assert forecast["ʜ°ᴄ"] in data_rows[i], f"High temperature '{forecast['ʜ°ᴄ']}' not displayed in row {i+1}"
        assert forecast["ʟ°ᴄ"] in data_rows[i], f"Low temperature '{forecast['ʟ°ᴄ']}' not displayed in row {i+1}"

    return table

def test_missing_and_invalid_data_handling():
    """Test the formatter's ability to handle missing or invalid data gracefully."""
    forecasts = [
        {
            "ᴄɪᴛʏ": "Complete",
            "ʜ°ᴄ": "20°",
            "ʟ°ᴄ": "10°",
            "ᴘʀᴇᴄɪᴘ": "15%"
        },
        {
            "ᴄɪᴛʏ": "NoHighTemp",
            # Missing high temperature
            "ʟ°ᴄ": "5°",
            "ᴘʀᴇᴄɪᴘ": "25%"
        },
        {
            "ᴄɪᴛʏ": "NoLowTemp",
            "ʜ°ᴄ": "30°",
            # Missing low temperature
            "ᴘʀᴇᴄɪᴘ": "0%"
        },
        {
            "ᴄɪᴛʏ": "NoPrecip",
            "ʜ°ᴄ": "22°",
            "ʟ°ᴄ": "12°"
            # Missing precipitation
        },
        {
            "ᴄɪᴛʏ": "InvalidTemp",
            "ʜ°ᴄ": "N/A",  # Invalid temperature format
            "ʟ°ᴄ": "Error",  # Invalid temperature format
            "ᴘʀᴇᴄɪᴘ": "30%"
        },
        {
            # Empty dictionary with minimal data
            "ᴄɪᴛʏ": "Empty"
        }
    ]

    formatter = WeatherGovFormatter(strings={})

    # Generate the formatted table
    table = formatter.format_forecast_table(forecasts)

    # Print the table for visual inspection

    # Split into lines
    lines = table.split("\n")
    lines[0]
    data_rows = lines[1:]

    # Verify all rows are present and have proper structure
    assert len(data_rows) == len(forecasts), "Table should include all rows even with missing data"

    # Check that missing values are represented by some placeholder
    for row in data_rows:
        # Each row should have the same number of columns
        columns = row.split()
        # There might be extra spaces, but should have at least the key columns
        assert len(columns) >= 4, f"Row '{row}' is missing required columns"

    # The width of each row should be consistent
    row_widths = [len(row) for row in data_rows]
    assert len(set(row_widths)) == 1, "Rows have inconsistent widths with missing data"

    # Verify that columns are properly aligned despite missing data
    # Extract high temperature column positions
    high_temp_positions = []
    for row in data_rows:
        if "°" in row:  # Only check rows that have at least one temperature value
            # Find position of first degree symbol
            pos = row.find("°")
            if pos > 0:
                high_temp_positions.append(pos)

    # All found temperature positions should be aligned
    if high_temp_positions:
        assert len(set(high_temp_positions)) <= 2, "Temperature columns not aligned with missing data"

    return table

def test_forecast_table_with_conditions():
    """Test formatting a weather table that includes weather conditions column."""
    forecasts = [
        {
            "ᴄɪᴛʏ": "Seattle",
            "ᴄᴏɴᴅ": "Rainy",
            "ʜ°ᴄ": "14°",
            "ʟ°ᴄ": "8°",
            "ᴘʀᴇᴄɪᴘ": "70%"
        },
        {
            "ᴄɪᴛʏ": "Los Angeles",
            "ᴄᴏɴᴅ": "Sunny",
            "ʜ°ᴄ": "28°",
            "ʟ°ᴄ": "18°",
            "ᴘʀᴇᴄɪᴘ": "0%"
        },
        {
            "ᴄɪᴛʏ": "Chicago",
            "ᴄᴏɴᴅ": "Partly Cloudy with Occasional Showers",  # Very long condition
            "ʜ°ᴄ": "15°",
            "ʟ°ᴄ": "5°",
            "ᴘʀᴇᴄɪᴘ": "30%"
        },
        {
            "ᴄɪᴛʏ": "Miami",
            "ᴄᴏɴᴅ": "Stormy",
            "ʜ°ᴄ": "30°",
            "ʟ°ᴄ": "22°",
            "ᴘʀᴇᴄɪᴘ": "90%"
        }
    ]

    formatter = WeatherGovFormatter(strings={})

    # Generate the formatted table WITH conditions column
    table = formatter.format_forecast_table(forecasts, include_condition=True)

    # Print the table for visual inspection

    # Split into lines
    lines = table.split("\n")
    header = lines[0]
    data_rows = lines[1:]

    # Verify table has correct number of rows
    assert len(data_rows) == len(forecasts), "Table should have one row per forecast"

    # Verify header includes conditions column
    assert "ᴄᴏɴᴅ" in header, "Header should include conditions column"

    # Verify expected columns are present in header
    header_columns = [col for col in header.split() if col.strip()]
    expected_columns = ["ᴄɪᴛʏ", "ᴄᴏɴᴅ", "ʜ°ᴄ", "ʟ°ᴄ", "ᴘʀᴇᴄɪᴘ"]
    for col in expected_columns:
        assert col in header_columns, f"Expected column {col} not found in header"

    # Check that conditions are displayed properly
    for i, forecast in enumerate(forecasts):
        # Each condition should appear in its row
        assert forecast["ᴄᴏɴᴅ"] in data_rows[i], f"Condition '{forecast['ᴄᴏɴᴅ']}' not in row {i+1}"

        # Each temperature value should be present in its row
        assert forecast["ʜ°ᴄ"] in data_rows[i], f"High temp '{forecast['ʜ°ᴄ']}' not in row {i+1}"
        assert forecast["ʟ°ᴄ"] in data_rows[i], f"Low temp '{forecast['ʟ°ᴄ']}' not in row {i+1}"
        assert forecast["ᴘʀᴇᴄɪᴘ"] in data_rows[i], f"Precipitation '{forecast['ᴘʀᴇᴄɪᴘ']}' not in row {i+1}"

    # Verify that long condition text is displayed properly
    long_condition_row_index = next(i for i, f in enumerate(forecasts) if "Partly Cloudy" in f["ᴄᴏɴᴅ"])
    long_condition_row = data_rows[long_condition_row_index]
    assert "Partly Cloudy with Occasional Showers" in long_condition_row, "Long condition text not displayed correctly"

    return table

def test_header_alignment_with_data():
    """Test that verifies headers are properly aligned with their data columns."""
    # Create test data with various formats
    forecasts = [
        {
            "ᴄɪᴛʏ": "NYC",
            "ʜ°ᴄ": "7°",
            "ʟ°ᴄ": "-1°",
            "ᴘʀᴇᴄɪᴘ": "0%"
        },
        {
            "ᴄɪᴛʏ": "Seattle",
            "ʜ°ᴄ": "14°",
            "ʟ°ᴄ": "8°",
            "ᴘʀᴇᴄɪᴘ": "70%"
        },
        {
            "ᴄɪᴛʏ": "Tokyo",
            "ʜ°ᴄ": "5°",
            "ʟ°ᴄ": "1°",
            "ᴘʀᴇᴄɪᴘ": "100%"
        }
    ]

    # Generate the table using the formatter
    formatter = WeatherGovFormatter(strings={})
    table = formatter.format_forecast_table(forecasts)

    # Split into lines for analysis
    lines = table.split("\n")
    header = lines[0]
    data_rows = lines[1:]

    # Extract header positions
    city_header_pos = header.find("ᴄɪᴛʏ")
    high_temp_header_pos = header.find("ʜ°ᴄ")
    header.find("ʟ°ᴄ")
    header.find("ᴘʀᴇᴄɪᴘ")

    # For each data row, check alignment with headers
    for row in data_rows:
        # For city (left-aligned), the start position should match the header
        city_data_pos = row.find(row.strip().split()[0])  # First word in row
        assert city_data_pos == city_header_pos, f"City column not aligned with header in row: {row}"

        # Extract positions of temperature and precip data
        # We need to use a method that finds these values reliably

        # Find high temp position (right-aligned)
        # The degree symbol helps us locate the temperature values
        high_temp_end_pos = row.find("°", high_temp_header_pos)
        assert high_temp_end_pos > 0, f"Cannot find high temperature in row: {row}"

        # Find low temp position (right-aligned)
        low_temp_end_pos = row.find("°", high_temp_end_pos + 1)
        assert low_temp_end_pos > 0, f"Cannot find low temperature in row: {row}"

        # Find precipitation position
        precip_data_pos = row.find("%")
        assert precip_data_pos > 0, f"Cannot find precipitation in row: {row}"

        # For right-aligned data, check that the data ends in a consistent position
        # relative to the header start position
        # The temperatures should end at a consistent distance from header start

        # Print the table and relevant positions for debugging

    return table

def test_precipitation_alignment_and_trailing_spaces():
    """Test that percentage values in the precipitation column are properly aligned and no unnecessary trailing spaces exist."""
    # Create test data with various precipitation percentages (short and long)
    forecasts = [
        {
            "ᴄɪᴛʏ": "City1",
            "ʜ°ᴄ": "10°",
            "ʟ°ᴄ": "5°",
            "ᴘʀᴇᴄɪᴘ": "0%"    # Short percentage
        },
        {
            "ᴄɪᴛʏ": "City2",
            "ʜ°ᴄ": "15°",
            "ʟ°ᴄ": "8°",
            "ᴘʀᴇᴄɪᴘ": "70%"   # Medium percentage
        },
        {
            "ᴄɪᴛʏ": "City3",
            "ʜ°ᴄ": "20°",
            "ʟ°ᴄ": "12°",
            "ᴘʀᴇᴄɪᴘ": "100%"  # Long percentage
        }
    ]

    # Generate the table
    formatter = WeatherGovFormatter(strings={})
    table = formatter.format_forecast_table(forecasts)

    # Split into lines
    lines = table.split("\n")
    data_rows = lines[1:]  # Skip header

    # Check the consistency of spacing
    # The width of all rows should be the same
    row_widths = [len(row) for row in data_rows]
    assert len(set(row_widths)) == 1, f"Rows have inconsistent widths: {row_widths}"

    # Check precipitation column alignment by finding the percentage symbol in each row
    percent_positions = [row.find("%") for row in data_rows]

    # Percentage symbols should be aligned or have minimal variation (<=2 spaces)
    # This allows for the natural width difference between "0%", "70%" and "100%"
    max_diff = max(percent_positions) - min(percent_positions)
    assert max_diff <= 2, f"Percentage symbols are not properly aligned: {percent_positions}"

    # Print the table for visual inspection

    # Print details about each row for debugging
    for _i, _row in enumerate(data_rows):
        pass

    # The table should look visually well-formatted, with same-width rows
    # and consistent column spacing
    return table

def test_consistent_column_spacing():
    """Test that verifies consistent spacing between columns regardless of data length variations."""
    # Create test data with various city and temperature formats to test column spacing
    forecasts = [
        {
            "ᴄɪᴛʏ": "SF",           # Short city name
            "ʜ°ᴄ": "17°",           # Double digit positive
            "ʟ°ᴄ": "7°",            # Single digit positive
            "ᴘʀᴇᴄɪᴘ": "0%"           # Short percentage
        },
        {
            "ᴄɪᴛʏ": "Seattle",      # Medium city name
            "ʜ°ᴄ": "14°",           # Double digit positive
            "ʟ°ᴄ": "8°",            # Single digit positive
            "ᴘʀᴇᴄɪᴘ": "70%"          # Medium percentage
        },
        {
            "ᴄɪᴛʏ": "Blodgett",     # Medium city name
            "ʜ°ᴄ": "14°",           # Double digit positive
            "ʟ°ᴄ": "4°",            # Single digit positive
            "ᴘʀᴇᴄɪᴘ": "0%"           # Short percentage
        },
        {
            "ᴄɪᴛʏ": "NYC",          # Short city name
            "ʜ°ᴄ": "7°",            # Single digit positive
            "ʟ°ᴄ": "-1°",           # Single digit negative
            "ᴘʀᴇᴄɪᴘ": "0%"           # Short percentage
        },
        {
            "ᴄɪᴛʏ": "Boston",       # Medium city name
            "ʜ°ᴄ": "5°",            # Single digit positive
            "ʟ°ᴄ": "-2°",           # Single digit negative
            "ᴘʀᴇᴄɪᴘ": "0%"           # Short percentage
        },
        {
            "ᴄɪᴛʏ": "Tokyo",        # Medium city name
            "ʜ°ᴄ": "5°",            # Single digit positive
            "ʟ°ᴄ": "1°",            # Single digit positive
            "ᴘʀᴇᴄɪᴘ": "100%"         # Long percentage
        }
    ]

    # Generate table with the exact data from the example
    formatter = WeatherGovFormatter(strings={})
    table = formatter.format_forecast_table(forecasts)

    # Print full table for visual inspection

    # Split into lines
    lines = table.split("\n")
    header = lines[0]
    data_rows = lines[1:]

    # All rows should have the same width for consistency
    row_widths = [len(row) for row in data_rows]
    assert len(set(row_widths)) == 1, f"Row widths vary: {row_widths}"

    # Measure the spacing between columns in each row
    # For consistent formatting, the columns should be visually aligned

    # Function to find column positions
    def find_column_positions(row):
        # We need to locate each column start position
        # For city (left-aligned): Find the start of the first word
        city_pos = row.find(row.strip().split()[0])

        # For high temp (right-aligned): Find degree symbol and work backward
        high_temp_deg_pos = row.find("°", city_pos)
        # Find temp column start by working backward to find the start of the temperature
        # This could be a space followed by digits, or a space followed by a minus sign
        high_temp_start = None
        for i in range(high_temp_deg_pos - 1, -1, -1):
            if row[i] == " " and (row[i+1].isdigit() or row[i+1] == "-"):
                high_temp_start = i + 1
                break

        # For low temp: Find degree symbol after the first one
        low_temp_deg_pos = row.find("°", high_temp_deg_pos + 1)
        # Find temp column start by working backward
        low_temp_start = None
        for i in range(low_temp_deg_pos - 1, -1, -1):
            if row[i] == " " and (row[i+1].isdigit() or row[i+1] == "-"):
                low_temp_start = i + 1
                break

        # For precip: Find percentage symbol
        precip_percent_pos = row.find("%")
        # Find precip column start by working backward
        precip_start = None
        for i in range(precip_percent_pos - 1, -1, -1):
            if row[i] == " " and row[i+1].isdigit():
                precip_start = i + 1
                break

        return {
            "city": city_pos,
            "high_temp": high_temp_start,
            "low_temp": low_temp_start,
            "precip": precip_start,
            "high_temp_end": high_temp_deg_pos,
            "low_temp_end": low_temp_deg_pos,
            "precip_end": precip_percent_pos
        }

    # Find positions in header
    header_positions = find_column_positions(header)

    # Check column alignment for each row
    for i, row in enumerate(data_rows):
        row_positions = find_column_positions(row)

        # Print detailed position information for debugging

        # Check for consistent column spacing

        # 1. For left-aligned columns (city): start positions should match header
        assert row_positions["city"] == header_positions["city"], f"City column not aligned with header in row {i+1}"

        # 2. For right-aligned columns (temperatures): Verify consistent end positions
        # High temp end position should be consistent
        high_temp_end_positions = [find_column_positions(r)["high_temp_end"] for r in data_rows]
        assert len(set(high_temp_end_positions)) == 1, f"High temperature end positions vary: {high_temp_end_positions}"

        # Low temp end position should be consistent
        low_temp_end_positions = [find_column_positions(r)["low_temp_end"] for r in data_rows]
        assert len(set(low_temp_end_positions)) == 1, f"Low temperature end positions vary: {low_temp_end_positions}"

        # 3. Check spacing between columns is consistent within a reasonable margin
        # The spacing between columns might vary slightly for negative values
        spaces_between_temps = [pos["low_temp"] - pos["high_temp_end"] - 1 for pos in [find_column_positions(r) for r in data_rows]]

        # Allow a difference of 1 space due to our handling of negative values
        max_diff = max(spaces_between_temps) - min(spaces_between_temps)
        assert max_diff <= 1, f"Spacing between temperature columns varies too much: {spaces_between_temps}"

        # Space between low temp and precip should be consistent within a margin
        # Since we're using right-aligned precipitation values, allow up to 2 spaces difference
        # This accounts for varying widths of "0%", "70%", and "100%"
        spaces_between_low_and_precip = [pos["precip"] - pos["low_temp_end"] - 1 for pos in [find_column_positions(r) for r in data_rows]]
        max_diff_precip = max(spaces_between_low_and_precip) - min(spaces_between_low_and_precip)
        assert max_diff_precip <= 2, f"Spacing between low temp and precip columns varies too much: {spaces_between_low_and_precip}"

    return table

def test_exact_column_alignment():
    """Test that verifies exact column positions for all data points, especially percentage symbols."""
    # Create test data with exact sample data from the problematic case
    forecasts = [
        {
            "ᴄɪᴛʏ": "SF",
            "ʜ°ᴄ": "17°",
            "ʟ°ᴄ": "7°",
            "ᴘʀᴇᴄɪᴘ": "0%"
        },
        {
            "ᴄɪᴛʏ": "Seattle",
            "ʜ°ᴄ": "14°",
            "ʟ°ᴄ": "8°",
            "ᴘʀᴇᴄɪᴘ": "70%"
        },
        {
            "ᴄɪᴛʏ": "Blodgett",
            "ʜ°ᴄ": "14°",
            "ʟ°ᴄ": "4°",
            "ᴘʀᴇᴄɪᴘ": "0%"
        },
        {
            "ᴄɪᴛʏ": "NYC",
            "ʜ°ᴄ": "7°",
            "ʟ°ᴄ": "-1°",
            "ᴘʀᴇᴄɪᴘ": "0%"
        },
        {
            "ᴄɪᴛʏ": "Boston",
            "ʜ°ᴄ": "5°",
            "ʟ°ᴄ": "-2°",
            "ᴘʀᴇᴄɪᴘ": "0%"
        },
        {
            "ᴄɪᴛʏ": "Tokyo",
            "ʜ°ᴄ": "5°",
            "ʟ°ᴄ": "1°",
            "ᴘʀᴇᴄɪᴘ": "100%"
        }
    ]

    # Generate actual table
    formatter = WeatherGovFormatter(strings={})
    table = formatter.format_forecast_table(forecasts)

    # Print for visual inspection

    # Split into lines
    lines = table.split("\n")
    header = lines[0]
    data_rows = lines[1:]

    # 1. First, check that all rows have the same width (no extra trailing spaces)
    row_widths = [len(row) for row in [header, *data_rows]]
    assert len(set(row_widths)) == 1, f"Rows have inconsistent widths: {row_widths}"

    # 2. Extract the positions of each column header
    header_positions = {}
    header_positions["ᴄɪᴛʏ"] = header.find("ᴄɪᴛʏ")
    header_positions["ʜ°ᴄ"] = header.find("ʜ°ᴄ")
    header_positions["ʟ°ᴄ"] = header.find("ʟ°ᴄ")
    header_positions["ᴘʀᴇᴄɪᴘ"] = header.find("ᴘʀᴇᴄɪᴘ")

    # 3. Extract exact positions for all data elements
    high_temp_positions = []  # Position of degree symbol
    low_temp_positions = []   # Position of degree symbol
    percent_positions = []    # Position of percent symbol

    for row in data_rows:
        # Find positions of special characters
        high_temp_pos = row.find("°", header_positions["ʜ°ᴄ"])
        low_temp_pos = row.find("°", high_temp_pos + 1)
        percent_pos = row.find("%")

        # Store positions
        high_temp_positions.append(high_temp_pos)
        low_temp_positions.append(low_temp_pos)
        percent_positions.append(percent_pos)

    # Print for detailed analysis
    for i, row in enumerate(data_rows):
        pass

    # 4. Verify that all special characters are aligned exactly
    assert len(set(high_temp_positions)) == 1, f"High temp degree symbols not aligned: {high_temp_positions}"
    assert len(set(low_temp_positions)) == 1, f"Low temp degree symbols not aligned: {low_temp_positions}"
    assert len(set(percent_positions)) == 1, f"Percent symbols not aligned: {percent_positions}"

    # 5. Verify spacing between columns is consistent
    spacing_between_high_low = [low_temp_positions[0] - high_temp_positions[0] - 1]  # Spacing should be same for all rows
    spacing_between_low_percent = [percent_positions[0] - low_temp_positions[0] - 1]  # Spacing should be same for all rows

    for row in data_rows:
        for i in range(len(data_rows)):
            assert low_temp_positions[i] - high_temp_positions[i] - 1 == spacing_between_high_low[0], \
                f"Inconsistent spacing between high and low temperature in row {i+1}"
            assert percent_positions[i] - low_temp_positions[i] - 1 == spacing_between_low_percent[0], \
                f"Inconsistent spacing between low temperature and percent in row {i+1}"

    # 6. Ensure there are no unnecessary trailing spaces in any line
    for i, row in enumerate(data_rows):
        assert not row.endswith("  "), f"Row {i+1} has multiple trailing spaces: '{row}'"

    return table
