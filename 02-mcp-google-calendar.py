import asyncio
import os
from agents import Agent, Runner, HostedMCPTool, function_tool, SQLiteSession, run_demo_loop
from dotenv import load_dotenv
from datetime import date

load_dotenv()

@function_tool
def get_todays_date() -> str:
    """Returns today's date in YYYY-MM-DD format."""
    return date.today().isoformat()

calendarAgent = Agent(
    name="Google calendar manager agent",
    instructions="Make sure you know the right date and You have to access the google calendar and answer for questions i have doubt regarding with.",
    tools=[
        get_todays_date,
        HostedMCPTool(
            tool_config={
                "type": "mcp",
                "server_label": "google_calendar",
                "connector_id": "connector_googlecalendar",
                "authorization": os.environ["GOOGLE_CALENDAR_AUTHORIZATION"],
                "require_approval": "never",
            }
        )
    ],
)

async def main() -> None:
    await run_demo_loop(calendarAgent)

if __name__ == "__main__":
    asyncio.run(main())