from uiagent.browser import get_current_page, start_browser, open_page, get_actionable_elements, clear_actionable_elements, draw_actionable_elements

if __name__ == "__main__":
    browser = start_browser()
    page = open_page(browser)
    while True:
        page = get_current_page()
        elements = get_actionable_elements(page)
        draw_actionable_elements(page, elements)
        clear_actionable_elements(page, elements)