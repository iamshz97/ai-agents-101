import asyncio
import os
from agents import (
    Agent,
    HandoffOutputItem,
    ItemHelpers,
    MessageOutputItem,
    Runner,
    SQLiteSession,
    ToolCallItem,
    ToolCallOutputItem,
    WebSearchTool,
    function_tool,
    trace,
)
from dotenv import load_dotenv
from datetime import date, datetime, timedelta
from agents.mcp import MCPServerStdio
from pydantic import BaseModel
from typing import Optional, Dict, List

load_dotenv()

RECOMMENDED_PROMPT_PREFIX = """You have access to handoff tools, which let you delegate requests to other agents specialized in specific areas. Always consider whether another agent would be better suited to handle the user's request."""


# ============== USER PROFILE & CONTEXT ==============

USER_ROUTINE = {
    "daily": {
        "gym": "7:00 PM - 9:00 PM every weekday",
        "commute": "Take train to office from Kandy at 7:00 AM, return at 6:00 PM",
    },
    "preferences": {
        "location": "Kandy",
        "saloon": "Kumara Weediya",
        "shopping": "Arpico",
    },
    "work_schedule": {
        "office_hours": "9:00 AM - 5:00 PM on weekdays",
        "location": "Colombo (via train from Kandy)",
    },
}

context_storage = {
    "questions_asked": 0,
    "max_questions": 3,
    "conflicts_detected": [],
    "plan_approved": False,
}


@function_tool
def get_todays_date() -> str:
    """Returns today's date in YYYY-MM-DD format."""
    return date.today().isoformat()


@function_tool
def get_user_routine() -> Dict:
    """Get the user's daily routine and preferences."""
    return USER_ROUTINE


@function_tool
def save_event_context(key: str, value: str) -> str:
    """Save event-specific information."""
    context_storage[key] = value
    return f"Saved: {key}"


@function_tool
def get_event_context(key: str) -> Optional[str]:
    """Get saved event context."""
    return context_storage.get(key)


@function_tool
def increment_questions() -> int:
    """Track number of questions asked to user."""
    context_storage["questions_asked"] = context_storage.get("questions_asked", 0) + 1
    return context_storage["questions_asked"]


@function_tool
def can_ask_more_questions() -> bool:
    """Check if we can still ask user questions."""
    asked = context_storage.get("questions_asked", 0)
    max_q = context_storage.get("max_questions", 3)
    return asked < max_q


class PlanningContext(BaseModel):
    event_type: str | None = None
    event_date: str | None = None
    has_conflicts: bool = False
    conflicts_resolved: bool = False
    plan_created: bool = False


