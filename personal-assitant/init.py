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

from tools import (
    get_todays_date,
    get_user_routine,
    save_event_context,
    get_event_context,
    increment_questions,
    USER_ROUTINE,
    set_context_value,
    get_context_value,
)

load_dotenv()

RECOMMENDED_PROMPT_PREFIX = """You have access to handoff tools, which let you delegate requests to other agents specialized in specific areas. Handoffs are achieved by calling a handoff function. Always consider whether another agent would be better suited to handle the user's request."""


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

        # ============== CONFLICT CHECKING AGENTS ==============

        calendar_conflict_checker = Agent(
            name="CalendarConflictChecker",
            instructions="""Check Google Calendar for scheduling conflicts.
            
            TASK:
            - Use list-events to query calendar for the event date
            - List all existing events on that date with times
            - Identify any time overlaps
            
            OUTPUT:
            Return a clear list of conflicting events with their times, or "No calendar conflicts" if clear.""",
            tools=[get_todays_date, save_event_context],
            mcp_servers=[calendar_server],
            model="gpt-4o-mini",
        )

        routine_conflict_checker = Agent(
            name="RoutineConflictChecker",
            instructions=f"""Check user's daily routine for potential conflicts.
            
            USER ROUTINE:
            {USER_ROUTINE}
            
            TASK:
            - Check if event timing conflicts with:
              * Gym (7-9 PM weekdays)
              * Commute (7 AM departure, 6 PM return)
              * Work hours (9 AM - 5 PM weekdays in Colombo)
            - Consider travel time from Kandy to event location
            
            OUTPUT:
            Return specific conflicts found, or "No routine conflicts" if clear.""",
            tools=[get_user_routine, save_event_context, get_todays_date],
            model="gpt-4o-mini",
        )

        # ============== CONFLICT ORCHESTRATOR ==============

        conflict_orchestrator = Agent(
            name="ConflictOrchestrator",
            handoff_description="Analyzes conflicts and routes to appropriate next step.",
            instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
            
            ROLE: Coordinate conflict analysis and routing.
            
            DECISION LOGIC:
            1. Review both calendar and routine conflict reports
            2. If ANY conflicts exist:
               - Summarize all conflicts clearly
               - Transfer to NegotiatorAgent
            3. If NO conflicts:
               - Confirm calendar is clear
               - Transfer directly to PlanningOrchestrator
            
            Be direct and concise. Always transfer to another agent - don't end here.""",
            tools=[get_todays_date, save_event_context],
            model="gpt-4o-mini",
        )

        negotiator_agent = Agent(
            name="NegotiatorAgent",
            handoff_description="Resolves scheduling conflicts with user input.",
            instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
            
            ROLE: Help user resolve scheduling conflicts.
            
            APPROACH:
            1. Present conflicts clearly with specific times
            2. Suggest practical solutions:
               - Skip gym for one day (if event is evening)
               - Take earlier/later train (if work day)
               - Reschedule existing calendar events
               - Adjust event participation time
            3. Ask user which solution they prefer
            4. Save the resolution decision
            5. Once resolved, transfer to PlanningOrchestrator
            
            Be empathetic but efficient. Focus on actionable solutions.""",
            tools=[save_event_context, get_event_context, get_user_routine],
            mcp_servers=[calendar_server],
            model="gpt-4o-mini",
        )

        # ============== PLANNING AGENTS ==============

        planning_orchestrator = Agent(
            name="PlanningOrchestrator",
            handoff_description="Gathers information and coordinates plan creation.",
            instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
            
            ROLE: Gather necessary details and create a comprehensive plan.
            
            WORKFLOW:
            1. Check what information you already have (check context)
            2. Ask for ONLY the most critical missing information:
               - Event type (if not clear)
               - Who it's for (relationship/importance)
               - Budget preference (low/medium/high)
            3. Use get_event_context to check existing info BEFORE asking
            4. After gathering info, create a detailed plan considering:
               - User's routine: {USER_ROUTINE}
               - Local preferences (Arpico for shopping, Kumara Weediya salon)
               - Kandy location and Colombo commute
            5. Transfer to ReviewerAgent when plan is ready
            
            Don't over-ask. Infer what you can from context.""",
            tools=[
                get_user_routine,
                save_event_context,
                get_event_context,
                get_todays_date,
            ],
            model="gpt-4o",
        )

        # ============== REVIEWER ==============

        reviewer_agent = Agent(
            name="ReviewerAgent",
            handoff_description="Presents plan for user approval.",
            instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
            
            ROLE: Present plan and get user approval.
            
            WORKFLOW:
            1. Retrieve plan from context
            2. Present plan in clear markdown format:
               ### Event Plan
               
               **Timeline**
               - Task 1: [Date/Time]
               - Task 2: [Date/Time]
               
               **Vendors**
               - Shopping: Arpico (Kandy)
               - Salon: Kumara Weediya
               
               **Budget Estimate**
               - [Breakdown]
               
               **Notes**
               - [How it fits routine]
               
            3. Ask: "Does this plan work for you?"
            4. LISTEN TO USER RESPONSE:
               - If YES/APPROVE/GOOD/LOOKS GOOD → Transfer to CalendarAgent
               - If user wants changes → Ask what to change, then transfer back to PlanningOrchestrator with feedback
            
            Don't assume approval - wait for clear confirmation.""",
            tools=[get_event_context, get_user_routine],
            model="gpt-4o-mini",
        )

        calendar_agent = Agent(
            name="CalendarAgent",
            handoff_description="Creates calendar events for the approved plan.",
            instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
            
            ROLE: Execute the plan by creating Google Calendar events.
            
            WORKFLOW:
            1. Retrieve final plan using get_event_context("final_plan")
            2. For EACH task in the plan:
               - Use create-event with:
                 * Title: Clear description
                 * Start time: ISO 8601 format (YYYY-MM-DDTHH:MM:SS+05:30)
                 * End time: ISO 8601 format
                 * Location: If applicable
                 * Description: Task details
               - Set reminders (1 day before for major tasks)
            3. List all created events to confirm
            
            IMPORTANT:
            - Use Sri Lanka timezone: +05:30
            - Create separate events for each task (shopping, salon, preparations, etc.)
            - Be thorough - don't skip tasks
            
            After creating all events, confirm completion to user.""",
            tools=[get_event_context, get_user_routine, get_todays_date],
            mcp_servers=[calendar_server],
            model="gpt-4o",
        )

        # ============== SETUP HANDOFFS ==============

        conflict_orchestrator.handoffs = [negotiator_agent, planning_orchestrator]
        negotiator_agent.handoffs = [planning_orchestrator]
        planning_orchestrator.handoffs = [reviewer_agent]
        reviewer_agent.handoffs = [calendar_agent, planning_orchestrator]
        calendar_agent.handoffs = []

        conversation_id = f"planning_{datetime.now().timestamp()}"
        session = SQLiteSession(conversation_id)

        print("\n🎯 Smart Planning Assistant")
        print("=" * 60)
        print("📅 Connected to Google Calendar")
        print("👤 User: Kandy resident, trains to Colombo, gym 7-9 PM")
        print("\nTell me about your upcoming event!\n")

        # Start with initial message
        user_input = input("You: ").strip()

        if not user_input or user_input.lower() in ["exit", "quit", "bye"]:
            print("\nGoodbye! 👋")
            return

        # Save initial request
        set_context_value("initial_request", user_input)

        # ============== PHASE 1: PARALLEL CONFLICT CHECKING ==============

        print("\n🔍 Checking for conflicts...")

        # Run both conflict checkers in parallel
        calendar_result, routine_result = await asyncio.gather(
            Runner.run(calendar_conflict_checker, user_input, context=context),
            Runner.run(routine_conflict_checker, user_input, context=context),
        )

        # Combine results
        calendar_conflicts = ItemHelpers.text_message_outputs(calendar_result.new_items)
        routine_conflicts = ItemHelpers.text_message_outputs(routine_result.new_items)

        combined_conflicts = f"""User request: {user_input}

Calendar check results:
{calendar_conflicts}

Routine check results:
{routine_conflicts}"""

        print(f"✓ Conflict check complete\n")

        # Orchestrator decides next step
        result = await Runner.run(
            conflict_orchestrator,
            combined_conflicts,
            context=context,
            session=session,
        )

        current_agent = result.last_agent

        # Display result
        for item in result.new_items:
            if isinstance(item, MessageOutputItem):
                print(f"{item.agent.name}: {ItemHelpers.text_message_output(item)}\n")
            elif isinstance(item, HandoffOutputItem):
                print(f"→ Transferring to {item.target_agent.name}...\n")
                current_agent = item.target_agent

        # ============== PHASE 2: INTERACTIVE CONVERSATION ==============

        while True:
            # Get next user input
            user_input = input("You: ").strip()

            if not user_input or user_input.lower() in ["exit", "quit", "bye"]:
                print("\nGoodbye! 👋")
                break

            # Process message
            result = await Runner.run(
                current_agent,
                user_input,
                context=context,
                session=session,
            )

            # Display results and update current agent
            for item in result.new_items:
                if isinstance(item, MessageOutputItem):
                    message = ItemHelpers.text_message_output(item)
                    print(f"\n{item.agent.name}: {message}\n")

                    # Save plan if it looks like a plan
                    if item.agent.name == "PlanningOrchestrator" and (
                        "###" in message or "**" in message
                    ):
                        set_context_value("final_plan", message)

                elif isinstance(item, HandoffOutputItem):
                    print(f"→ Transferring to {item.target_agent.name}...\n")
                    current_agent = item.target_agent

            # Update current agent to last agent
            current_agent = result.last_agent

            # Check if we're done (calendar agent completed)
            if current_agent.name == "CalendarAgent" and any(
                isinstance(item, MessageOutputItem)
                and "created" in ItemHelpers.text_message_output(item).lower()
                for item in result.new_items
            ):
                print("\n✅ Planning complete! Check your Google Calendar.")
                break


if __name__ == "__main__":
    asyncio.run(main())
