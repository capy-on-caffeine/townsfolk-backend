import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

import requests

from .schema import Persona
from .state import AgentState
from .utils import MongoDBClient

AIML_ENDPOINT = "https://api.aimlapi.com/v1/chat/completions"
AIML_MODEL = "openai/gpt-4.1-mini-2025-04-14"


def _get_api_key() -> str:
    api_key = (
        os.getenv("AIMLAPI_KEY")
        or os.getenv("AIML_API_KEY")
        or os.getenv("AIMLAPIKEY")
        or ""
    )
    return api_key


def _build_messages(title: str, description: str, target_audience: str) -> List[Dict[str, str]]:
    prompt = ("""
        You are an expert persona designer specializing in constructing authentic, research-driven user personas.

Using the provided product context and target audience, generate a single realistic persona.  
Your response must be a valid JSON object and must adhere strictly to the following schema:

{
  "name": "string",
  "age": integer,
  "gender": "string",
  "occupation": "string",
  "bio": "string"
}

Requirements:
- The persona must be credible, demographically plausible, and aligned with the given context.
- The bio must be detailed, human-sounding, and clearly reflect the persona’s background, motivations, goals, and connection to the product or domain.
- Do not include any text outside the JSON object.
- Ensure the JSON is syntactically valid and conforms exactly to the schema (no extra fields).

Generate the persona now."""
    )

    user_context = (
        f"Title: {title or 'N/A'}\n"
        f"Description: {description or 'N/A'}\n"
        f"Target Audience: {target_audience or 'N/A'}\n"
        "Return only JSON without additional commentary."
    )

    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_context},
    ]


def _parse_persona_payload(raw_content: str) -> Dict[str, Any]:
    try:
        return json.loads(raw_content)
    except json.JSONDecodeError:
        # Attempt to extract JSON substring if the response contains extra text.
        start = raw_content.find("{")
        end = raw_content.rfind("}")
        if start != -1 and end != -1 and start < end:
            snippet = raw_content[start : end + 1]
            return json.loads(snippet)
        raise ValueError("Failed to parse persona JSON from model response.")


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_persona(state: AgentState) -> Dict[str, Any]:
    api_key = _get_api_key()

    title = state.get("title", "")
    description = state.get("description", "")
    target_audience = state.get("target_audience", "")

    if not target_audience:
        raise ValueError("target_audience is required to generate a persona.")

    response = requests.post(
        AIML_ENDPOINT,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json={
            "model": AIML_MODEL,
            "messages": _build_messages(title, description, target_audience),
            "temperature": 0.2,
        },
        timeout=60,
    )
    response.raise_for_status()

    payload = response.json()
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise ValueError(f"Unexpected response format from AIML API: {payload}")

    persona_data = _parse_persona_payload(content)

    persona_id = persona_data.get("id") or str(uuid4())
    persona_data["id"] = persona_id

    now = _timestamp()
    persona_data["created_at"] = now
    persona_data["updated_at"] = now

    personas = list(state.get("persona", []))
    personas.append(persona_data)

    generated_count = state.get("generated_count", 0) + 1

    return {
        "current_persona": persona_data,
        "persona": personas,
        "generated_count": generated_count,
    }


def write_persona(state: AgentState) -> Dict[str, Any]:
    current = state.get("current_persona")
    if not current:
        raise ValueError("No persona available in state to persist.")

    collection_name = state.get("collection_name") or "Persona"
    db_name = state.get("DB_name")
    URI  = os.getenv("MONGODB_URI")
    mongo_client = MongoDBClient(db_name=db_name , uri=os.getenv("MONGODB_URI")
)
    persona_record = Persona(
        id=current.get("id"),
        name=current.get("name", ""),
        age=current.get("age"),
        gender=current.get("gender"),
        occupation=current.get("occupation"),
        bio=current.get("bio"),
        created_at=current.get("created_at"),
        updated_at=current.get("updated_at"),
    )

    insert_result = mongo_client.insert_one(collection_name, {**persona_record.__dict__})

    stored_persona = {**current, "_id": str(insert_result.inserted_id)}

    personas = list(state.get("persona", []))
    if personas:
        personas[-1] = stored_persona

    return {
        "persona": personas,
        "current_persona": stored_persona,
    }


def check_status(state: AgentState) -> Dict[str, Any]:
    generated = state.get("generated_count", 0)
    target = state.get("number", 0)

    if target <= 0:
        return {"status": "completed"}

    if generated >= target:
        return {"status": "completed"}

    return {}
