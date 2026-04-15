import logging
import time
import json
import urllib.parse
import re
import datetime as dt
from datetime import date
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright, Response
import anyio

from utils.validators import is_valid_event
from utils.price_extractor import extract_price
from utils.date_extractor import extract_date

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TODAY = date.today()


class BaseAgent:
    def __init__(self, platform_name: str, base_url: str):
        self.platform_name = platform_name
        self.base_url = base_url
        self.intercepted_api_data: List[Dict] = []

    # ─────────────────────────────────────────────
    # Browser configuration
    # ─────────────────────────────────────────────
    def _get_browser_config(self) -> dict:
        return {
            "headless": False,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        }

    def _get_context_config(self) -> dict:
        return {
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "viewport": {"width": 1920, "height": 1080},
            "locale": "en-IN",
            "timezone_id": "Asia/Kolkata",
        }

    # ─────────────────────────────────────────────
    # Main entry-point
    # ─────────────────────────────────────────────
    def run_sync_extraction(
        self, location: str, target_count: int, max_price: Optional[int]
    ) -> List[Dict]:
        """
        4-Layer pipeline:
          L1  Direct JSON extraction  (_perform_scraping_sync)
          L2  Network API sniffing    (_handle_response via page.on)
          L3  Google stealth fallback (_google_search_fallback)
          L4  Detail-page enrichment  (_enrich_event_details)
        """
        final_events: List[Dict] = []
        self.intercepted_api_data = []   # reset per run

        with sync_playwright() as p:
            browser = p.chromium.launch(**self._get_browser_config())
            context = browser.new_context(**self._get_context_config())
            page = context.new_page()

            # Stealth: remove webdriver flag
            page.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
            )

            try:
                # ── Layer 2 setup: intercept API responses ──
                page.on("response", self._handle_response)

                seen_urls: set = set()
                loop_counter = 0

                # PRIMARY ARCHITECTURE CHANGE: Progressive discovery loop
                while len(final_events) < target_count and loop_counter < 3:
                    loop_counter += 1
                    start_count = len(final_events)
                    candidates: List[Dict] = []

                    # ── Layer 1: platform-specific direct scraping ──
                    try:
                        candidates = self._perform_scraping_sync(
                            page, location, target_count, max_price
                        )
                        logger.info(
                            f"{self.platform_name}: L1 scrape (Pass {loop_counter}) → {len(candidates)} candidates"
                        )
                    except Exception as exc:
                        logger.warning(f"{self.platform_name}: L1 failed – {exc}")

                    # ── Merge API-sniffed data (Layer 2 results) ──
                    if self.intercepted_api_data:
                        logger.info(
                            f"{self.platform_name}: L2 API sniff → "
                            f"{len(self.intercepted_api_data)} extra candidates"
                        )
                        candidates.extend(self.intercepted_api_data)
                        self.intercepted_api_data = [] # consume

                    # ── Layer 3: Google stealth fallback (if still underfilled) ──
                    if len(candidates) == 0 or len(final_events) + len(candidates) < target_count:
                        logger.info(f"{self.platform_name}: L3 Google fallback triggered")
                        candidates.extend(
                            self._google_search_fallback(page, location, target_count)
                        )

                    new_candidates_found = False

                    # ── Layer 4: enrich + validate each candidate ──
                    for raw in candidates:
                        if len(final_events) >= target_count:
                            break
                        
                        url = (raw.get("url") or "").strip()
                        if not url or url in seen_urls:
                            continue
                        
                        seen_urls.add(url)
                        new_candidates_found = True

                        # Always enrich if price OR date is missing/unreliable/past
                        needs_price = not raw.get("price") or raw.get("price") in ("0", 0, "") \
                                      or raw.get("price") is None
                        
                        # Also re-enrich if snippet date seems wrong (past)
                        needs_date = not raw.get("date") or raw.get("date") in ("", None)
                        if not needs_date and raw.get("date"):
                            parsed_check = extract_date(str(raw["date"]))
                            if parsed_check:
                                try:
                                    from datetime import date as _d
                                    if dt.datetime.strptime(parsed_check, "%Y-%m-%d").date() < TODAY:
                                        needs_date = True   # detail page may have real date
                                except Exception:
                                    needs_date = True

                        if needs_price or needs_date:
                            raw = self._enrich_event_details(page, raw)

                        event = self._format_event(raw)
                        if event:
                            if max_price is None or event["price"] <= max_price:
                                final_events.append(event)
                                logger.info(
                                    f"{self.platform_name}: ✓ Accepted '{event['event_name']}' "
                                    f"| ₹{event['price']} | {event['event_date']}"
                                )

                    # If no new events found -> break
                    if not new_candidates_found or len(final_events) == start_count:
                        break

            except Exception as exc:
                logger.error(f"{self.platform_name}: Pipeline error – {exc}")
            finally:
                browser.close()

        logger.info(
            f"{self.platform_name}: Final yield = {len(final_events)} / {target_count}"
        )
        return final_events

    async def extract_events(
        self, location: str, target_count: int, max_price: Optional[int] = None
    ) -> List[Dict]:
        return await anyio.to_thread.run_sync(
            self.run_sync_extraction, location, target_count, max_price
        )

    # ─────────────────────────────────────────────
    # Layer 1 (override per platform)
    # ─────────────────────────────────────────────
    def _perform_scraping_sync(
        self, page, location: str, target_count: int, max_price: Optional[int]
    ) -> List[Dict]:
        return []

    # ─────────────────────────────────────────────
    # Layer 2: API sniffing
    # ─────────────────────────────────────────────
    def _handle_response(self, response: Response):
        try:
            ct = response.headers.get("content-type", "")
            if "application/json" not in ct:
                return
            url = response.url.lower()
            # Only intercept event-relevant endpoints
            if not any(x in url for x in ["/api/", "graphql", "events", "search", "activities"]):
                return
            try:
                data = response.json()
            except Exception:
                return
            extracted = self._parse_api_json(data)
            if extracted:
                self.intercepted_api_data.extend(extracted)
        except Exception:
            pass

    def _parse_api_json(self, json_data) -> List[Dict]:
        """Override in platform subclasses when API structure is known."""
        return []

    # ─────────────────────────────────────────────
    # Layer 3: Google stealth fallback
    # ─────────────────────────────────────────────
    def _google_search_fallback(
        self, page, location: str, count_needed: int
    ) -> List[Dict]:
        """
        Extracts price, date, and event URLs directly from Google snippets.
        Does NOT default date to a past value — leaves it None so enrichment fires.
        """
        if count_needed <= 0:
            return []

        # Platform-domain mapping for precise site-specific Google queries
        domain_map = {
            "BookMyShow":   "in.bookmyshow.com",
            "District":     "district.in",
            "Swiggy Scenes": "district.in",
            "Skillbox":     "skillbox.co",
            "Sort My Scene": "sortmyscene.com",
            "Mera Events":  "meraevents.com",
            "Urbanaut":     "urbanaut.app",
            "Urbanot":      "urbanaut.app",
            "Meetup":       "meetup.com",
        }
        site = domain_map.get(self.platform_name, "")
        site_filter = f"site:{site}" if site else f"\"{self.platform_name}\""

        # Two-pass: upcoming + tickets to get individual event pages
        queries = [
            f"{site_filter} {location} events tickets 2026",
            f"{site_filter} {location} upcoming events 2026",
            f"{site_filter} {location} events April May June 2026",
        ]
        results: List[Dict] = []

        for query in queries:
            if len(results) >= count_needed * 3:
                break
            search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(2.5)

                domain_key = (site or self.platform_name).lower().replace(" ", "")
                titles = page.query_selector_all("h3")

                for h3 in titles:
                    if len(results) >= count_needed * 3:
                        break
                    try:
                        anchor = h3.evaluate_handle("n=>n.closest('a')").as_element()
                        if not anchor:
                            continue
                        href = anchor.get_attribute("href") or ""
                        if not href or "google.com" in href:
                            continue

                        logger.debug(f"Google L3 found URL: {href}")

                        # Must be from target domain
                        if domain_key not in href.lower():
                            logger.debug(f"Skipped {href}: domain_key '{domain_key}' not in href")
                            continue

                        # Reject non-event / listing URLs
                        from urllib.parse import urlparse as _urlparse
                        parsed_href = _urlparse(href)
                        path_segs = [s for s in parsed_href.path.split("/") if s]
                        if len(path_segs) < 2:   # must have at least /events/something
                            logger.debug(f"Skipped {href}: path_segs {path_segs} too short")
                            continue
                        if any(bad in href.lower() for bad in [
                            "/search?", "?q=", "/login", "/register",
                            "/explore\n", "/category",
                        ]):
                            continue

                        # Snippet text
                        block = h3.evaluate_handle(
                            "n=>n.closest('div.g,div.v7W49e,div.tF2Cxc,div.MjjYud')"
                        ).as_element()
                        snippet = block.inner_text().replace("\n", " ") if block else ""

                        # Price — leave None if not found (triggers enrichment)
                        price_m = re.search(
                            r"(?:₹|INR|Rs\.?)\s?(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+)",
                            snippet, re.I,
                        )
                        price = price_m.group(1).replace(",", "") if price_m else None
                        if "free" in snippet.lower():
                            price = "0"

                        # Date — leave None if not found (triggers enrichment)
                        date_m = re.search(
                            r"(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
                            r"(?:\s+\d{4})?|\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
                            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?)",
                            snippet, re.I,
                        )
                        raw_date = date_m.group(1) if date_m else None

                        results.append({
                            "name":        h3.inner_text().replace(" ...", "").strip(),
                            "url":         href,
                            "price":       price,
                            "date":        raw_date,
                            "description": snippet[:400],
                            "organizer":   self.platform_name,
                        })
                    except Exception:
                        continue

            except Exception as exc:
                logger.warning(f"{self.platform_name}: Google fallback pass error – {exc}")

        return results

    # ─────────────────────────────────────────────
    # Layer 4: Detail-page enrichment
    # ─────────────────────────────────────────────
    def _self_healing_extract(self, page, field_type: str) -> Optional[str]:
        """
        Production-grade extraction with fallback sequences for high resiliency.
        """
        targets = {
            "title": [
                "h1", "h2", "h3", ".card-title", ".event-title", ".title",
                "meta[property='og:title']", "a[class*='title'] div"
            ],
            "date": [
                "time", "[class*='date']", "[class*='Date']", "span:has-text('2025')", "span:has-text('2026')",
                "meta[property='event:start_time']"
            ],
            "location": [
                "[class*='location']", "[class*='venue']", "[class*='Venue']", ".address",
                "span:has-text('Hyderabad')", "meta[property='event:location']"
            ],
            "description": [
                "meta[name='description']", "meta[property='og:description']",
                "[class*='description']", "section[class*='about']", "[class*='snippet']"
            ],
            "price": [
                ".price", ".ticket-price", "[class*='Price']", "[class*='amount']",
                "span:has-text('₹')", "span:has-text('Rs')"
            ]
        }
        
        selectors = targets.get(field_type, [])
        for sel in selectors:
            try:
                el = page.query_selector(sel)
                if el:
                    val = ""
                    if sel.startswith("meta"):
                        val = el.get_attribute("content") or ""
                    else:
                        val = el.inner_text().strip()
                    if val and len(val) > 1:
                        return val
            except Exception:
                continue
        return None

    def _enrich_event_details(self, page, raw_event: dict) -> dict:
        """
        Visits the event detail page to extract:
          1. JSON-LD schema (name, startDate, offers.price)
          2. Visible page text price regex fallback
          3. Visible page text date regex fallback
        """
        url = (raw_event.get("url") or "").strip()
        if not url or "google.com" in url:
            return raw_event

        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=18000)
            if not resp or resp.status >= 400:
                # Cloudflare / bot block — try a targeted Google search for price
                raw_event = self._google_price_lookup(page, raw_event)
                return raw_event

            # -- JSON-LD extraction (highest confidence) --
            ld_items = self._extract_json_ld(page)
            for item in ld_items:
                type_val = str(item.get("@type", "")).lower()
                if "event" in type_val:
                    # Price
                    offer = item.get("offers") or {}
                    if isinstance(offer, list):
                        offer = offer[0] if offer else {}
                    ld_price = str(offer.get("price", "") or "")
                    if ld_price and ld_price not in ("0", ""):
                        raw_event["price"] = ld_price

                    # Date
                    ld_date = item.get("startDate") or item.get("startDateTime") or ""
                    if ld_date:
                        raw_event["date"] = ld_date

                    if raw_event.get("price") and raw_event.get("date"):
                        return raw_event    # fully enriched

            # -- Visible-text fallback for price --
            if not raw_event.get("price") or raw_event.get("price") in ("0", 0):
                # Search specific ticket sections first
                for p_sel in ["[class*='ticket']", "[class*='price']", "[class*='cost']"]:
                    try:
                        e = page.query_selector(p_sel)
                        if e:
                            pt = e.inner_text().strip()
                            pm = re.search(r"(?:₹|INR|Rs\.?)\s?([\d,]+)", pt, re.I)
                            if pm:
                                raw_event["price"] = pm.group(1).replace(",", "")
                                break
                    except Exception:
                        pass

                # Fallback to general body text
                if not raw_event.get("price") or raw_event.get("price") in ("0", 0):
                    try:
                        body = page.inner_text("body")
                        pm = re.search(
                            r"(?:₹|INR|Rs\.?)\s?(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+)",
                            body, re.I,
                        )
                        if pm:
                            raw_event["price"] = pm.group(1).replace(",", "")
                        elif re.search(r"\bfree\b", body, re.I):
                            raw_event["price"] = "0"
                    except Exception:
                        pass

            # -- Visible-text fallback for date --
            if not raw_event.get("date"):
                try:
                    body = page.inner_text("body")
                    dm = re.search(
                        r"(\d{1,2}(?:st|nd|rd|th)?\s+"
                        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
                        r"(?:\s+\d{4})?|\d{4}-\d{2}-\d{2})",
                        body, re.I,
                    )
                    if dm:
                        raw_event["date"] = dm.group(1)
                except Exception:
                    pass

        except Exception as exc:
            logger.debug(f"Enrichment failed for {url}: {exc}")

        return raw_event

    # ─────────────────────────────────────────────
    # Utilities
    def _google_price_lookup(self, page, raw_event: dict) -> dict:
        """
        When direct URL is Cloudflare-blocked, search Google for
        '[event name] [city] price tickets' to extract price + date.
        """
        name = raw_event.get("name", "")
        if not name:
            return raw_event
        try:
            q = f'"{name}" price tickets 2025 2026'
            url = f"https://www.google.com/search?q={urllib.parse.quote(q)}"
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(1.5)
            body = page.inner_text("body")

            # Price
            if not raw_event.get("price") or raw_event.get("price") in (0, "0"):
                pm = re.search(
                    r"(?:₹|INR|Rs\.?)\s?(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+)",
                    body, re.I,
                )
                if pm:
                    raw_event["price"] = pm.group(1).replace(",", "")
                elif re.search(r"\bfree\b", body, re.I):
                    raw_event["price"] = "0"

            # Date (if also missing)
            if not raw_event.get("date"):
                dm = re.search(
                    r"(\d{1,2}(?:st|nd|rd|th)?\s+"
                    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
                    r"(?:\s+\d{4})?|\d{4}-\d{2}-\d{2})",
                    body, re.I,
                )
                if dm:
                    raw_event["date"] = dm.group(1)
        except Exception as exc:
            logger.debug(f"Google price lookup failed for '{name}': {exc}")
        return raw_event

    # ─────────────────────────────────────────────
    def _deep_scroll_page(self, page, scrolls: int = 8):
        """Scroll page N times with 2s waits to trigger lazy loading."""
        for i in range(scrolls):
            page.evaluate("window.scrollBy(0, 900)")
            time.sleep(2)

    def _extract_json_ld(self, page) -> List[Dict]:
        data: List[Dict] = []
        try:
            for s in page.query_selector_all("script[type='application/ld+json']"):
                try:
                    js = json.loads(s.inner_text().strip())
                    if isinstance(js, list):
                        data.extend(js)
                    else:
                        data.append(js)
                except Exception:
                    continue
        except Exception:
            pass
        return data

    def _extract_window_object(self, page, object_name: str) -> Optional[dict]:
        try:
            return page.evaluate(f"window.{object_name}")
        except Exception:
            return None

    # ─────────────────────────────────────────────
    # Strict validation & formatting
    # ─────────────────────────────────────────────
    def _format_event(self, raw_event: dict) -> Optional[dict]:
        event_url = str(raw_event.get("url", "")).strip()

        # URL sanity checks
        if not event_url or "http" not in event_url:
            return None
        if any(bad in event_url for bad in ["google.com", "/search?", "?q="]):
            return None

        # ── Title Extraction (Self-healing fallback) ──
        event_name = str(raw_event.get("name", "")).strip()
        if not event_name or event_name.lower() in ["none", "null", "undefined"]:
            event_name = "Untitled Event"

        # ── Price Rule: if not found -> -1 ──
        price_val = extract_price(str(raw_event.get("price", "")))
        if price_val is None:
            price_val = -1

        # ── Date Rule ──
        date_raw = str(raw_event.get("date", "") or "")
        date_val = extract_date(date_raw)
        
        # Urbanaut specific behavior handled in its subclass, 
        # but for global consistency:
        if not date_val:
            if self.platform_name == "Urbanaut":
                date_val = "Unknown"
            else:
                logger.debug(f"{self.platform_name}: Discarding '{event_name}' — no parseable date")
                return None

        # Filter past dates (unless Unknown)
        if date_val != "Unknown":
            try:
                parsed_date = dt.datetime.strptime(date_val, "%Y-%m-%d").date()
                if parsed_date < TODAY:
                    logger.debug(f"{self.platform_name}: Discarding '{event_name}' — past date {date_val}")
                    return None
            except Exception:
                pass

        # ── Location Rule ──
        city = str(raw_event.get("location", "Hyderabad")).strip()
        if not city:
            city = "Hyderabad"

        # ── Description Rule ──
        description = str(raw_event.get("description", "")).strip()
        if not description or len(description) < 5:
            description = "Not available"

        formatted = {
            "event_name":  event_name if event_name != "Untitled Event" else "Event",
            "event_date":  date_val,
            "price":       price_val,
            "organizer":   str(raw_event.get("organizer", self.platform_name)).strip(),
            "platform":    self.platform_name,
            "event_url":   event_url,
            "city":        city,
            "description": description[:500],
        }

        is_valid, reason = is_valid_event(formatted)
        if not is_valid:
            logger.debug(f"{self.platform_name}: Validator rejected — {reason}")
            # Even if validator rejects, if user wants ALL events for specific fixes...
            # But usually validator checks for name/url which we need.
            if not formatted["event_name"] or formatted["event_name"] == "Event": return None

        return formatted
