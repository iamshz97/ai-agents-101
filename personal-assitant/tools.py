# tools.py
from agents import function_tool
from typing import Optional, Dict
from datetime import date

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


# ============== FUNCTION TOOLS (for agents) ==============


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


# ============== HELPER FUNCTIONS (for your Python code) ==============


def get_context_value(key: str) -> Optional[str]:
    """
    Helper function to get context value directly from Python code.
    This is NOT a FunctionTool - use this in your application logic.

    Args:
        key: The context key to retrieve

    Returns:
        The value associated with the key, or None if not found
    """
    return context_storage.get(key)


def set_context_value(key: str, value: str) -> None:
    """
    Helper function to set context value directly from Python code.
    This is NOT a FunctionTool - use this in your application logic.

    Args:
        key: The context key to set
        value: The value to store
    """
    context_storage[key] = value


def get_all_context() -> Dict:
    """
    Get the entire context storage dictionary.
    Useful for debugging or passing context between components.

    Returns:
        The complete context storage dictionary
    """
    return context_storage.copy()


def clear_context() -> None:
    """
    Clear all context except the configuration values.
    Useful when starting a new planning session.
    """
    context_storage.clear()
    context_storage.update(
        {
            "questions_asked": 0,
            "max_questions": 10,
            "conflicts_detected": [],
            "plan_approved": False,
        }
    )


def get_questions_remaining() -> int:
    """
    Get the number of questions remaining before max is reached.

    Returns:
        Number of questions that can still be asked
    """
    asked = context_storage.get("questions_asked", 0)
    max_q = context_storage.get("max_questions", 10)
    return max(0, max_q - asked)
