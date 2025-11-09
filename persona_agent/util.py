import base64
import asyncio
import json
import os
from google import genai
from google.genai.types import Content, Part
from playwright.async_api import async_playwright

MODEL_NAME = "gemini-2.5-flash-thinking-exp-01-21"  # Computer Use enabled

async def get_screenshot(page):
    screenshot_bytes = await page.screenshot(full_page=True)
    return base64.b64encode(screenshot_bytes).decode("utf-8")

async def get_accessibility_tree(page):
    tree = await page.accessibility.snapshot()
    return tree

# --- LOGIC FIX ---
# Updated to correctly send the full conversation history
async def send_to_gemini(user_parts, history, client):
    """
    Sends the current user turn (prompt, screenshot, tree) along
    with the entire conversation history to Gemini.
    """
    
    # Combine the existing history with the new user turn
    contents_to_send = history + [Content(parts=user_parts)]

    res = client.models.generate_content(
        model=MODEL_NAME,
        contents=contents_to_send,  # Send the full history
        config={"response_mime_type": "application/json"}
    )
    
    # Return the model's response (which is JSON text)
    return res.text


async def apply_action(page, action):
    """Execute Gemini’s browser action."""
    print(f"Executing action: {action}") # Added for visibility
    try:
        a = action["action"]

        if a == "goto":
            await page.goto(action["url"])

        elif a == "click":
            await page.click(action["selector"])

        elif a == "type":
            await page.fill(action["selector"], action["text"])

        elif a == "scroll":
            # Default to scrolling down by 1000px if 'amount' is missing
            await page.evaluate(f"window.scrollBy(0, {action.get('amount', 1000)});")

        elif a == "wait":
            await page.wait_for_timeout(action.get("duration", 1000))
        
        # Give the page a moment to react after an action
        await page.wait_for_timeout(500) 

    except Exception as e:
        print(f"Warning: Could not apply action {action}. Error: {e}")
    return

async def gemini_computer_use_feedback(url: str, api_key: str):
    # --- FIX 1 ---
    # Reverted to genai.Client, which is the correct way to initialize.
    client = genai.Client(api_key=api_key)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(url) # Go to the URL first

        # Initial instruction to the Gemini Computer Use model
        user_instruction = (
            f"You are a UX/UI expert. You will be given a screenshot and accessibility tree."
            f"Your task is to fully explore the page at {url} by issuing actions "
            f"like 'click', 'scroll', and 'type'. "
            f"Your goal is to provide a clear, concise UX/UI feedback summary. "
            f"When you are finished exploring and ready to give feedback, "
            f"output ONLY: {{\"done\": true, \"feedback\": \"...your summary here...\"}}"
            f"Otherwise, output actions to continue exploring: {{\"actions\": [ ... ]}}"
        )

        # History will store a list of Content objects
        history = []
        step = 0

        while True:
            print(f"\n--- Step {step} ---")
            step += 1

            if step > 20: # Failsafe to prevent infinite loops
                print("Exceeded 20 steps, stopping.")
                break
                
            screenshot_b64 = await get_screenshot(page)
            tree = await get_accessibility_tree(page)

            # Build the parts for the *current* user turn
            current_user_parts = []
            if step == 1:
                # On the first step, send the full instruction
                current_user_parts.append(Part.text(user_instruction))
            else:
                # On subsequent steps, just send a simple prompt
                current_user_parts.append(Part.text("Here is the new page state. Continue your task."))
            
            # Add the state (screenshot and tree)
            current_user_parts.extend([
                Part.inline_data(
                    mime_type="image/png",
                    data=base64.b64decode(screenshot_b64)
                ),
                Part.text(json.dumps(tree))
            ])

            # Send to Gemini (with history)
            # --- FIX 2 ---
            # Pass the 'client' object, not the 'genai' module
            gemini_response_text = await send_to_gemini(
                current_user_parts,
                history,
                client, # <-- This is the fix
            )

            try:
                gemini_response_json = json.loads(gemini_response_text)
            except json.JSONDecodeError:
                print(f"Error: Model returned invalid JSON: {gemini_response_text}")
                break

            # Add *both* the user's turn and the model's response to history
            history.append(Content(parts=current_user_parts))
            history.append(Content(parts=[Part.text(gemini_response_text)]))

            # If Gemini says "done", return final feedback
            if gemini_response_json.get("done") is True:
                print("Model signaled 'done'.")
                await browser.close()
                return gemini_response_json.get("feedback", "No feedback provided.")

            # Otherwise Gemini returns actions
            actions = gemini_response_json.get("actions", [])
            if not actions:
                print("Model returned no actions and no 'done' flag. Stopping.")
                break  # fail-safe

            for action in actions:
                await apply_action(page, action)

        await browser.close()
        return "Model ended without providing feedback."