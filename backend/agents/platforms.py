import time
import json
import re
import logging
from typing import List, Dict, Optional
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# BOOKMYSHOW — L1: __INITIAL_STATE__ + detail-page price/desc
# ══════════════════════════════════════════════════════════════
class BookMyShowAgent(BaseAgent):
    def __init__(self):
        super().__init__("BookMyShow", "https://in.bookmyshow.com/explore/events-hyderabad")

    def _perform_scraping_sync(
        self, page, location: str, target_count: int, max_price: Optional[int]
    ) -> List[Dict]:
        try:
            city = location.lower().split(",")[0].strip()
            url = f"https://in.bookmyshow.com/explore/events-{city}"
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            self._deep_scroll_page(page, scrolls=6)

            raw_candidates = []

            # L1a — Window state (fast path)
            state = self._extract_window_object(page, "__INITIAL_STATE__") or {}
            explore = state.get("explore", {})
            for group in explore.get("groups", []):
                for item in group.get("events", []):
                    slug = item.get("eventUrl")
                    if slug:
                        raw_candidates.append({
                            "name":  item.get("eventName"),
                            "url":   f"https://in.bookmyshow.com{slug}",
                            "date":  item.get("displayDate"),
                            "price": item.get("price"),
                        })

            # L1b — DOM fallback when state is empty (Cloudflare block)
            if not raw_candidates:
                for a in page.query_selector_all("a[href*='/events/']"):
                    href = a.get_attribute("href") or ""
                    if href.count("/") >= 2:
                        full_url = (
                            f"https://in.bookmyshow.com{href}"
                            if href.startswith("/") else href
                        )
                        name_el = a.query_selector("h3, h4, [class*='title'], [class*='name']")
                        raw_candidates.append({
                            "name": name_el.inner_text().strip() if name_el else None,
                            "url":  full_url,
                        })

            # L1c — Visit detail pages to get price + description from JSON-LD
            enriched = []
            for cand in raw_candidates[:target_count * 3]:
                detail_url = cand.get("url", "")
                if not detail_url or "google.com" in detail_url:
                    continue
                try:
                    resp = page.goto(detail_url, wait_until="domcontentloaded", timeout=18000)
                    if resp and resp.status < 400:
                        # JSON-LD first
                        for ld in self._extract_json_ld(page):
                            if "event" in str(ld.get("@type", "")).lower():
                                offer = ld.get("offers") or {}
                                if isinstance(offer, list): offer = offer[0] if offer else {}
                                ld_price = str(offer.get("price", "") or "")
                                if ld_price and ld_price != "0":
                                    cand["price"] = ld_price
                                if not cand.get("date"):
                                    cand["date"] = ld.get("startDate") or ld.get("startDateTime", "")
                                if not cand.get("description"):
                                    cand["description"] = ld.get("description", "")
                                break

                        # CSS fallback for price
                        if not cand.get("price") or cand.get("price") in ("0", 0):
                            for sel in [
                                "[data-testid='price']", "[class*='price']",
                                "[class*='Price']", "[class*='amount']",
                            ]:
                                el = page.query_selector(sel)
                                if el:
                                    txt = el.inner_text().strip()
                                    pm = re.search(r"[\d,]+", txt.replace(",", ""))
                                    if pm:
                                        cand["price"] = pm.group().replace(",", "")
                                        break

                        # meta description fallback
                        if not cand.get("description"):
                            meta = page.query_selector("meta[name='description'], meta[property='og:description']")
                            if meta:
                                cand["description"] = meta.get_attribute("content") or ""

                except Exception as exc:
                    logger.debug(f"BMS detail visit failed for {detail_url}: {exc}")

                enriched.append(cand)

            return enriched
        except Exception as exc:
            logger.debug(f"BookMyShow L1 error: {exc}")
            return []

    def _parse_api_json(self, data) -> List[Dict]:
        """Parse BMS event API shards intercepted during page load."""
        results = []
        try:
            def _recurse(obj):
                if isinstance(obj, dict):
                    if "eventName" in obj and "eventUrl" in obj:
                        results.append({
                            "name":  obj.get("eventName"),
                            "url":   f"https://in.bookmyshow.com{obj['eventUrl']}",
                            "date":  obj.get("displayDate"),
                            "price": obj.get("price"),
                        })
                    for v in obj.values():
                        _recurse(v)
                elif isinstance(obj, list):
                    for item in obj:
                        _recurse(item)
            _recurse(data)
        except Exception:
            pass
        return results


