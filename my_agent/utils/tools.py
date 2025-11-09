# tools.py
from __future__ import annotations
from google.genai.types import ComputerUse, Tool, Environment


def get_computer_use_tool() -> Tool:
    """
    Reusable Computer Use tool. We exclude risky predefined functions like drag_and_drop.
    """
    return Tool(
        computer_use=ComputerUse(
            environment=Environment.ENVIRONMENT_BROWSER,
            excluded_predefined_functions=["drag_and_drop"],
        )
    )