async def main() -> None:
    context = PlanningContext()

    async with MCPServerStdio(
        name="GoogleCalendar",
        params={
            "command": "npx",
            "args": ["-y", "@cocal/google-calendar-mcp"],
            "env": {
                "GOOGLE_OAUTH_CREDENTIALS": os.getenv(
                    "GOOGLE_OAUTH_CREDENTIALS_PATH", "gcp-oauth.keys.json"
                )
            },
        },
    ) as calendar_server:

        conflict_checker_agent = Agent(
            name="ConflictChecker",
            handoff_description="Checks user's calendar for scheduling conflicts with the new event.",
            instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
            
            You check for calendar conflicts when a user mentions an upcoming event.
            
            WORKFLOW:
            1. Extract the event date/time from user's message
            2. Use list-events tool to check Google Calendar for existing events on that date range
            3. Also check against user's routine: {USER_ROUTINE}
            4. Identify any conflicts:
               - Existing calendar events
               - Gym time (7-9 PM weekdays)
               - Train commute times (7 AM departure, 6 PM return)
               - Work hours (9 AM - 5 PM weekdays)
            
            If conflicts found:
            - List all conflicts with specific times
            - Hand off to NegotiatorAgent to resolve them
            
            If no conflicts:
            - Confirm calendar is clear
            - Hand off directly to PlannerAgent
            
            ALWAYS use the calendar tools to check actual events!""",
            tools=[get_todays_date, get_user_routine, save_event_context],
            mcp_servers=[calendar_server],
            model="gpt-4o-mini",
        )

        negotiator_agent = Agent(
            name="NegotiatorAgent",
            handoff_description="Negotiates and resolves calendar conflicts with the user.",
            instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
            
            You help resolve scheduling conflicts.
            
            WORKFLOW:
            1. Present conflicts clearly to the user
            2. Suggest alternatives:
               - Reschedule existing events (use update-event)
               - Adjust timing
               - Skip non-critical activities (e.g., gym once)
            3. Get user's decision on resolution
            4. Save the resolution strategy
            5. Hand off to PlannerAgent once conflicts are resolved
            
            Be solution-oriented. Only ask 1-2 questions to resolve.""",
            tools=[save_event_context, get_event_context, get_user_routine],
            mcp_servers=[calendar_server],
            model="gpt-4o-mini",
        )

        planner_agent = Agent(
            name="PlannerAgent",
            handoff_description="Creates detailed event plans by asking minimal clarifying questions.",
            instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
            
            You create detailed, personalized event plans.
            
            CRITICAL CONSTRAINT: Ask MAX 3 questions total. Use can_ask_more_questions() to check.
            
            User's routine: {USER_ROUTINE}
            
            WORKFLOW:
            1. Check what info you already have (event type, date, user routine)
            2. Identify the 3 MOST CRITICAL missing pieces only:
               - Who is it for? (if wedding/birthday)
               - Budget level? (low/medium/high)
               - Any special requirements?
            3. Ask questions ONE at a time using increment_questions()
            4. Use user's routine to make smart recommendations:
               - Shopping at Arpico (Kandy)
               - Haircut at Kumara Weediya salon
               - Work around gym time (7-9 PM) and train schedule
               - Consider Kandy location for local tasks
            5. Create complete plan with specific dates and times
            6. Hand off to ReviewerAgent for approval
            
            Be efficient. Infer from context. Don't over-ask.
            
            Plan should include:
            - Shopping list items
            - Salon appointment timing
            - Travel arrangements if needed
            - Task deadlines working around routine""",
            tools=[
                get_user_routine,
                save_event_context,
                get_event_context,
                increment_questions,
                can_ask_more_questions,
                get_todays_date,
            ],
            model="gpt-4o",
        )

        reviewer_agent = Agent(
            name="ReviewerAgent",
            handoff_description="Reviews the plan and presents it to user for approval (human-in-the-loop).",
            instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
            
            You review the plan and get user approval.
            
            WORKFLOW:
            1. Show the complete plan clearly formatted:
               - Timeline with specific dates/times
               - Tasks with deadlines
               - Vendor recommendations (Arpico, Kumara Weediya, etc.)
               - Budget estimate
               - How it fits with their routine
            2. Ask: "Does this plan work for you, or would you like any changes?"
            3. If user says YES/APPROVE/LOOKS GOOD, hand off to CalendarAgent
            4. If user wants changes, hand back to PlannerAgent with specific feedback
            
            Present plan in organized markdown format.""",
            tools=[get_event_context, get_user_routine],
            model="gpt-4o-mini",
        )

        calendar_agent = Agent(
            name="CalendarAgent",
            handoff_description="Executes the approved plan by creating/updating Google Calendar events.",
            instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
            
            You execute the approved plan in Google Calendar.
            
            WORKFLOW:
            1. Retrieve the complete plan from context using get_event_context
            2. For EACH task in the plan, use create-event to add to calendar:
               - Event title (clear and descriptive)
               - Start and end times (use ISO format with timezone)
               - Location (if applicable)
               - Description with details
            3. If conflicts were negotiated earlier and events need rescheduling:
               - Use update-event or delete-event + create-event
            4. Set appropriate reminders for each event
            5. List all created events to confirm to user
            
            IMPORTANT: 
            - Use create-event tool for EACH task/milestone
            - Format dates as ISO 8601: YYYY-MM-DDTHH:MM:SS+05:30 (Sri Lanka time)
            - Be thorough - create events for shopping, salon, preparations, etc.
            - Confirm completion with list of what was added""",
            tools=[get_event_context, get_user_routine, get_todays_date],
            mcp_servers=[calendar_server],
            model="gpt-4o",
        )

        conflict_checker_agent.handoffs = [negotiator_agent, planner_agent]
        negotiator_agent.handoffs = [planner_agent]
        planner_agent.handoffs = [reviewer_agent]
        reviewer_agent.handoffs = [calendar_agent, planner_agent]
        calendar_agent.handoffs = []

        conversation_id = f"planning_{datetime.now().timestamp()}"
        session = SQLiteSession(conversation_id)

        current_agent = conflict_checker_agent

        print("\n🎯 Smart Planning Assistant")
        print("=" * 60)
        print("📅 Connected to Google Calendar")
        print("👤 User Profile: Lives in Kandy, trains to Colombo, gym 7-9 PM")
        print("\nTell me about your upcoming event!\n")

        while True:
            user_input = input("You: ").strip()

            if not user_input or user_input.lower() in ["exit", "quit", "bye"]:
                print("\nGoodbye! 👋")
                break

            with trace("Planning Assistant", group_id=conversation_id):
                result = await Runner.run(
                    current_agent, user_input, context=context, session=session
                )

                for new_item in result.new_items:
                    agent_name = new_item.agent.name

                    if isinstance(new_item, MessageOutputItem):
                        message = ItemHelpers.text_message_output(new_item)
                        print(f"\n{agent_name}: {message}\n")

                    elif isinstance(new_item, HandoffOutputItem):
                        print(f"\n→ Transferring to {new_item.target_agent.name}...\n")

                    elif isinstance(new_item, ToolCallItem):
                        # FIX: Access tool_call.function.name instead of .name
                        if hasattr(new_item, "tool_call") and hasattr(
                            new_item.tool_call, "function"
                        ):
                            tool_name = new_item.tool_call.function.name
                            if (
                                "calendar" in tool_name.lower()
                                or "event" in tool_name.lower()
                            ):
                                print(f"📅 Using calendar: {tool_name}...")
                        else:
                            print(f"🔧 {agent_name}: Using tool...")

                current_agent = result.last_agent

                if current_agent.name == "CalendarAgent" and any(
                    isinstance(item, MessageOutputItem) for item in result.new_items
                ):
                    print("\n✅ Planning complete! Check your Google Calendar.")
                    break


if __name__ == "__main__":
    asyncio.run(main())