# ══════════════════════════════════════════════════════════════
# DISTRICT — Layer 1: __NEXT_DATA__ deep recursive search
# ══════════════════════════════════════════════════════════════
class DistrictAgent(BaseAgent):
    def __init__(self):
        super().__init__("District", "https://www.district.in/events-in-hyderabad/")

    def _perform_scraping_sync(
        self, page, location: str, target_count: int, max_price: Optional[int]
    ) -> List[Dict]:
        try:
            city = location.lower().split(",")[0].strip()
            url = f"https://www.district.in/events-in-{city}/"
            page.goto(url, wait_until="networkidle", timeout=60000)
            self._deep_scroll_page(page, scrolls=6)

            candidates = []

            # L1a — __NEXT_DATA__ deep parse
            next_data = self._extract_window_object(page, "__NEXT_DATA__") or {}
            if next_data:
                def _find_events(obj):
                    if isinstance(obj, list):
                        for item in obj:
                            if isinstance(item, dict) and "name" in item and "slug" in item:
                                yield item
                    if isinstance(obj, dict):
                        for v in obj.values():
                            yield from _find_events(v)

                for item in _find_events(next_data):
                    slug = item.get("slug", "")
                    if "/events/" in slug or "/activities/" in slug:
                        full_url = (
                            f"https://www.district.in{slug}"
                            if not slug.startswith("http")
                            else slug
                        )
                        candidates.append({
                            "name":  item.get("name"),
                            "url":   full_url,
                            "price": item.get("min_price"),
                            "date":  item.get("start_datetime") or item.get("startDate"),
                        })

            # L1b — DOM card fallback
            if not candidates:
                for a in page.query_selector_all("a:has(h3), a:has(h5), a[class*='dds-h-full']"):
                    href = a.get_attribute("href") or ""
                    if "/events/" in href or "/activities/" in href:
                        full_url = (
                            f"https://www.district.in{href}"
                            if href.startswith("/") else href
                        )
                        inner = a.inner_text()
                        price_m = re.search(
                            r"(?:₹|INR|Rs\.?)\s?(\d[\d,]*)", inner, re.I
                        )
                        candidates.append({
                            "name":  inner.split("\n")[0].strip(),
                            "url":   full_url,
                            "price": price_m.group(1).replace(",", "") if price_m else None,
                        })

            return candidates[:target_count * 3]
        except Exception as exc:
            logger.debug(f"District L1 error: {exc}")
            return []

    def _parse_api_json(self, data) -> List[Dict]:
        results = []
        try:
            def _recurse(obj):
                if isinstance(obj, dict):
                    if "name" in obj and ("slug" in obj or "eventUrl" in obj):
                        slug = obj.get("slug") or obj.get("eventUrl", "")
                        if "/events/" in slug or "/activities/" in slug:
                            results.append({
                                "name":  obj.get("name"),
                                "url":   f"https://www.district.in{slug}" if not slug.startswith("http") else slug,
                                "price": obj.get("min_price") or obj.get("price"),
                                "date":  obj.get("start_datetime") or obj.get("startDate"),
                            })
                    for v in obj.values():
                        _recurse(v)
                elif isinstance(obj, list):
                    for item in obj:
                        _recurse(item)
            _recurse(data)
        except Exception:
            pass
        return results


