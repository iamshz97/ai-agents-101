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
)

load_dotenv()

RECOMMENDED_PROMPT_PREFIX = """You have access to handoff tools, which let you delegate requests to other agents specialized in specific areas. Always consider whether another agent would be better suited to handle the user's request."""


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

        # ============== PARALLEL CONFLICT CHECKING AGENTS ==============

        calendar_conflict_checker = Agent(
            name="CalendarConflictChecker",
            instructions="""You check Google Calendar for scheduling conflicts.
            
            FOCUS ONLY ON:
            - Listing existing calendar events for the given date/time
            - Identifying time overlaps
            
            Return a concise list of conflicting events with times.""",
            tools=[get_todays_date, save_event_context],
            mcp_servers=[calendar_server],
            model="gpt-4o-mini",
        )

        routine_conflict_checker = Agent(
            name="RoutineConflictChecker",
            instructions=f"""You check user's routine for conflicts.
            
            User routine: {USER_ROUTINE}
            
            FOCUS ONLY ON:
            - Gym time conflicts (7-9 PM weekdays)
            - Commute conflicts (7 AM, 6 PM)
            - Work hour conflicts (9 AM - 5 PM)
            
            Return a concise list of routine conflicts.""",
            tools=[get_user_routine, save_event_context],
            model="gpt-4o-mini",
        )

        # ============== CONFLICT ORCHESTRATOR ==============

        conflict_orchestrator = Agent(
            name="ConflictOrchestrator",
            handoff_description="Orchestrates parallel conflict checking from calendar and routine.",
            instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
            
            You coordinate conflict checking by analyzing results from:
            1. Calendar conflicts (existing events)
            2. Routine conflicts (gym, commute, work)
            
            WORKFLOW:
            - Receive parallel results
            - Combine and deduplicate conflicts
            - If ANY conflicts found → hand off to NegotiatorAgent
            - If NO conflicts → hand off directly to PlanningOrchestrator
            
            Be concise in summarizing conflicts.""",
            tools=[get_todays_date, get_user_routine, save_event_context],
            model="gpt-4o-mini",
        )

        negotiator_agent = Agent(
            name="NegotiatorAgent",
            handoff_description="Negotiates and resolves calendar conflicts with the user.",
            instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
            
            You help resolve scheduling conflicts.
            You have to understand user's routine and see if any conflicts exist with the mentioned plan.
            Will it disrupt what they are daily routine..
            
            WORKFLOW:
            1. Present conflicts clearly to the user
            2. Suggest alternatives:
               - Reschedule existing events
               - Adjust timing
               - Skip non-critical activities (e.g., gym once)
            3. Get user's decision on resolution
            4. Save the resolution strategy
            5. Hand off to PlanningOrchestrator once conflicts are resolved
            
            Be solution-oriented. Only ask 1-2 questions to resolve.""",
            tools=[save_event_context, get_event_context, get_user_routine],
            mcp_servers=[calendar_server],
            model="gpt-4o-mini",
        )

        # ============== PARALLEL PLANNING AGENTS ==============

        conservative_planner = Agent(
            name="ConservativePlanner",
            instructions=f"""You create conservative, safe plans with extra time buffers.
            
            User routine: {USER_ROUTINE}
            
            APPROACH:
            - Add 50% extra time for each task
            - Schedule tasks well in advance
            - Prefer weekends for shopping/personal tasks
            - Avoid tight schedules
            
            Create a detailed plan with buffer time.""",
            tools=[get_user_routine, get_event_context, get_todays_date],
            model="gpt-4o",
        )

        efficient_planner = Agent(
            name="EfficientPlanner",
            instructions=f"""You create efficient, optimized plans.
            
            User routine: {USER_ROUTINE}
            
            APPROACH:
            - Minimize time spent
            - Batch similar tasks (all shopping in one trip)
            - Use local vendors (Arpico, Kumara Weediya)
            - Maximize use of commute times
            
            Create a streamlined, time-efficient plan.""",
            tools=[get_user_routine, get_event_context, get_todays_date],
            model="gpt-4o",
        )

        budget_conscious_planner = Agent(
            name="BudgetPlanner",
            instructions=f"""You create budget-conscious plans.
            
            User routine: {USER_ROUTINE}
            
            APPROACH:
            - Prioritize cost-effective options
            - Suggest DIY where possible
            - Local shopping (Arpico) over premium stores
            - Combine trips to save transport costs
            
            Create a budget-friendly plan.""",
            tools=[get_user_routine, get_event_context, get_todays_date],
            model="gpt-4o",
        )

        # ============== PLANNING ORCHESTRATOR ==============

        planning_orchestrator = Agent(
            name="PlanningOrchestrator",
            handoff_description="Orchestrates parallel plan generation and picks the best approach.",
            instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
            
            You coordinate multiple planning approaches:
            1. Conservative (safe, buffered)
            2. Efficient (time-optimized)
            3. Budget-conscious (cost-effective)
            
            WORKFLOW:
            - Ask user 1-3 critical questions first (use increment_questions)
            - Generate 3 plans in parallel
            - Evaluate and pick the BEST plan based on:
              * User's stated priorities
              * Feasibility
              * Balance of factors
            - Hand off final plan to ReviewerAgent
            
            Ask MAX 3 questions total before generating plans.""",
            tools=[
                get_user_routine,
                save_event_context,
                get_event_context,
                increment_questions,
                get_todays_date,
            ],
            model="gpt-4o",
        )

        # ============== PARALLEL ENRICHMENT AGENTS ==============

        vendor_researcher = Agent(
            name="VendorResearcher",
            instructions=f"""You research and recommend local vendors.
            
            User location: Kandy
            Preferred vendors: Arpico, Kumara Weediya salon
            
            Provide:
            - Specific vendor recommendations with locations
            - Operating hours
            - Contact information if available
            - Why each vendor is suitable""",
            tools=[WebSearchTool(), get_event_context],
            model="gpt-4o-mini",
        )

        budget_estimator = Agent(
            name="BudgetEstimator",
            instructions="""You estimate costs for the plan.
            
            Provide:
            - Itemized cost breakdown
            - Total estimate (low/medium/high ranges)
            - Cost-saving tips
            - Payment timeline recommendations""",
            tools=[get_event_context],
            model="gpt-4o-mini",
        )

        # ============== REVIEWER ==============

        reviewer_agent = Agent(
            name="ReviewerAgent",
            handoff_description="Reviews the plan and presents it to user for approval (human-in-the-loop).",
            instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
            
            You review the plan and get user approval.
            
            WORKFLOW:
            1. Show the complete plan with:
               - Timeline with specific dates/times
               - Tasks with deadlines
               - Vendor recommendations
               - Budget estimate
               - How it fits their routine
            2. Ask: "Does this plan work for you, or would you like any changes?"
            3. If user says YES/APPROVE/LOOKS GOOD → hand off to CalendarAgent
            4. If user wants changes → hand back to PlanningOrchestrator with feedback
            
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
            1. Retrieve the complete plan from context
            2. For EACH task, use create-event to add to calendar:
               - Event title (clear and descriptive)
               - Start and end times (ISO format: YYYY-MM-DDTHH:MM:SS+05:30)
               - Location (if applicable)
               - Description with details
            3. If conflicts were negotiated, update/reschedule events
            4. Set reminders for each event
            5. List all created events to confirm
            
            Be thorough - create events for all tasks.""",
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

        print("\n🎯 Smart Planning Assistant (Parallelized)")
        print("=" * 60)
        print("📅 Connected to Google Calendar")
        print("👤 User Profile: Lives in Kandy, trains to Colombo, gym 7-9 PM")
        print("⚡ Using parallel processing for faster planning")
        print("\nTell me about your upcoming event!\n")

        # Start with initial message processing
        user_input = input("You: ").strip()

        if not user_input or user_input.lower() in ["exit", "quit", "bye"]:
            print("\nGoodbye! 👋")
            return

        # ============== PHASE 1: PARALLEL CONFLICT CHECKING ==============

        print("\n🔍 Checking for conflicts...")

        with trace("Conflict Check", group_id=conversation_id):
            # Run both conflict checkers in parallel
            calendar_result, routine_result = await asyncio.gather(
                Runner.run(calendar_conflict_checker, user_input, context=context),
                Runner.run(routine_conflict_checker, user_input, context=context),
            )

            # Combine results
            combined_conflicts = f"""Calendar conflicts:
{ItemHelpers.text_message_outputs(calendar_result.new_items)}

Routine conflicts:
{ItemHelpers.text_message_outputs(routine_result.new_items)}"""

            print(f"✓ Conflict check complete")

            # Orchestrator decides next step
            orchestrator_result = await Runner.run(
                conflict_orchestrator,
                f"User request: {user_input}\n\n{combined_conflicts}",
                context=context,
                session=session,
            )

            current_agent = orchestrator_result.last_agent

            # Display orchestrator decision
            for item in orchestrator_result.new_items:
                if isinstance(item, MessageOutputItem):
                    print(
                        f"\n{item.agent.name}: {ItemHelpers.text_message_output(item)}\n"
                    )
                elif isinstance(item, HandoffOutputItem):
                    print(f"→ Transferring to {item.target_agent.name}...\n")

        # ============== PHASE 2: INTERACTIVE CONVERSATION ==============

        while True:
            # If we're at planning orchestrator, trigger parallel planning
            if current_agent.name == "PlanningOrchestrator":

                # Get any clarifying questions first
                questions_asked = 0
                while questions_asked < 3:
                    result = await Runner.run(
                        current_agent,
                        "Continue with planning",
                        context=context,
                        session=session,
                    )

                    # Check if agent is asking a question
                    has_question = False
                    for item in result.new_items:
                        if isinstance(item, MessageOutputItem):
                            message = ItemHelpers.text_message_output(item)
                            print(f"\n{item.agent.name}: {message}\n")
                            if "?" in message:
                                has_question = True

                    if not has_question:
                        # Agent is done asking questions, proceed to parallel planning
                        break

                    # Get user response
                    user_response = input("You: ").strip()
                    result = await Runner.run(
                        current_agent,
                        user_response,
                        context=context,
                        session=session,
                    )
                    questions_asked += 1

                # ============== PARALLEL PLAN GENERATION ==============

                print("\n⚡ Generating multiple plan options in parallel...")

                planning_context = (
                    f"Create a plan based on all gathered information for: {user_input}"
                )

                with trace("Parallel Planning", group_id=conversation_id):
                    conservative_result, efficient_result, budget_result = (
                        await asyncio.gather(
                            Runner.run(
                                conservative_planner, planning_context, context=context
                            ),
                            Runner.run(
                                efficient_planner, planning_context, context=context
                            ),
                            Runner.run(
                                budget_conscious_planner,
                                planning_context,
                                context=context,
                            ),
                        )
                    )

                    plans = {
                        "Conservative (Safe)": ItemHelpers.text_message_outputs(
                            conservative_result.new_items
                        ),
                        "Efficient (Fast)": ItemHelpers.text_message_outputs(
                            efficient_result.new_items
                        ),
                        "Budget-Conscious": ItemHelpers.text_message_outputs(
                            budget_result.new_items
                        ),
                    }

                    print("\n✓ Generated 3 plan options")

                    # Let orchestrator pick best plan
                    all_plans = "\n\n---\n\n".join(
                        [f"{name}:\n{plan}" for name, plan in plans.items()]
                    )

                    best_plan_result = await Runner.run(
                        planning_orchestrator,
                        f"Select the best plan:\n\n{all_plans}",
                        context=context,
                        session=session,
                    )

                    # Save best plan
                    best_plan = ItemHelpers.text_message_outputs(
                        best_plan_result.new_items
                    )
                    set_context_value("final_plan", best_plan)

                    current_agent = best_plan_result.last_agent

                    for item in best_plan_result.new_items:
                        if isinstance(item, MessageOutputItem):
                            print(
                                f"\n{item.agent.name}: {ItemHelpers.text_message_output(item)}\n"
                            )
                        elif isinstance(item, HandoffOutputItem):
                            print(f"→ Transferring to {item.target_agent.name}...\n")
                            current_agent = item.target_agent

                # ============== PARALLEL ENRICHMENT ==============

                if current_agent.name == "ReviewerAgent":
                    print("\n🔍 Enriching plan with vendor and budget details...")

                    with trace("Parallel Enrichment", group_id=conversation_id):
                        vendor_result, budget_result = await asyncio.gather(
                            Runner.run(
                                vendor_researcher,
                                f"Research vendors for: {best_plan}",
                                context=context,
                            ),
                            Runner.run(
                                budget_estimator,
                                f"Estimate budget for: {best_plan}",
                                context=context,
                            ),
                        )

                        vendors = ItemHelpers.text_message_outputs(
                            vendor_result.new_items
                        )
                        budget = ItemHelpers.text_message_outputs(
                            budget_result.new_items
                        )

                        set_context_value("vendor_recommendations", vendors)
                        set_context_value("budget_estimate", budget)

                    print("✓ Added vendor and budget details")

            # Regular conversation loop
            if current_agent.name == "CalendarAgent":
                # Execute calendar creation
                result = await Runner.run(
                    current_agent,
                    "Execute the approved plan",
                    context=context,
                    session=session,
                )

                for item in result.new_items:
                    if isinstance(item, MessageOutputItem):
                        print(
                            f"\n{item.agent.name}: {ItemHelpers.text_message_output(item)}\n"
                        )

                print("\n✅ Planning complete! Check your Google Calendar.")
                break

            # Get next user input
            user_input = input("You: ").strip()

            if not user_input or user_input.lower() in ["exit", "quit", "bye"]:
                print("\nGoodbye! 👋")
                break

            result = await Runner.run(
                current_agent,
                user_input,
                context=context,
                session=session,
            )

            for item in result.new_items:
                if isinstance(item, MessageOutputItem):
                    print(
                        f"\n{item.agent.name}: {ItemHelpers.text_message_output(item)}\n"
                    )
                elif isinstance(item, HandoffOutputItem):
                    print(f"→ Transferring to {item.target_agent.name}...\n")

            current_agent = result.last_agent


if __name__ == "__main__":
    asyncio.run(main())
