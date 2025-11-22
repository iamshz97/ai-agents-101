import asyncio
import os
from agents import Agent, run_demo_loop, FileSearchTool, HostedMCPTool
from dotenv import load_dotenv

load_dotenv()

taxAgent = Agent(
    name="Leave policy agent",
    instructions="You are a helpful assistant.",
    tools=[
        FileSearchTool(
            max_num_results=3,
            vector_store_ids=["vs_691f69d8c1d481918f716c9bdc82e4a0"],
        )
    ],
)

async def main() -> None:
    await run_demo_loop(taxAgent)

if __name__ == "__main__":
    asyncio.run(main())