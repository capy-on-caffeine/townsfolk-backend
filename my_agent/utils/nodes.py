from __future__ import annotations
import sys

# ============================================================
# ⚠️ CRITICAL: Windows Event-Loop Policy Fix
# ============================================================
# This MUST run before any other asyncio code (including imports
# from other libraries like Playwright or FastAPI) creates an
# event loop.
#
# On Windows, the default SelectorEventLoop does not support
# subprocesses, which Playwright needs. We must set the
# policy to WindowsProactorEventLoopPolicy.
if sys.platform.startswith("win"):
    try:
        import asyncio
        if not isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        # If policy is unavailable (non-Windows) or already set, ignore.
        pass
# ============================================================
# End of Windows Fix
# ============================================================

import os
import json
import base64
import asyncio
import traceback
from typing import Any, Dict, List, Optional

# --- Playwright: use ASYNC API only (Option A) ---
from playwright.async_api import async_playwright, Error as PlaywrightError

# --- Gemini (sync client; we'll call via to_thread) ---
from google import genai
from google.genai.types import Content, Part

# --- Your project utils/schemas ---
# Note: Ensure these paths are correct relative to your execution context
from .utils import get_mongo_client
from .schema import Feedback, Persona

# ============================================================
# Model / Runtime Config
# ============================================================
MODEL_NAME = "gemini-2.5-computer-use-preview-10-2025"
MAX_STEPS = 20
HEADLESS = True

VIEWPORT = {"width": 1440, "height": 900}
BROWSER_STATE_PATH = "playwright_state.json"  # persistent cookies/session
PAGE_DEFAULT_TIMEOUT_MS = 15000
NAVIGATION_WAIT_UNTIL = "load"

CHROMIUM_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
]

# ============================================================
# Helpers: screenshots, a11y, actions
# ============================================================

async def _grab_screenshot_b64(page) -> str:
    png_bytes = await page.screenshot(full_page=True, type="png")
    return base64.b64encode(png_bytes).decode("utf-8")

async def _grab_a11y_snapshot(page) -> dict:
    try:
        snap = await page.accessibility.snapshot()
        return snap or {}
    except PlaywrightError:
        return {}

async def _apply_action(page, action: dict):
    """
    Execute a single Gemini-issued action.
    Supported: goto, click, type, scroll, wait
    """
    if not isinstance(action, dict):
        return
    a = action.get("action")
    if not a:
        return

    try:
        if a == "goto":
            url = action["url"]
            await page.goto(url, wait_until=NAVIGATION_WAIT_UNTIL, timeout=PAGE_DEFAULT_TIMEOUT_MS)

        elif a == "click":
            selector = action["selector"]
            await page.click(selector, timeout=PAGE_DEFAULT_TIMEOUT_MS)

        elif a == "type":
            selector = action["selector"]
            text = action.get("text", "")
            # Prefer fill for deterministic results
            await page.fill(selector, text, timeout=PAGE_DEFAULT_TIMEOUT_MS)

        elif a == "scroll":
            amount = int(action.get("amount", 1000))
            await page.evaluate(f"window.scrollBy(0, {amount});")

        elif a == "wait":
            duration = int(action.get("duration", 1000))
            await page.wait_for_timeout(duration)

        # small settle between steps
        await page.wait_for_timeout(300)

    except PlaywrightError:
        # swallow per-action errors to keep loop resilient
        await page.wait_for_timeout(200)

# ============================================================
# Gemini call (sync SDK -> run in thread)
# ============================================================

def _gemini_call_sync(api_key: str, contents: List[Content]) -> str:
    client = genai.Client(api_key=api_key)
    res = client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        generation_config={"response_mime_type": "application/json"},
    )
    return res.text

async def gemini_generate_json(api_key: str, contents: List[Content]) -> str:
    return await asyncio.to_thread(_gemini_call_sync, api_key, contents)

# ============================================================
# Instruction builder
# ============================================================

def build_exploration_instruction(persona: Persona, url: str, app_context: str) -> str:
    return f"""
You are a UX researcher simulating the following persona while exploring a LIVE website via screenshots and the accessibility tree.
During exploration, return JSON actions only. When finished, output ONLY the final JSON report (no prose outside JSON).

Persona:
- id: {persona.id}
- name: {persona.name}
- age: {persona.age}
- gender: {persona.gender}
- occupation: {persona.occupation}
- bio: {persona.bio}

Target URL: {url}
Context: {app_context}

FINAL OUTPUT FORMAT (strict JSON):
{{
  "persona_id": "{persona.id}",
  "overall_rating": 0-5,
  "summary": "...",
  "rubric": {{
    "value_prop_clarity": 0-5,
    "information_architecture": 0-5,
    "visual_design": 0-5,
    "ux_flows": 0-5,
    "performance": 0-5,
    "accessibility": 0-5
  }},
  "highlights": ["..."],
  "issues": [{{"title": "", "impact": "low|medium|high", "detail": "", "suggestion": ""}}],
  "critical_cta_check": {{
    "cta_label": "",
    "was_findable": true,
    "was_clickable": true,
    "blocked_by": ""
  }}
}}

If more exploration is needed, respond like:
{{"actions":[{{"action":"scroll","amount":1200}}]}}
""".strip()

# ============================================================
# Core: async Playwright + Gemini loop
# ============================================================

