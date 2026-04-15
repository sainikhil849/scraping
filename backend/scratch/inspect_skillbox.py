from playwright.sync_api import sync_playwright
import time

def inspect_skillbox():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print("Navigating to Skillbox Hyderabad page...")
        # Try both variants
        urls = [
            "https://www.skillbox.co/events/hyderabad",
            "https://www.skillbox.co/events?city=hyderabad"
        ]
        
        for url in urls:
            print(f"\n--- Testing {url} ---")
            page.goto(url, wait_until="networkidle", timeout=60000)
            time.sleep(3)
            
            # Interaction: See if we can trigger City selection if needed
            try:
                city_sel = page.query_selector("button:has-text('City'), [class*='city-selector']")
                if city_sel:
                    print("Found city selector, interaction possible.")
            except: pass
            
            links = page.query_selector_all("a")
            count = 0
            for a in links:
                href = a.get_attribute("href") or ""
                if "/events/" in href or "/event/" in href:
                    if count < 10:
                        print(f"Match: {a.inner_text().strip()[:20]} -> {href}")
                    count += 1
            print(f"Total event-like links found: {count}")
            
        browser.close()

if __name__ == "__main__":
    inspect_skillbox()
