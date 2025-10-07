from google.adk import Agent

from . import prompt

MODEL = "gemini-2.0-flash"

unit_conversion_agent = Agent(
    model=MODEL,
    name="unit_conversion_agent",
    instruction=prompt.UNIT_CONVERSION_PROMPT,
)
