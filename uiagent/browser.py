from time import sleep
from typing import Optional, List, Tuple
from playwright.sync_api import sync_playwright, Page, ElementHandle, Locator, Browser
from enum import Enum

class Action(Enum):
    NONE = "none"
    CLICK = "click"
    TYPE = "type"
    HOVER = "hover"
    BACK = "back"
    CANCEL = "cancel"

# List of page history, so we can go back. The uage pattern is linear - clicking certain
# link may open a new tab. The agent may decide to go back, and we will close the
# tab when going back from the top of that tab.
page_history = []

def is_element_outside_viewport(page: Page, element: ElementHandle) -> bool:
    if not element.is_visible():
        return True
    # Get the element's bounding box
    bounding_box = element.bounding_box()
    if not bounding_box or bounding_box['width'] < 10 or bounding_box['height'] < 10:
        return True  # Element is not rendered (e.g., display: none)
    # Get the viewport dimensions
    viewport = page.viewport_size
    # Check if any part of the element is outside the viewport
    if (
        bounding_box['x'] < 0 or
        bounding_box['y'] < 0 or
        bounding_box['x'] + bounding_box['width'] > viewport['width'] or
        bounding_box['y'] + bounding_box['height'] > viewport['height']
    ):
        return True
    return False

def find_elements_by_text(page: Page, text: str, selector : str='*') -> Optional[List[Page]]:
    try:
        # Find all elements that contain the text string
        elements = page.query_selector_all(f'{selector}:has-text("{text}")')
        if len(elements) == 0:
            raise Exception(f"No element found with text: {text}")
        return [element for element in elements if not is_element_outside_viewport(page, element)]
    except Exception as e:
        print(f"Error: {str(e)}")
        return None
    
def find_button(page: Page, element_text: str) -> Locator:
    elements = page.get_by_role("button", name=element_text)
    if elements.count() > 0:
        return elements
    elements = page.locator(f'button:has-text("{element_text}"), a:has-text("{element_text}"), [role="button"]:has-text("{element_text}")')
    if elements.count() > 0:
        return elements
    return page.locator(f'*:has-text("{element_text}")')

def find_link(page: Page, element_text: str) -> Locator:
    elements = page.get_by_role("link", name=element_text)
    if elements.count() > 0:
        return elements
    elements = page.locator(f'a:has-text("{element_text}"), [role="link"]:has-text("{element_text}")')
    if elements.count() > 0:
        return elements
    return find_button(page, element_text)
    
def find_checkbox(page: Page, element_text: str) -> Locator:
    elements = page.get_by_role("checkbox", name=element_text)
    if elements.count() > 0:
        return elements
    elements = page.locator(f'input[type="checkbox"]:has-text("{element_text}"), input[type="radio"]:has-text("{element_text}")')
    if elements.count() > 0:
        return elements
    return find_link(page, element_text)

def find_radio(page: Page, element_text: str) -> Locator:
    elements = page.get_by_role("radio", name=element_text)
    if elements.count() > 0:
        return elements
    elements = page.locator(f'input[type="checkbox"]:has-text("{element_text}"), input[type="radio"]:has-text("{element_text}")')
    if elements.count() > 0:
        return elements
    return find_checkbox(page, element_text)

def find_textarea(page: Page, element_text: str) -> Locator:
    elements = page.get_by_role("textbox", name=element_text)
    if elements.count() > 0:
        return elements
    elements = page.get_by_label(element_text)
    if elements.count() > 0:
        return elements
    elements = page.get_by_placeholder(element_text)
    if elements.count() > 0:
        return elements
    return page.locator(f'textarea:has-text("{element_text}")')


