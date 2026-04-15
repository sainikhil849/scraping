from playwright.sync_api import sync_playwright
import time

def check_platforms():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # 1. Skillbox
        print("\n--- Skillbox ---")
        try:
            page.goto("https://www.skillbox.co/events?city=hyderabad", timeout=60000)
            time.sleep(5)
            links = page.query_selector_all("a[href*='/events/']")
            print(f"URL: {page.url}")
            print(f"Found {len(links)} event links")
            if links:
                print(f"Example link: {links[0].get_attribute('href')}")
        except Exception as e:
            print(f"Error: {e}")

        # 2. Swiggy Scenes
        print("\n--- Swiggy Scenes ---")
        try:
            page.goto("https://www.swiggy.com/scenes?city=hyderabad", timeout=60000)
            time.sleep(5)
            links = page.query_selector_all("a[href*='/event']")
            print(f"URL: {page.url}")
            print(f"Found {len(links)} event links")
        except Exception as e:
            print(f"Error: {e}")

        # 3. Sort My Scene
        print("\n--- Sort My Scene ---")
        try:
            page.goto("https://www.sortmyscene.com/events/hyderabad", timeout=60000)
            time.sleep(5)
            links = page.query_selector_all("a[href*='event']")
            print(f"URL: {page.url}")
            print(f"Found {len(links)} event links")
        except Exception as e:
            print(f"Error: {e}")

        browser.close()

if __name__ == "__main__":
    check_platforms()
