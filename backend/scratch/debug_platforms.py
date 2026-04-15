from playwright.sync_api import sync_playwright
import time
import os

def debug_platforms():
    os.makedirs("debug", exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # 1. Skillbox
        print("Debugging Skillbox...")
        try:
            page.goto("https://www.skillbox.co/events?city=hyderabad", wait_until="networkidle", timeout=60000)
            time.sleep(5)
            page.screenshot(path="debug/skillbox.png")
            with open("debug/skillbox.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            links = page.query_selector_all("a[href*='/events/']")
            print(f"Skillbox: found {len(links)} event links")
        except Exception as e:
            print(f"Skillbox Error: {e}")

        # 2. Swiggy
        print("Debugging Swiggy...")
        try:
            page.goto("https://www.swiggy.com/scenes", wait_until="networkidle", timeout=60000)
            time.sleep(5)
            page.screenshot(path="debug/swiggy.png")
            with open("debug/swiggy.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            # Check for city selector
            city_btn = page.query_selector("button:has-text('Hyderabad'), span:has-text('Hyderabad')")
            print(f"Swiggy: Hyderabad link/span found? {'Yes' if city_btn else 'No'}")
        except Exception as e:
            print(f"Swiggy Error: {e}")

        # 3. Sort My Scene
        print("Debugging Sort My Scene...")
        try:
            # Try a different URL format
            page.goto("https://www.sortmyscene.com/city-events/hyderabad", wait_until="networkidle", timeout=60000)
            time.sleep(5)
            page.screenshot(path="debug/sortmyscene.png")
            with open("debug/sortmyscene.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            links = page.query_selector_all("a[href*='event']")
            print(f"Sort My Scene: found {len(links)} event links")
        except Exception as e:
            print(f"Sort My Scene Error: {e}")

        browser.close()

if __name__ == "__main__":
    debug_platforms()
