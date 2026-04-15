from playwright.sync_api import sync_playwright

def inspect_urbanaut():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print("Navigating to Urbanaut Hyderabad page...")
        page.goto("https://urbanaut.app/?city=Hyderabad", wait_until="networkidle")
        page.wait_for_timeout(5000) # Give extra time for tiles to load
        
        # Take a screenshot to verify what's seen
        page.screenshot(path="debug_urbanaut.png")
        print("Screenshot saved as debug_urbanaut.png")
        
        # Dump links
        links = page.query_selector_all("a")
        print(f"Total links: {len(links)}")
        for i, a in enumerate(links[:20]):
            href = a.get_attribute("href") or ""
            text = a.inner_text().strip()
            print(f"{i}: {text} -> {href}")
            
        browser.close()

if __name__ == "__main__":
    inspect_urbanaut()
