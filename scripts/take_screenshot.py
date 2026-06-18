"""Capture a screenshot of the Streamlit app for visual PR confirmation."""

from playwright.sync_api import sync_playwright
import time
import json
import os


def capture():
    config_path = ".github/screenshot_target.json"
    target_path = ""
    target_selector = None
    full_page = True

    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
            target_path = config.get("path", "")
            target_selector = config.get("selector")
            full_page = config.get("full_page", True)

    base_url = "http://localhost:8501"
    url = f"{base_url}/{target_path}".rstrip("/") if target_path else base_url

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(url)

        # Wait for Streamlit to finish loading (websocket + render)
        time.sleep(5)

        if target_selector:
            element = page.locator(target_selector)
            element.screenshot(path="screenshot.png")
        else:
            page.screenshot(path="screenshot.png", full_page=full_page)

        browser.close()


if __name__ == "__main__":
    capture()
