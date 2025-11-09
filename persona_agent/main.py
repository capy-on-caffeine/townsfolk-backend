import sys
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel

# Allow running the module directly (e.g., `uvicorn main:app`) without setting PYTHONPATH.
_here = Path(__file__).resolve().parent
_package_parent = _here.parent
if _here.name == "persona_agent" and str(_package_parent) not in sys.path:
    sys.path.insert(0, str(_package_parent))

from persona_agent.utils.state import AgentState
from persona_agent.utils.nodes import generate_persona, write_persona, check_status


builder = StateGraph(AgentState)

# Nodes
builder.add_node("generate_persona", generate_persona)
builder.add_node("write_persona", write_persona)
builder.add_node("check_status", check_status)

# Edges
builder.add_edge(START, "generate_persona")
builder.add_edge("generate_persona", "write_persona")
builder.add_edge("write_persona", "check_status")


def _is_completed(state: AgentState) -> bool:
    return state.get("status") == "completed"


builder.add_conditional_edges(
    "check_status",
    _is_completed,
    {
        True: END,
        False: "generate_persona",
    },
)


graph = builder.compile(checkpointer=MemorySaver())


fastapi_app = FastAPI(
    title="Persona Agent",
    description="Serve the persona generation LangGraph as a FastAPI endpoint.",
)


class PersonaRequest(BaseModel):
    thread_id: str
    title: str
    description: str
    target_audience: str
    number: int = 1
    collection_name: str = "Persona"
    DB_name: Optional[str] = None


@fastapi_app.post("/invoke")
async def invoke_graph(payload: PersonaRequest):
    """
    Invoke the LangGraph persona agent.
    """
    config = {"configurable": {"thread_id": payload.thread_id}}
    initial_state = payload.model_dump(exclude={"thread_id"})

    try:
        result = await run_in_threadpool(graph.invoke, initial_state, config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safeguard for unexpected errors
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"thread_id": payload.thread_id, "result": result}


app = fastapi_app


if __name__ == "__main__":
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)
