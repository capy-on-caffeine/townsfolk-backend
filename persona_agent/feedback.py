import base64
import asyncio
import json
from google import genai
from google.genai.types import Content, Part
from playwright.async_api import async_playwright
from google import genai
from google.genai import types
from google.genai.types import Content, Part
MODEL_NAME = "gemini-2.5-computer-use-preview-10-2025"  # Computer Use enabled

async def get_screenshot(page):
    screenshot_bytes = await page.screenshot(full_page=True)
    return base64.b64encode(screenshot_bytes).decode("utf-8")

async def get_accessibility_tree(page):
    tree = await page.accessibility.snapshot()
    return tree

async def send_to_gemini(prompt, screenshot_b64, tree, history, client):
    content = [
        Part.from_text(prompt),
        Part.from_data(mime_type="image/png", data=base64.b64decode(screenshot_b64)),
        Part.from_text(json.dumps(tree))
    ]

    res = client.models.generate_content(
        model=MODEL_NAME,
        contents=[Content(parts=content)],
        config={"response_mime_type": "application/json"}  # force JSON actions
    )
    return json.loads(res.text)

async def apply_action(page, action):
    """Execute Gemini’s browser action."""
    a = action["action"]

    if a == "goto":
        await page.goto(action["url"])

    elif a == "click":
        await page.click(action["selector"])

    elif a == "type":
        await page.fill(action["selector"], action["text"])

    elif a == "scroll":
        await page.evaluate(f"window.scrollBy(0, {action['amount']});")

    elif a == "wait":
        await page.wait_for_timeout(action.get("duration", 1000))

    # Gemini may generate more action types in future
    return

async def gemini_computer_use_feedback(url: str, api_key: str):
    client = genai.Client(api_key=api_key)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto("about:blank")

        # Initial instruction to the Gemini Computer Use model
        user_instruction = (
            f"Go to {url}, fully explore the page if needed, "
            f"and then provide a clear UX/UI feedback summary. "
            f"When finished, output only: {{\"done\": true, \"feedback\": \"...\"}}"
        )

        history = []
        step = 0

        while True:
            step += 1
            screenshot_b64 = await get_screenshot(page)
            tree = await get_accessibility_tree(page)

            gemini_response = await send_to_gemini(
                user_instruction,
                screenshot_b64,
                tree,
                history,
                client,
            )

            # If Gemini says "done", return final feedback
            if gemini_response.get("done") is True:
                await browser.close()
                return gemini_response.get("feedback", "No feedback provided.")

            # Otherwise Gemini returns actions
            actions = gemini_response.get("actions", [])
            if not actions:
                break  # fail-safe

            for action in actions:
                await apply_action(page, action)

            history.append(gemini_response)

        await browser.close()
        return "Model ended without providing feedback."
from typing import Any, List, Tuple
import time

def denormalize_x(x: int, screen_width: int) -> int:
    """Convert normalized x coordinate (0-1000) to actual pixel coordinate."""
    return int(x / 1000 * screen_width)

def denormalize_y(y: int, screen_height: int) -> int:
    """Convert normalized y coordinate (0-1000) to actual pixel coordinate."""
    return int(y / 1000 * screen_height)

def execute_function_calls(candidate, page, screen_width, screen_height):
    results = []
    function_calls = []
    for part in candidate.content.parts:
        if part.function_call:
            function_calls.append(part.function_call)

    for function_call in function_calls:
        action_result = {}
        fname = function_call.name
        args = function_call.args
        print(f"  -> Executing: {fname}")

        try:
            if fname == "open_web_browser":
                pass # Already open
            elif fname == "click_at":
                actual_x = denormalize_x(args["x"], screen_width)
                actual_y = denormalize_y(args["y"], screen_height)
                page.mouse.click(actual_x, actual_y)
            elif fname == "type_text_at":
                actual_x = denormalize_x(args["x"], screen_width)
                actual_y = denormalize_y(args["y"], screen_height)
                text = args["text"]
                press_enter = args.get("press_enter", False)

                page.mouse.click(actual_x, actual_y)
                # Simple clear (Command+A, Backspace for Mac)
                page.keyboard.press("Meta+A")
                page.keyboard.press("Backspace")
                page.keyboard.type(text)
                if press_enter:
                    page.keyboard.press("Enter")
            else:
                print(f"Warning: Unimplemented or custom function {fname}")

            # Wait for potential navigations/renders
            page.wait_for_load_state(timeout=5000)
            time.sleep(1)

        except Exception as e:
            print(f"Error executing {fname}: {e}")
            action_result = {"error": str(e)}

        results.append((fname, action_result))

    return results


def get_function_responses(page, results):
    screenshot_bytes = page.screenshot(type="png")
    current_url = page.url
    function_responses = []
    for name, result in results:
        response_data = {"url": current_url}
        response_data.update(result)
        function_responses.append(
            types.FunctionResponse(
                name=name,
                response=response_data,
                parts=[types.FunctionResponsePart(
                        inline_data=types.FunctionResponseBlob(
                            mime_type="image/png",
                            data=screenshot_bytes))
                ]
            )
        )
    return function_responses



import time
from typing import Any, List, Tuple
from playwright.sync_api import sync_playwright

from google import genai
from google.genai import types
from google.genai.types import Content, Part
import os 
from dotenv import load_dotenv
load_dotenv
import os 
from dotenv import load_dotenv
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
# Constants for screen dimensions
SCREEN_WIDTH = 1440
SCREEN_HEIGHT = 900

# Setup Playwright
print("Initializing browser...")
playwright = sync_playwright().start()
browser = playwright.chromium.launch(headless=False)
context = browser.new_context(viewport={"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT})
page = context.new_page()

# Define helper functions. Copy/paste from steps 3 and 4
# def denormalize_x(...)
# def denormalize_y(...)
# def execute_function_calls(...)
# def get_function_responses(...)

try:
    # Go to initial page
    page.goto("https://hackcbs.tech/")

    # Configure the model (From Step 1)
    config = types.GenerateContentConfig(
        tools=[types.Tool(computer_use=types.ComputerUse(
            environment=types.Environment.ENVIRONMENT_BROWSER
        ))],
        thinking_config=types.ThinkingConfig(include_thoughts=True),
    )

    # Initialize history
    initial_screenshot = page.screenshot(type="png")
    USER_PROMPT = "Go to hackcbs.tech and feedback about the website its layout , UI/UX and validate its idea ."
    print(f"Goal: {USER_PROMPT}")

    contents = [
        Content(role="user", parts=[
            Part(text=USER_PROMPT),
            Part.from_bytes(data=initial_screenshot, mime_type='image/png')
        ])
    ]

    # Agent Loop
    turn_limit = 5
    for i in range(turn_limit):
        print(f"\n--- Turn {i+1} ---")
        print("Thinking...")
        response = client.models.generate_content(
            model='gemini-2.5-computer-use-preview-10-2025',
            contents=contents,
            config=config,
        )

        candidate = response.candidates[0]
        contents.append(candidate.content)

        has_function_calls = any(part.function_call for part in candidate.content.parts)
        if not has_function_calls:
            text_response = " ".join([part.text for part in candidate.content.parts if part.text])
            print("Agent finished:", text_response)
            break

        print("Executing actions...")
        results = execute_function_calls(candidate, page, SCREEN_WIDTH, SCREEN_HEIGHT)

        print("Capturing state...")
        function_responses = get_function_responses(page, results)

        contents.append(
            Content(role="user", parts=[Part(function_response=fr) for fr in function_responses])
        )

finally:
    # Cleanup
    print("\nClosing browser...")
    browser.close()
    playwright.stop()