# ══════════════════════════════════════════════════════════════
# SWIGGY SCENES — Swiggy's own event platform
# ══════════════════════════════════════════════════════════════
class SwiggyScenesAgent(BaseAgent):
    def __init__(self):
        super().__init__("Swiggy Scenes", "https://www.swiggy.com/scenes")

    def _perform_scraping_sync(
        self, page, location: str, target_count: int, max_price: Optional[int]
    ) -> List[Dict]:
        try:
            city = location.lower().replace(" ", "").split(",")[0].strip()
            # 1. Open Scenes main page
            page.goto("https://www.swiggy.com/scenes", wait_until="networkidle", timeout=60000)
            
            # 2. Location Interaction (Essential for yield)
            try:
                # Look for typical Swiggy location selector buttons
                loc_btn = page.query_selector("button:has-text('Location'), [class*='location']")
                if loc_btn:
                    loc_btn.click()
                    time.sleep(1)
                    page.keyboard.type(city)
                    time.sleep(2)
                    page.keyboard.press("Enter")
                    time.sleep(3)
            except Exception:
                # Fallback to URL param if interaction fails
                page.goto(f"https://www.swiggy.com/scenes?city={city}")

            # 3. Deep scroll for discovery
            for _ in range(10):
                page.evaluate("window.scrollBy(0, 3000)")
                time.sleep(1.2)

            candidates = []
            seen = set()

            # Collect event links from card hrefs
            for a in page.query_selector_all("a[href*='/event']"):
                href = a.get_attribute("href") or ""
                if not href or href in seen: continue
                if any(bad in href for bad in ["/scenes\n", "?city=", "/home"]): continue
                
                full = f"https://www.swiggy.com{href}" if href.startswith("/") else href
                seen.add(href)
                
                # Normalize check for location
                # user_location = city (normalized above)
                # event_location = extraction from card or detail
                
                # Inline data
                name_el = a.query_selector("h1, h2, h3, h4, [class*='name'], [class*='title']")
                cand = {
                    "url":  full,
                    "name": name_el.inner_text().strip() if name_el else None
                }
                
                # 4. Mandatory detail hop for robust price/desc/location
                try:
                    page.goto(full, wait_until="domcontentloaded", timeout=15000)
                    
                    # Self-healing location extraction
                    ev_loc = self._self_healing_extract(page, "location") or ""
                    if city in ev_loc.lower().replace(" ", "") or not ev_loc:
                        # Keep event
                        cand["location"] = ev_loc or location
                        cand = self._enrich_event_details(page, cand)
                        candidates.append(cand)
                except Exception:
                    pass
                
                if len(candidates) >= target_count: break

            return candidates
        except Exception as exc:
            logger.debug(f"SwiggyScenesAgent error: {exc}")
            return []


# ══════════════════════════════════════════════════════════════
# SKILLBOX — DOM card scraping + JS data
# ══════════════════════════════════════════════════════════════
class SkillboxAgent(BaseAgent):
    def __init__(self):
        super().__init__("Skillbox", "https://www.skillbox.co/events")

    def _perform_scraping_sync(
        self, page, location: str, target_count: int, max_price: Optional[int]
    ) -> List[Dict]:
        try:
            city = location.lower().split(",")[0].strip()
            # Try /explore first as /events is 404
            url = f"https://www.skillbox.co/explore"
            page.goto(f"{url}?city={city.capitalize()}", wait_until="networkidle", timeout=40000)
            
            # 12x Deep scroll
            for _ in range(12):
                page.evaluate("window.scrollBy(0, 4000)")
                time.sleep(1)

            seen_hrefs = set()
            event_urls = []
            # FIX: Robust selectors for Skillbox cards
            selectors = [
                ".event-card a", "a[href*='/events/']", 
                "a[href*='/event/']", "a[href*='/spot/']",
                ".listing-card a"
            ]
            for sel in selectors:
                for a in page.query_selector_all(sel):
                    href = a.get_attribute("href") or ""
                    if not href: continue
                    full = f"https://www.skillbox.co{href}" if href.startswith("/") else href
                    if full not in seen_hrefs:
                        path_parts = [p for p in full.replace("https://www.skillbox.co", "").split("/") if p]
                        if len(path_parts) >= 1:
                            seen_hrefs.add(full)
                            event_urls.append(full)

            enriched = []
            for d_url in event_urls:
                if len(enriched) >= target_count: break
                try:
                    page.goto(d_url, wait_until="domcontentloaded", timeout=20000)
                    cand = {"url": d_url}
                    # Self-healing extraction
                    cand["name"] = self._self_healing_extract(page, "title")
                    cand["description"] = self._self_healing_extract(page, "description")
                    cand["location"] = self._self_healing_extract(page, "location") or location
                    
                    cand = self._enrich_event_details(page, cand)
                    enriched.append(cand)
                except Exception:
                    pass

            return enriched
        except Exception as exc:
            logger.debug(f"Skillbox L1 error: {exc}")
            return []

            return enriched
        except Exception as exc:
            logger.debug(f"Skillbox L1 error: {exc}")
            return []


