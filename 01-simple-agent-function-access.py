import asyncio
import os
from dotenv import load_dotenv
from agents import Agent, ModelSettings, Runner, function_tool, set_tracing_disabled
from agents.extensions.models.litellm_model import LitellmModel
from pydantic import BaseModel, Field
from agents import Agent, FileSearchTool, Runner, WebSearchTool
from agents.extensions.models.litellm_model import LitellmModel

load_dotenv()

@function_tool
def get_weather(city: str) -> str:
    """returns weather info for the specified city."""
    return f"The weather in {city} is sunny"

async def main(model: str):
    agent = Agent(
        name="Assistant",
        instructions="You are a weather manager reply me",
        model=LitellmModel(model=model),
        tools=[get_weather],
    )

    result = await Runner.run(agent, "What's the weather in Tokyo?")
    print(result.final_output)


if __name__ == "__main__":
    model = "anthropic/claude-sonnet-4-5-20250929"
    asyncio.run(main(model))