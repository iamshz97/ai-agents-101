import asyncio
import os
from pydantic import BaseModel
from agents import Agent, Runner, trace, HostedMCPTool, FileSearchTool, function_tool, SQLiteSession
from datetime import date
from dotenv import load_dotenv

load_dotenv()

@function_tool
def get_todays_date() -> str:
    """Returns today's date in YYYY-MM-DD format."""
    return date.today().isoformat()

# Agent to check leave policy eligibility
class LeavePolicyOutput(BaseModel):
    eligible: bool
    reason: str

leave_policy_agent = Agent(
    name="leave_policy_agent",
    instructions="Check if the user is eligible for leave as per company policy. Answer with reason if not eligible.",
    output_type=LeavePolicyOutput,
    tools=[
        FileSearchTool(
            max_num_results=3,
            vector_store_ids=["vs_691f69d8c1d481918f716c9bdc82e4a0"],
        )
    ],
)

# Agent to check Google Calendar for important events
class CalendarCheckOutput(BaseModel):
    conflict: bool
    summary: str

calendar_agent = Agent(
    name="calendar_agent",
    instructions="Check if user has important events or entries on the requested leave days using Google Calendar.",
    output_type=CalendarCheckOutput,
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

async def main():
    session = SQLiteSession("leave-calendar-session")
    leave_request = input("What leave dates do you want to check? (e.g. 'Leave on 2025-11-25') ")

    # Ensure the workflow is a single trace
    with trace("Deterministic leave request flow"):
        # Step 1: Check leave eligibility
        policy_result = await Runner.run(
            leave_policy_agent,
            leave_request,
        )
        print("Leave policy checked.")
        assert isinstance(policy_result.final_output, LeavePolicyOutput)
        if not policy_result.final_output.eligible:
            print(f"Decision: Not eligible for leave. Reason: {policy_result.final_output.reason}")
            exit(0)

        print("You are eligible for leave. Checking your calendar for conflicts...")

        # Step 2: Check calendar for conflicts
        calendar_result = await Runner.run(
            calendar_agent,
            leave_request
        )
        assert isinstance(calendar_result.final_output, CalendarCheckOutput)
        if calendar_result.final_output.conflict:
            print(f"Decision: You have an event/conflict: {calendar_result.final_output.summary}. Please consider rescheduling your leave.")
            exit(0)

        print("No major conflicts found in your Google Calendar. You can apply for leave!")

if __name__ == "__main__":
    asyncio.run(main())