async def run_computer_use_eval_async(url: str, api_key: str, instruction: str) -> str:
    """
    Fully async browser session (Option A):
      - async_playwright
      - headless Chromium
      - storage_state persisted to JSON
      - Gemini calls via to_thread (non-blocking)
    """
    # Prepare initial storage_state (load if exists)
    load_storage_state: Optional[str | dict] = None
    if os.path.exists(BROWSER_STATE_PATH):
        load_storage_state = BROWSER_STATE_PATH

    history: List[Content] = []
    
    browser = None
    context = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=HEADLESS, args=CHROMIUM_ARGS)

            context_kwargs = {"viewport": VIEWPORT}
            if load_storage_state:
                context_kwargs["storage_state"] = load_storage_state

            context = await browser.new_context(**context_kwargs)
            page = await context.new_page()
            page.set_default_timeout(PAGE_DEFAULT_TIMEOUT_MS)

            # Best-effort initial nav
            try:
                await page.goto(url, wait_until=NAVIGATION_WAIT_UNTIL, timeout=PAGE_DEFAULT_TIMEOUT_MS)
            except PlaywrightError:
                pass # Continue even if first nav fails

            for step in range(1, MAX_STEPS + 1):
                screenshot_b64 = await _grab_screenshot_b64(page)
                a11y_tree = await _grab_a11y_snapshot(page)

                parts: List[Part] = []
                if step == 1:
                    parts.append(Part.text(instruction))
                else:
                    parts.append(Part.text("Here is the updated page state. Continue."))

                # inline image data
                parts.append(
                    Part.inline_data(
                        mime_type="image/png",
                        data=base64.b64decode(screenshot_b64),
                    )
                )
                # accessibility tree as text JSON
                parts.append(Part.text(json.dumps(a11y_tree)))

                contents = history + [Content(parts=parts)]
                raw = await gemini_generate_json(api_key, contents)

                # maintain conversation history for the next turn
                history.append(Content(parts=parts))
                history.append(Content(parts=[Part.text(raw)]))

                # Try strict JSON
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    if context:
                        await context.storage_state(path=BROWSER_STATE_PATH)
                    if browser:
                        await browser.close()
                    return json.dumps({
                        "error": "Model returned non-JSON response",
                        "raw": raw[:2000],
                        "url": url,
                    })

                # Terminal shapes (check for final report)
                if any(k in data for k in ("overall_rating", "rubric", "issues", "summary")):
                    if context:
                        await context.storage_state(path=BROWSER_STATE_PATH)
                    if browser:
                        await browser.close()
                    return json.dumps(data)

                # Otherwise execute actions if present
                actions = data.get("actions", [])
                if not actions:
                    break # Model stopped giving actions

                for action in actions:
                    await _apply_action(page, action)

            # If we exit loop without final JSON
            if context:
                await context.storage_state(path=BROWSER_STATE_PATH)
            if browser:
                await browser.close()
            return json.dumps({
                "error": "Model ended without providing feedback.",
                "url": url,
            })

    finally:
        # Ensure state is saved and browser is closed even if something throws mid-loop
        try:
            if context:
                await context.storage_state(path=BROWSER_STATE_PATH)
        except Exception:
            pass
        try:
            if browser:
                await browser.close()
        except Exception:
            pass

# ============================================================
# LangGraph Node Functions
# ============================================================

async def load_personas(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Loads personas from Mongo in a worker thread.
    Expects:
      - state["personas_db_name"]
      - state["personas_collection_name"]
    """
    def _load():
        mongo = get_mongo_client()
        docs = mongo.find(
            state["personas_db_name"],
            state["personas_collection_name"],
            {}
        )
        return [Persona.from_mongo(d).to_dict() for d in docs]

    personas = await asyncio.to_thread(_load)
    return {
        "personas": personas,
        "index": 0,
        "feedbacks": [],
        "current_feedback": None,
        "status": "running",
    }

async def process_persona(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runs the async Playwright + Gemini computer-use loop for the current persona.
    Expects in state:
      - "gemini_api_key"
      - "mvp_link"
      - optional "app_context"
    """
    personas = state.get("personas") or []
    idx = state.get("index", 0)

    if idx >= len(personas):
        return {"status": "completed"}

    persona = Persona.from_mongo(personas[idx])

    api_key = state.get("gemini_api_key")
    if not api_key:
        return {
            "current_feedback": {
                "persona_id": persona.id,
                "text": json.dumps({
                    "error": "Missing Gemini API key",
                    "persona_id": persona.id
                })
            }
        }

    instruction = build_exploration_instruction(
        persona,
        url=state["mvp_link"],
        app_context=state.get("app_context", "No context"),
    )

    try:
        feedback_json = await run_computer_use_eval_async(
            url=state["mvp_link"],
            api_key=api_key,
            instruction=instruction,
        )
    except Exception as exc:
        feedback_json = json.dumps({
            "persona_id": persona.id,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })

    return {
        "current_feedback": {
            "persona_id": persona.id,
            "text": feedback_json,
        }
    }

async def write_feedback(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Persists the current feedback to Mongo.
    Needs in state:
      - "feedback_db_name"
      - "feedback_collection_name"
      - "job_id"
    """
    cur = state.get("current_feedback")
    if not cur:
        return {}

    fb = Feedback.new(
        job=state["job_id"],
        persona=cur["persona_id"],
        feedback=cur["text"],
        rating=None,
        rubric_breakdown=None,
        raw_actions=None,
    )
    doc = fb.to_mongo()

    def _write():
        mongo = get_mongo_client()
        mongo.insert_one(
            state["feedback_db_name"],
            state["feedback_collection_name"],
            doc
        )

    await asyncio.to_thread(_write)

    feedbacks = list(state.get("feedbacks") or [])
    feedbacks.append(cur)

    return {
        "feedbacks": feedbacks,
        "current_feedback": None,
    }

async def check_status(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Advances to the next persona or marks completed.
    """
    idx = state.get("index", 0)
    personas = state.get("personas") or []
    if idx + 1 >= len(personas):
        return {"status": "completed"}
    return {"index": idx + 1}