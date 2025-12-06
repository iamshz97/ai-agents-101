# visualize_agents.py
import os
from agents import Agent
from agents.mcp import MCPServerStdio
from agents.extensions.visualization import draw_graph
from dotenv import load_dotenv

from tools import (
    get_todays_date,
    get_user_routine,
    save_event_context,
    get_event_context,
    USER_ROUTINE,
)

load_dotenv()

# Create MCP server
calendar_server = MCPServerStdio(
    name="Google Calendar MCP",
    params={
        "command": "npx",
        "args": ["-y", "@cocal/google-calendar-mcp"],
        "env": {
            "GOOGLE_OAUTH_CREDENTIALS": os.getenv(
                "GOOGLE_OAUTH_CREDENTIALS_PATH", "gcp-oauth.keys.json"
            )
        },
    },
)

# Create all agents
negotiator_agent = Agent(
    name="NegotiatorAgent",
    instructions="Resolve scheduling conflicts with user",
    tools=[save_event_context, get_event_context, get_user_routine],
    mcp_servers=[calendar_server],
)

planning_orchestrator = Agent(
    name="PlanningOrchestrator",
    instructions="Gather info and create comprehensive plan",
    tools=[get_user_routine, save_event_context, get_event_context, get_todays_date],
)

reviewer_agent = Agent(
    name="ReviewerAgent",
    instructions="Present plan and get user approval",
    tools=[get_event_context, get_user_routine],
)

calendar_agent = Agent(
    name="CalendarAgent",
    instructions="Execute plan by creating calendar events",
    tools=[get_event_context, get_user_routine, get_todays_date],
    mcp_servers=[calendar_server],
)

conflict_orchestrator = Agent(
    name="ConflictOrchestrator",
    instructions="Analyze conflicts and route to appropriate agent",
    handoffs=[negotiator_agent, planning_orchestrator],
    tools=[get_todays_date, save_event_context],
)

# Setup remaining handoffs
negotiator_agent.handoffs = [planning_orchestrator]
planning_orchestrator.handoffs = [reviewer_agent]
reviewer_agent.handoffs = [calendar_agent, planning_orchestrator]

# Generate visualization
print("Generating agent visualization...")
draw_graph(conflict_orchestrator)
print("Visualization complete!")
