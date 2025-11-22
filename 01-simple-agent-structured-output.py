import asyncio
import os
from dotenv import load_dotenv
from agents import Agent, ModelSettings, Runner, function_tool, set_tracing_disabled
from agents.extensions.models.litellm_model import LitellmModel
from pydantic import BaseModel, Field
from agents import Agent, FileSearchTool, Runner, WebSearchTool

load_dotenv()

class WeatherResponse(BaseModel):
    city: str
    forecast: str = Field(description="A brief weather forecast in haiku form.")
    country: str
    temperature: float = Field(description="Temp in Farenhite")

async def main(model: str):
    agent = Agent(
        name="Assistant",
        instructions="You are a weather manager",
        model="gpt-4.1",
        output_type=WeatherResponse,
        tools=[
         WebSearchTool(),
        ]
    )

    result = await Runner.run(agent, "What's the weather in Tokyo?")
    print(result.final_output)


if __name__ == "__main__":
    # model = "anthropic/claude-sonnet-4-5-20250929"
    asyncio.run(main(''))