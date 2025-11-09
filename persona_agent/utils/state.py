from typing import TypedDict, Dict, List, Optional


class AgentState(TypedDict, total=False):
    """
    Runtime state shared across persona generation nodes.
    """

    # Inputs provided by the caller
    title: str
    description: str
    target_audience: str
    number: int                         # Total personas to generate
    collection_name: str                # MongoDB collection for personas
    DB_name: str                        # MongoDB database override (optional)

    # Accumulators / outputs
    persona: List[Dict]                 # Collected personas
    current_persona: Optional[Dict]     # Persona produced in current iteration
    generated_count: int                # Personas generated so far

    # Metadata
    status: str                         # "pending" | "completed" (optional)
