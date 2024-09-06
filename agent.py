import os
import re
import google.generativeai as genai
from google.generativeai.types import ContentDict, File
from pathlib import Path
from datetime import datetime

import yaml
from uiagent.browser import (
    get_actionable_elements,
    clear_actionable_elements,
    draw_actionable_elements,
    get_current_page,
    open_page,
    start_browser,
    do_action,
)

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# Create the model
generation_config = {
  "temperature": 1,
  "top_p": 0.95,
  "top_k": 64,
  "max_output_tokens": 8192,
  "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-pro",
    generation_config=generation_config,
    # safety_settings = Adjust safety settings
    # See https://ai.google.dev/gemini-api/docs/safety-settings
    system_instruction="""
I want you to accomplish a specified task on the UI. I will provide you with the UI screenshots and a task description. For each step, I will always provide 2 screenshots:
* one original screenshot
* one with red bounding box and black number overlays on the UI elements. You will use the number to indicate where you want the mouse to go. The number will be at the center of the bounding box. Please use the original screenshot to find the UI elements, and then the bounding box to find the number.

In response, please ask me to perform actions that you would like to do. For instance, click on a UI element or type some text. If you are not entirely clear about what the page does or what actions are possible, you can ask me to explore by performing specific actions and give you back the screenshot for comparison.

Going forward, please use the above for every step. I'll be your agent, and you must tell me exactly what to do. My response can be either one of the two:
* if there is no error, I will always give you back the screenshot after performing your action
* if there is an error, I will give you the text explaining the error

Please do exactly as I ask and no more. In your response, you should use the following yaml format:

---
reason: <why you want me to do it>
action: <the action you want me to perform, and the only choices are hover, click, type, back, cancel, scroll, none. Action none means the task is done. You should only use hover when you believe hover will reveal sub-menus. Otherwise you can click directly. Click means I will move the mouse there and click. scroll means trigger scroll event for one page, cancel means hit Esc key>
text: <if action is type, this is the text you want me to type. If you want me to hit enter then add ENTER at the end>
location: <if the action is hover or click, this is the location number you want me to hover the mouse or click the mouse>
""",
)

octet_stream_mime_type = "application/octet-stream"

def upload_to_gemini(path: str, mime_type=None) -> File:
    """Uploads the given file to Gemini.

    See https://ai.google.dev/gemini-api/docs/prompting_with_media
    """
    file = genai.upload_file(path, mime_type=mime_type)
    print(f"Uploaded file '{file.display_name}' as: {file.uri}")
    return file

def get_string_between_dashes(text):
    # Use regular expression to capture the string between the first two occurrences of ---
    match = re.search(r'---\s*(.*?)\s*---', text, re.DOTALL)
    if match:
        return match.group(1).strip()  # Extract the string and remove surrounding whitespace
    return None  # Return None if no match is found

if __name__ == "__main__":
    browser = start_browser()
    while True:
        chat_session = model.start_chat()
        task_description = input("Enter a detailed task description: ")
        starting_url = input("Enter a starting URL: ")
        content = ContentDict(
            role="user",
            parts=[task_description],
        )

        # Store all results and artifacts in a temporary directory
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        directory_path = Path(f"/tmp/{current_time}")
        directory_path.mkdir(parents=False, exist_ok=False)

        page = open_page(browser)
        page.goto(starting_url)

        # Now the main task loop. Until the action is none, we get the screenshot and feed to
        # the model
        iter = 0
        while True:
            page = get_current_page()
            # always 2 files in each iteration - <iter>-0.png and <iter>-1.png
            page.screenshot(path=f"{directory_path}/{iter}-0.png")

            elements = get_actionable_elements(page)
            draw_actionable_elements(page, elements)
            page.screenshot(path=f"{directory_path}/{iter}-1.png")

            f0 = upload_to_gemini(f"{directory_path}/{iter}-0.png")
            f1 = upload_to_gemini(f"{directory_path}/{iter}-1.png")

            content['parts'].extend([f0, f1])
            clear_actionable_elements(page, elements)
            
            response = chat_session.send_message(content)
            print(response.text)

            # parse the response.text as yaml.
            try:
                res = yaml.safe_load(get_string_between_dashes(response.text))
                do_action(page, elements, res)
            except Exception as e:
                print(f"Error: {str(e)}")
                exit(1)

            iter += 1
            content = ContentDict(role="user", parts=[])
