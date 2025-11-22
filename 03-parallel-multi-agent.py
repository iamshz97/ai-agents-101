import asyncio
import os
from pydantic import BaseModel
from agents import Agent, Runner, trace, HostedMCPTool, FileSearchTool, function_tool, ItemHelpers
from datetime import date
from dotenv import load_dotenv

load_dotenv()

@function_tool
def get_todays_date() -> str:
    """Returns today's date in YYYY-MM-DD format."""
    return date.today().isoformat()

class LeavePolicyOutput(BaseModel):
    eligible: bool
    reason: str

leave_policy_agent = Agent(
    name="leave_policy_agent",
    instructions="Check if the user is eligible for leave as per company policy.",
    output_type=LeavePolicyOutput,
    tools=[
        FileSearchTool(
            max_num_results=3,
            vector_store_ids=["vs_691f69d8c1d481918f716c9bdc82e4a0"],
        )
    ],
)

class CalendarCheckOutput(BaseModel):
    conflict: bool
    summary: str

calendar_agent = Agent(
    name="calendar_agent",
    instructions="Check Google Calendar for important events on leave dates.",
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
        ),
    ],
)

decision_agent = Agent(
    name="decision_agent",
    instructions="Given outputs from the leave policy agent and calendar agent, decide if leave should be approved and explain why.",
)

async def main():
    leave_request = input("What leave dates do you want to check? (e.g. 'Leave on 2025-11-25') ")

    with trace("Parallel leave eligibility & calendar check"):
        # Run both agents in parallel
        policy_future, calendar_future = await asyncio.gather(
            Runner.run(leave_policy_agent, leave_request),
            Runner.run(calendar_agent, leave_request),
        )

        # Format outputs for decision agent
        policy_output = ItemHelpers.text_message_outputs(policy_future.new_items)
        calendar_output = ItemHelpers.text_message_outputs(calendar_future.new_items)
        combined_prompt = (
            f"Leave request: {leave_request}\n\n"
            f"Policy check:\n{policy_output}\n\n"
            f"Calendar check:\n{calendar_output}\n\n"
            "Please decide and explain if leave can be approved."
        )

        final_decision = await Runner.run(decision_agent, combined_prompt)
        print("\n\n-----\n")
        print(f"Decision Agent: {final_decision.final_output}")

if __name__ == "__main__":
    asyncio.run(main())