# ══════════════════════════════════════════════════════════════
# SORT MY SCENE — deep scroll (12x) for full event discovery
# ══════════════════════════════════════════════════════════════
class SortMySceneAgent(BaseAgent):
    def __init__(self):
        super().__init__("Sort My Scene", "https://www.sortmyscene.com")

    def _perform_scraping_sync(
        self, page, location: str, target_count: int, max_price: Optional[int]
    ) -> List[Dict]:
        try:
            city = location.lower().split(",")[0].strip()
            page.goto(f"https://www.sortmyscene.com/events/{city}", wait_until="networkidle", timeout=60000)

            candidates = []
            seen = set()
            
            # FIXED: Continuous extraction until target_count reached
            scroll_count = 0
            while len(candidates) < target_count and scroll_count < 20:
                page.evaluate("window.scrollBy(0, 3000)")
                time.sleep(1.5)
                scroll_count += 1
                
                new_links = page.query_selector_all("a[href*='event'], a[href*='show']")
                new_found_in_pass = False
                for a in new_links:
                    href = a.get_attribute("href") or ""
                    if not href or href in seen: continue
                    full = f"https://www.sortmyscene.com{href}" if href.startswith("/") else href
                    if any(x in full for x in ["/city/", "/events/all"]): continue
                    
                    seen.add(href)
                    new_found_in_pass = True
                    
                    # Detail parsing
                    try:
                        # Visit detail page in background
                        ctx = page.context.new_page()
                        ctx.goto(full, wait_until="domcontentloaded", timeout=15000)
                        
                        cand = {
                            "url":  full,
                            "name": self._self_healing_extract(ctx, "title"),
                            "description": self._self_healing_extract(ctx, "description"),
                        }
                        cand = self._enrich_event_details(ctx, cand)
                        candidates.append(cand)
                        ctx.close()
                    except Exception:
                        pass
                    
                    if len(candidates) >= target_count: break
                
                if not new_found_in_pass and scroll_count > 5: break

            return candidates
        except Exception as exc:
            logger.debug(f"SortMyScene L1 error: {exc}")
            return []


# ══════════════════════════════════════════════════════════════
# MERA EVENTS — listing scrape + detail hop for price/date
# ══════════════════════════════════════════════════════════════
class MeraEventsAgent(BaseAgent):
    def __init__(self):
        super().__init__("Mera Events", "https://www.meraevents.com/hyderabad-events")

    def _perform_scraping_sync(
        self, page, location: str, target_count: int, max_price: Optional[int]
    ) -> List[Dict]:
        try:
            city = location.lower().split(",")[0].strip()
            page.goto(f"https://www.meraevents.com/{city}-events", wait_until="networkidle", timeout=60000)
            
            # FIX: Use wait_for_selector for dynamic cards
            try:
                page.wait_for_selector("[class*='event-card'], .event-item, a[href*='/event/']", timeout=10000)
            except Exception:
                pass

            # Scroll loop
            for _ in range(10):
                page.evaluate("window.scrollBy(0, 1500)")
                time.sleep(1)

            candidates = []
            seen = set()
            
            # Card Loop Extraction
            cards = page.query_selector_all("[class*='event-card'], .event-item, div.event, a[href*='/event/']")
            for tile in cards:
                if len(candidates) >= target_count: break
                
                a = tile if tile.tag_name == "a" else tile.query_selector("a[href*='/event/']")
                if not a: continue
                
                href = a.get_attribute("href") or ""
                if not href or href in seen: continue
                seen.add(href)
                
                full = f"https://www.meraevents.com{href}" if href.startswith("/") else href
                
                try:
                    # Detail hop for full data
                    page.goto(full, wait_until="domcontentloaded", timeout=15000)
                    cand = {
                        "url":  full,
                        "title": self._self_healing_extract(page, "title"),
                        "description": self._self_healing_extract(page, "description"),
                        "location": self._self_healing_extract(page, "location") or location
                    }
                    cand = self._enrich_event_details(page, cand)
                    candidates.append(cand)
                except Exception:
                    pass

            return candidates
        except Exception as exc:
            logger.debug(f"MeraEvents L1 error: {exc}")
            return []


