# state.py
from __future__ import annotations
from typing import TypedDict, Dict, List, Optional, Any
from uuid import uuid4


class AgentState(TypedDict, total=False):
    """
    Canonical state for the LangGraph agent.

    Workflow:
      1) load_personas reads personas from (personas_db_name, personas_collection_name)
      2) process_persona uses Gemini Computer Use on mvp_link with the current persona
      3) write_feedback writes to database "feedback" (fixed) and collection feedback_collection_name
      4) loop until all personas processed → END
    """

    # Job details
    job_id: str                         # stable string id
    status: str                         # "pending" | "in-progress" | "completed"

    # Database config (from raw input)
    personas_db_name: str               # DB from which personas are fetched
    personas_collection_name: str       # Collection containing personas
    feedback_db_name: str               # Always "feedback" per spec (but configurable)
    feedback_collection_name: str       # Collection to write feedback to

    # Agent inputs
    mvp_link: str                       # URL to open and evaluate
    app_context: Optional[str]          # Optional context about the product
    gemini_project_id: Optional[str]    # Vertex project (optional)
    gemini_location: Optional[str]      # Vertex location (optional)
    gemini_use_vertex: bool             # If True, use Vertex; else API key
    gemini_api_key: Optional[str]       # If not using Vertex, use direct API key

    # Persona processing
    personas: List[Dict[str, Any]]      # Loaded persona dicts
    index: int                          # Current persona index (0-based)

    # Outputs
    feedbacks: List[Dict[str, Any]]     # Accumulated feedback
    current_feedback: Optional[Dict[str, Any]]  # Temp buffer for current persona

    # Runtime deps (managed internally)
    browser_state: Optional[Dict[str, Any]]     # If you want to reuse playwright browser
