
import pytest
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
