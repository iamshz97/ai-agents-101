import asyncio
from dotenv import load_dotenv
from agents import Agent, Runner

load_dotenv()


async def main(model: str):
    agent = Agent(
        name="Assistant",
        instructions="You are a weather manager",
    )

    result = await Runner.run(agent, "What's the weather in Tokyo?")
    print(result.final_output)


if __name__ == "__main__":
    # model = "anthropic/claude-sonnet-4-5-20250929"
    asyncio.run(main(""))
