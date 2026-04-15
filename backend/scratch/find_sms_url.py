from playwright.sync_api import sync_playwright
import time

def find_sortmyscene_url():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        urls_to_try = [
            "https://www.sortmyscene.com/city/hyderabad",
            "https://www.sortmyscene.com/events/hyderabad",
            "https://www.sortmyscene.com/hyderabad/events",
            "https://www.sortmyscene.com/hyderabad"
        ]
        
        for url in urls_to_try:
            print(f"Trying {url}...")
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                print(f"Status for {url}: {page.url}")
                if "not-found" not in page.url and page.query_selector("a[href*='event']"):
                    print(f"SUCCESS: {url} seems valid")
                    return url
            except Exception as e:
                print(f"Error for {url}: {e}")
        
        browser.close()
    return None

if __name__ == "__main__":
    find_sortmyscene_url()