# ══════════════════════════════════════════════════════════════
# URBANAUT — tile scraping + mandatory detail hop
# ══════════════════════════════════════════════════════════════
class UrbanautAgent(BaseAgent):
    def __init__(self):
        super().__init__("Urbanaut", "https://urbanaut.app")

    def _perform_scraping_sync(
        self, page, location: str, target_count: int, max_price: Optional[int]
    ) -> List[Dict]:
        try:
            from datetime import datetime as _dt
            from datetime import date as _date
            TODAY = _date.today()
            city = location.lower().split(",")[0].strip()

            # Point directly to city experiences
            page.goto(f"https://urbanaut.app/experiences?city={city}", wait_until="networkidle", timeout=60000)

            candidates = []
            seen = set()
            
            # FIX: Progressive scroll loop for Urbanaut
            scroll_count = 0
            while len(candidates) < target_count and scroll_count < 10:
                page.evaluate("window.scrollBy(0, 2000)")
                time.sleep(1.5)
                scroll_count += 1
                
                links = page.query_selector_all("a[href*='/experience/'], a[href*='/event/'], a[href*='/spot/']")
                new_found = False
                for a in links:
                    href = a.get_attribute("href") or ""
                    full = f"https://urbanaut.app{href}" if href.startswith("/") else href
                    if full in seen: continue
                    if "city=" in full or full.endswith("/"): continue
                    
                    seen.add(full)
                    new_found = True
                    
                    try:
                        ctx = page.context.new_page()
                        ctx.goto(full, wait_until="domcontentloaded", timeout=15000)
                        
                        cand = {
                            "url":  full,
                            "name": self._self_healing_extract(ctx, "title"),
                            "description": self._self_healing_extract(ctx, "description"),
                        }
                        cand = self._enrich_event_details(ctx, cand)
                        
                        # Strict Urbanaut Date Filter (Upcoming Only)
                        if cand.get("date"):
                            try:
                                d_val = cand["date"]
                                parsed = _dt.strptime(d_val, "%Y-%m-%d").date()
                                if parsed < TODAY:
                                    ctx.close()
                                    continue
                            except Exception:
                                # Parsing failed -> keep as "Unknown" (handled by BaseAgent._format_event)
                                pass
                        
                        candidates.append(cand)
                        ctx.close()
                    except Exception:
                        pass
                    
                    if len(candidates) >= target_count: break
                
                if not new_found and scroll_count > 3: break

            return candidates
        except Exception as exc:
            logger.debug(f"Urbanaut L1 error: {exc}")
            return []
        except Exception as exc:
            logger.debug(f"Urbanaut L1 error: {exc}")
            return []


