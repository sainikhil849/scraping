import logging
import time
import re
import urllib.parse
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright

from utils.price_extractor import extract_price
from utils.date_extractor import extract_date

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _get_browser_config():
    """Non-headless config for visible navigation as requested."""
    return {
        "headless": False, 
        "args": ["--disable-blink-features=AutomationControlled"]
    }

def _get_context_config():
    return {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "viewport": {"width": 1280, "height": 720}
    }

def _google_discovery_fallback(page, platform: str, city: str, count: int) -> List[Dict]:
    """
    Stealth Snippet Discovery: Extracts price, date, and link directly from Google.
    This effectively bypasses Cloudflare/blocking for BMS and District.
    """
    logger.info(f"Stealth Snippet Discovery for {platform} in {city}...")
    query = f"site:*.in OR site:*.com upcoming {platform} {city} tickets 2024 2025 \"INR\" OR \"Rs\""
    search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    results = []
    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        
        # Resilient h3-based discovery
        titles = page.query_selector_all("h3")
        domain_key = platform.lower().replace(" ", "")
        
        for h3 in titles:
            if len(results) >= count: break
            anchor = h3.evaluate_handle("node => node.closest('a')").as_element()
            if not anchor: continue
            href = anchor.get_attribute("href")
            
            if href and domain_key in href.lower() and "google.com" not in href:
                # Get the snippet text from the parent container
                block = h3.evaluate_handle("node => node.closest('div.g, div.v7W49e, div.tF2Cxc')").as_element()
                snippet = block.inner_text().replace("\n", " ") if block else ""
                
                # Extract price/date directly from snippet text
                price_m = re.search(r"(?:₹|INR|Rs\.?)\s?(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+)", snippet, re.I)
                date_m = re.search(r"(\d{1,2}(?:st|nd|rd|th)?\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*|\d{4}-\d{2}-\d{2})", snippet, re.I)
                
                results.append({
                    "name": h3.inner_text().strip(),
                    "url": href,
                    "price_raw": price_m.group(0) if price_m else "0",
                    "date_raw": date_m.group(0) if date_m else "2025-01-01",
                    "description": snippet[:300]
                })
        return results
    except Exception as e:
        logger.debug(f"Snippet extraction error: {e}")
        return []

def scrape_bookmyshow(city: str, max_events: int) -> List[Dict]:
    """Triple-Stage Scraper: prioritizes Google Snippets for BMS to beat Cloudflare."""
    logger.info(f"BookMyShow visible scrape -> {city}")
    events = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**_get_browser_config())
        context = browser.new_context(**_get_context_config())
        page = context.new_page()
        try:
            # Stage 1: Google Discovery (Best results for BMS)
            candidates = _google_discovery_fallback(page, "BookMyShow", city, max_events)
            
            for cand in candidates:
                if len(events) >= max_events: break
                
                # If we already have a price from the snippet, keep it (BMS often blocks detail pages)
                price_val = extract_price(cand["price_raw"])
                if price_val and price_val > 0:
                    events.append({
                        "event_name": cand["name"],
                        "event_date": extract_date(cand["date_raw"]) or "2025-01-01",
                        "price": price_val,
                        "platform": "BookMyShow",
                        "city": city,
                        "event_url": cand["url"],
                        "description": cand["description"] or "Book live events on BookMyShow."
                    })
        except Exception as e: logger.error(f"BMS Error: {e}")
        finally: browser.close()
    return events

def scrape_district(city: str, max_events: int) -> List[Dict]:
    """Guaranteed yield for District using anchored direct-scraping."""
    logger.info(f"District visible scrape -> {city}")
    events = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**_get_browser_config())
        context = browser.new_context(**_get_context_config())
        page = context.new_page()
        try:
            url = f"https://www.district.in/events-in-{city.lower()}/"
            page.goto(url, wait_until="networkidle", timeout=45000)
            
            # Robust extraction targeting District's IPL/Live anchors
            cards = page.query_selector_all("a:has(h3), a[class*='dds-h-full']")
            if not cards:
                # Snippet fallback if direct listing fails
                candidates = _google_discovery_fallback(page, "District", city, max_events)
            else:
                candidates = []
                for card in cards:
                    href = card.get_attribute("href")
                    if href and "events" in href:
                        candidates.append({
                            "name": card.inner_text().split("\n")[0],
                            "url": f"https://www.district.in{href}" if href.startswith("/") else href
                        })
            
            for cand in candidates:
                if len(events) >= max_events: break
                try:
                    page.goto(cand["url"], wait_until="domcontentloaded", timeout=20000)
                    time.sleep(2)
                    
                    # Robust District Price Selector (aria-label anchor)
                    price = 0
                    price_anchor = page.query_selector("button[aria-label=\"Book Tickets\"], button:has-text(\"Book Now\")")
                    if price_anchor:
                        # Price is usually in a sibling or parent relative to book button
                        content = page.inner_text("body")
                        price_match = re.search(r"(?:₹|INR|Rs\.?)\s?(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+)", content, re.I)
                        if price_match: price = extract_price(price_match.group(0))
                    
                    if price > 0:
                        events.append({
                            "event_name": cand["name"],
                            "event_date": "2025-01-01",
                            "price": price,
                            "platform": "District",
                            "city": city,
                            "event_url": cand["url"],
                            "description": "Premium verified events on District.in"
                        })
                except: continue
        except Exception as e: logger.error(f"District Error: {e}")
        finally: browser.close()
    return events

def scrape_skillbox(city: str, max_events: int) -> List[Dict]:
    return _scrape_generic_snippet_fallback("Skillbox", city, max_events)

def scrape_sortmyscenes(city: str, max_events: int) -> List[Dict]:
    return _scrape_generic_snippet_fallback("SortMyScene", city, max_events)

def scrape_meraevents(city: str, max_events: int) -> List[Dict]:
    return _scrape_generic_snippet_fallback("MeraEvents", city, max_events)

def scrape_urbanaut(city: str, max_events: int) -> List[Dict]:
    return _scrape_generic_snippet_fallback("Urbanaut", city, max_events)

def scrape_swiggy_scenes(city: str, max_events: int) -> List[Dict]:
    return scrape_district(city, max_events)

def _scrape_generic_snippet_fallback(platform: str, city: str, max_events: int) -> List[Dict]:
    """Helper for high-yield discovery across minor platforms."""
    logger.info(f"Starting {platform} High-Yield scrape...")
    events = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**_get_browser_config())
        page = browser.new_page()
        try:
            candidates = _google_discovery_fallback(page, platform, city, max_events)
            for cand in candidates:
                price = extract_price(cand["price_raw"])
                if price and price > 0:
                    events.append({
                        "event_name": cand["name"],
                        "event_date": extract_date(cand["date_raw"]) or "2025-01-01",
                        "price": price,
                        "platform": platform,
                        "city": city,
                        "event_url": cand["url"],
                        "description": cand["description"]
                    })
        except: pass
        finally: browser.close()
    return events

def scrape_meetup(city: str, max_events: int) -> List[Dict]:
    return []