# Check if the first element is inside the second element
def is_inside_element(first: ElementHandle, second: ElementHandle) -> bool:
    first_bounding_box = first.bounding_box()
    second_bounding_box = second.bounding_box()
    if first_bounding_box is None or second_bounding_box is None:
        return False
    f_x = first_bounding_box['x'] if first_bounding_box['x'] > 0 else 0
    f_y = first_bounding_box['y'] if first_bounding_box['y'] > 0 else 0
    s_x = second_bounding_box['x'] if second_bounding_box['x'] > 0 else 0
    s_y = second_bounding_box['y'] if second_bounding_box['y'] > 0 else 0
    return (
        f_x >= s_x and
        f_y >= s_y and
        f_x + first_bounding_box['width'] <= s_x + second_bounding_box['width'] and
        f_y + first_bounding_box['height'] <= s_y + second_bounding_box['height']
    )

# Given a locator, return element array of all the independent inner most elements
def get_inner_elements(elements: Locator) -> List[ElementHandle]:
        previous = None
        res = []
        for e in elements.all():
            if not e.is_visible() or is_element_outside_viewport(page, e):
                continue
            if previous is not None and not is_inside_element(e, previous):
                res.append(previous)
            previous = e
        if previous is not None:
            res.append(previous)
        return res

# Gather the visible elements
def get_visible_elements(page: Page, selector: str) -> List[ElementHandle]:
    elements = page.query_selector_all(selector)
    res = []
    for i, element in enumerate(elements):
        try:
            if not is_element_outside_viewport(page, element):
                res.append(element)
        except Exception as e:
            print(f"Error processing element: {e}")
    return res

def draw_bounding_box(page, bounding_box, number):
    # JavaScript code to create and style a bounding box with a small number in the top-left corner
    js_script = f"""
        const boundingBox = {bounding_box};
        
        // Create and style the bounding box
        const rect = document.createElement('div');
        rect.id = 'custom-bounding-box-{number}';
        rect.style.position = 'absolute';
        rect.style.left = boundingBox.x + 'px';
        rect.style.top = boundingBox.y + 'px';
        rect.style.width = boundingBox.width + 'px';
        rect.style.height = boundingBox.height + 'px';
        rect.style.border = '2px solid red';  // red border for visibility
        rect.style.zIndex = '9000000000000000';  // Ensures the box is on top of other elements
        document.body.appendChild(rect);
        
        // Create and style the number element
        const numberElem = document.createElement('div');
        numberElem.id = 'custom-bounding-box-tl-{number}';
        numberElem.textContent = '{number}';
        numberElem.style.position = 'absolute';
        numberElem.style.padding = '5px';
        numberElem.style.left = (boundingBox.x + (boundingBox.width - 14 - 2)/2) + 'px';
        numberElem.style.top = (boundingBox.y + (boundingBox.height - 14 - 2)/2)  + 'px';
        numberElem.style.fontSize = '14px'; 
        numberElem.style.fontWeight = 'bold'; 
        numberElem.style.backgroundColor = 'rgba(255, 255, 255, 1.0)';
        numberElem.style.color = 'red';
        numberElem.style.zIndex = '9900000000000000';  // Higher z-index than the box
        document.body.appendChild(numberElem);
    """
    page.evaluate(js_script)

def clear_bounding_box(page: Page, number) -> None:
    js_script = f"""
        const rect = document.getElementById('custom-bounding-box-{number}');
        if (rect) rect.remove();
        const tl = document.getElementById('custom-bounding-box-tl-{number}');
        if (tl) tl.remove();
    """
    page.evaluate(js_script)