# ══════════════════════════════════════════════════════════════
# MEETUP — API sniffing via network interception
# ══════════════════════════════════════════════════════════════
class MeetupAgent(BaseAgent):
    def __init__(self):
        super().__init__("Meetup", "https://www.meetup.com/find/?location=hyderabad&source=EVENTS")

    def _perform_scraping_sync(
        self, page, location: str, target_count: int, max_price: Optional[int]
    ) -> List[Dict]:
        try:
            city = location.lower().split(",")[0].strip()
            page.goto(
                f"https://www.meetup.com/find/?location={city}&source=EVENTS",
                wait_until="networkidle", timeout=60000,
            )
            # Scroll to trigger lazy-loaded results
            for _ in range(8):
                page.mouse.wheel(0, 5000)
                time.sleep(1.5)

            candidates = []
            seen = set()

            # Primary: DOM event links with depth check
            for a in page.query_selector_all("a[href*='/events/']"):
                href = a.get_attribute("href") or ""
                if "meetup.com" not in href or href in seen:
                    continue
                from urllib.parse import urlparse as _up
                segs = [s for s in _up(href).path.split("/") if s]
                if len(segs) < 2:
                    continue
                seen.add(href)

                inner = a.inner_text()
                date_m = re.search(
                    r"(\d{1,2}(?:st|nd|rd|th)?\s+"
                    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
                    r"(?:\s+\d{4})?|\d{4}-\d{2}-\d{2})",
                    inner, re.I,
                )
                candidates.append({
                    "url":  href,
                    "name": inner.split("\n")[0].strip() or None,
                    "date": date_m.group(1) if date_m else None,
                    # Meetup is typically free — price verified at detail page
                    "price": "0" if re.search(r"\bfree\b", inner, re.I) else None,
                })

            return candidates[:target_count * 3]
        except Exception as exc:
            logger.debug(f"Meetup L1 error: {exc}")
            return []

    def _parse_api_json(self, data) -> List[Dict]:
        """
        Parse Meetup GraphQL / REST JSON captured via API sniffing.
        Handles both paginated REST (/find/events) and GraphQL responses.
        """
        results = []
        try:
            def _recurse(obj):
                if isinstance(obj, dict):
                    # Check for event patterns
                    if "name" in obj and ("link" in obj or "eventUrl" in obj):
                        event_url = obj.get("link") or obj.get("eventUrl", "")
                        if "meetup.com" in str(event_url):
                            # Date extraction with epoch support
                            date_val = None
                            # Meetup timestamps are often in 'time' or 'dateTime' or 'dateTimeStr'
                            ts = obj.get("time") or obj.get("dateTime") or obj.get("startTime")
                            if ts:
                                try:
                                    import datetime as _dt
                                    # Handle epoch ms
                                    ts_float = float(ts)
                                    if ts_float > 1e11: ts_float /= 1000
                                    date_val = _dt.datetime.fromtimestamp(ts_float).strftime("%Y-%m-%d")
                                except:
                                    date_val = str(ts)[:10] if isinstance(ts, str) else None
                            
                            # Price extraction
                            fee = obj.get("fee") or obj.get("eventFee") or {}
                            price = str(fee.get("amount") or fee.get("value") or "")
                            if not price and (obj.get("rsvpLimit") or obj.get("isFree")):
                                price = "0"

                            results.append({
                                "name":        obj.get("name"),
                                "url":         event_url,
                                "date":        date_val,
                                "price":       price or "-1",
                                "description": obj.get("description", "")[:400],
                                "organizer":   obj.get("group", {}).get("name", "Meetup Group"),
                            })
                    for v in obj.values():
                        _recurse(v)
                elif isinstance(obj, list):
                    for item in obj:
                        _recurse(item)
            _recurse(data)
        except Exception:
            pass
        return results


# ══════════════════════════════════════════════════════════════
# Factory
# ══════════════════════════════════════════════════════════════
def get_platform_agent(platform_name: str, location: str = "Hyderabad") -> Optional[BaseAgent]:
    mapping = {
        "BookMyShow":   BookMyShowAgent,
        "District":     DistrictAgent,
        "Swiggy Scenes": SwiggyScenesAgent,
        "Skillbox":     SkillboxAgent,
        "Sort My Scene": SortMySceneAgent,
        "Mera Events":  MeraEventsAgent,
        "Urbanaut":     UrbanautAgent,
        "Urbanot":      UrbanautAgent,   # alias
        "Meetup":       MeetupAgent,
    }
    cls = mapping.get(platform_name)
    return cls() if cls else None
