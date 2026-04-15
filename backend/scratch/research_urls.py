from playwright.sync_api import sync_playwright
import time

def research_urls():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        print("\n--- Skillbox Search ---")
        try:
            page.goto("https://www.skillbox.co/events", timeout=60000)
            time.sleep(3)
            # Find city links or dropdown
            city_el = page.query_selector("button:has-text('City'), [class*='city']")
            if city_el:
                print("Found city selector button")
            
            # Check for links with /events/
            links = page.query_selector_all("a[href*='/events/']")
            if links:
                print(f"Found {len(links)} event links on main page")
                print(f"Example: {links[0].get_attribute('href')}")
        except Exception as e:
            print(f"Skillbox Error: {e}")

        print("\n--- Sort My Scene Search ---")
        try:
            page.goto("https://www.sortmyscene.com", timeout=60000)
            time.sleep(3)
            # Find city links
            city_links = page.query_selector_all("a[href*='/city/'], a[href*='/events/']")
            for l in city_links:
                href = l.get_attribute("href")
                if "hyderabad" in href.lower():
                    print(f"Found Hyderabad link: {href}")
        except Exception as e:
            print(f"Sort My Scene Error: {e}")

        print("\n--- Swiggy Scenes Location Check ---")
        try:
            page.goto("https://www.swiggy.com/scenes", timeout=60000)
            time.sleep(5)
            # Look for location buttons
            loc_btn = page.query_selector("button:has-text('Location'), [class*='location']")
            if loc_btn:
                print("Found location button")
                loc_btn.click()
                time.sleep(2)
                page.keyboard.type("Hyderabad")
                time.sleep(2)
                print("Typed Hyderabad, checking results...")
        except Exception as e:
            print(f"Swiggy Error: {e}")

        browser.close()

if __name__ == "__main__":
    research_urls()