def get_actionable_elements(page: Page) -> List[ElementHandle]:
    selectors = [
        "a",                    # Links
        "button",               # Button elements
        "input[type='button']", # Input buttons
        "input[type='submit']", # Input submit buttons
        "input[type='reset']",  # Input reset buttons
        # "input[type='image']",  # Image buttons
        "[role='button']",      # Elements with role="button"
        "[onclick]",            # Elements with an inline click handler
        # "label",                # Labels (can be clicked to focus associated inputs)
        "select",               # Dropdowns (clickable to open options)
        "textarea",             # Textareas (clickable to focus)
        # "div[role='button']",   # Divs that are styled as buttons
        # "span[role='button']",  # Spans that are styled as buttons
        # "li",                   # List items (often used in menus or dropdowns)
        # "img",                  # Images (can be clickable)
        # "svg",                  # SVG elements (can be used as icons or buttons)
        # "area",                 # Image map areas
        "[tabindex]",           # Elements with tabindex (can be made focusable and clickable)
        "[contenteditable='true']", # Editable elements (like divs, spans)
        # "summary",              # Summary elements in a <details> block (expandable)
        # "details"               # Clickable details elements
    ]
    def add_element(el):
        if is_element_outside_viewport(page, el):
            return
        bounding_box = element.bounding_box()
        # use the tuple of bounding box dimensions as id
        location = (bounding_box['x'], bounding_box['y'], bounding_box['width'], bounding_box['height'])
        if location not in unique_locations:
            unique_locations.add(location)
            unique_elements.append(el)

    # Gather the unique visible elements. We use the bounding box left corner 10x10 area as
    # a unique identifier. This is where we write the id. The id is small, and thus it's
    # not possible to have 2 real UI elements overlapping. We just need to keep one.
    unique_elements = []
    unique_locations = set()
    for selector in selectors:
        elements = get_visible_elements(page, selector)
        for element in elements:
            add_element(element)

    aria_elements = page.query_selector_all('[aria-label]')
    for element in aria_elements:
        add_element(element)
    aria_elements = page.query_selector_all('[aria-labelledby]')
    for element in aria_elements:
        add_element(element)
    return unique_elements

def draw_actionable_elements(page: Page, unique_elements: List[ElementHandle]) -> None:
    # Print the unique elements
    for index, element in enumerate(unique_elements):
        # print(f"{element.bounding_box()}: {element}")
        draw_bounding_box(page, element.bounding_box(), index)

def clear_actionable_elements(page: Page, unique_elements: List[ElementHandle]) -> None:
    # clear things up
    for index, element in enumerate(unique_elements):
        clear_bounding_box(page, index)

# This assumes a well behaving website - one popup at a time. It's not 100% reliable.
# Add locking etc later.
def handle_popup(popup):
    global page_history
    page_history.append(popup)

def get_current_page() -> Optional[Page]:
    if len(page_history) == 0:
        return None
    page = page_history[-1]
    page.wait_for_load_state("load")
    return page

def start_browser() -> Browser:
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    return browser

def open_page(browser: Browser) -> Page:
    # Use a somewhat random spec so that it's less likely to be flagged as a bot.
    context = browser.new_context(
        viewport={"width": 1381, "height": 998},
    )
    context.on('page', handle_popup)
    page = context.new_page()
    return page

# do action on element.
def do_action_impl(page: Page, element: ElementHandle, action: Action, text: Optional[str]) -> None:
    history_len = len(page_history)
    if action == Action.CLICK:
        element.click()
    elif action == Action.HOVER:
        element.hover()
    elif action == Action.BACK:
        prev = page.go_back()
        if prev is None:
            # we simulate the single tab behavior. We just close this one and go back.
            page.close()
            page_history.pop()
    elif action == Action.TYPE:
        # element.type(text)
        hit_enter = False
        if len(text) >= 5 and text[-5:] == 'ENTER':
            hit_enter = True
            text = text[:-5]
        page.keyboard.type(text)
        if hit_enter:
            page.keyboard.press('Enter')
    elif action == Action.CANCEL:
        page.keyboard.press('Escape')
    else:
        raise Exception(f"Unknown action: {action}")

def do_action(page: Page, elements: List[ElementHandle], cmd: dict) -> None:
    action = Action(cmd['action'])
    location = int(cmd['location'])
    if location >= len(elements):
        raise Exception(f"Invalid location: {location} - it's too big")
    element = elements[location]
    text = cmd['text'] if 'text' in cmd else None
    do_action_impl(page, element, action, text)

if __name__ == "__main__":
    # simple test code for running in debugger
    browser = start_browser()
    page = open_page(browser)
    while True:
        page = get_current_page()
        page.wait_for_load_state("load")
        elements = get_actionable_elements(page)
        draw_actionable_elements(page, elements)
        clear_actionable_elements(page, elements)
        sleep(1)