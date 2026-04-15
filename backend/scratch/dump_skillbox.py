from playwright.sync_api import sync_playwright

def dump_skillbox_html():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print("Navigating to Skillbox Hyderabad page...")
        page.goto("https://www.skillbox.co/events/hyderabad", wait_until="networkidle")
        page.wait_for_timeout(5000)
        
        # Dump unique hrefs
        hrefs = page.evaluate("() => Array.from(document.querySelectorAll('a')).map(a => a.href)")
        unique_hrefs = sorted(list(set(hrefs)))
        print(f"Total unique links: {len(unique_hrefs)}")
        for h in unique_hrefs:
            if "/events/" in h or "/event/" in h:
                print(f"EVENT LINK: {h}")
            elif "skillbox.co/spot" in h:
                print(f"POTENTIAL SPOT LINK: {h}")
        
        # Dump text
        text = page.inner_text("body")
        print("\n--- BODY SAMPLE (First 500 chars) ---")
        print(text[:500])
        
        browser.close()

if __name__ == "__main__":
    dump_skillbox_html()
