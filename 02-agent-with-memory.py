import asyncio
import os
from agents import Agent, run_demo_loop, FileSearchTool, HostedMCPTool, SQLiteSession
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

from agents import Agent, Runner, SQLiteSession, OpenAIConversationsSession

async def main() -> None:
    # Create agent
    agent = Agent(
        name="Assistant",
        instructions="Reply very concisely.",
    )

    # Create a new conversation
    session = SQLiteSession("user_123", "conversations.db")

    # # First turn
    # result = await Runner.run(
    #     agent,
    #     "Can you remember my favorite city is Kandy...",
    #     session=session
    # )
    # print(result.final_output)

    # Second turn - agent automatically remembers previous context
    result = await Runner.run(
        agent,
        "What is my favourite city",
        session=session
    )

    print(result.final_output)

    result = await Runner.run(
        agent,
        "What's the population?",
        session=session
    )
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())