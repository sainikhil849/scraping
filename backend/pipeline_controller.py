import logging
import asyncio
from typing import List, Dict, Optional

from agents.platforms import get_platform_agent
from utils.validators import deduplicate

logger = logging.getLogger(__name__)

# All supported platforms (canonical names used by get_platform_agent)
ALL_PLATFORMS = [
    "BookMyShow",
    "District",
    "Swiggy Scenes",
    "Skillbox",
    "Sort My Scene",
    "Mera Events",
    "Urbanaut",
    "Meetup",
]


class PipelineController:
    async def run_pipeline(
        self,
        location: str,
        max_events: int,
        target_platforms: List[str],
        category: Optional[str] = None,
        max_price: Optional[int] = None,
    ) -> List[Dict]:
        """
        Orchestrates multi-platform event extraction using the BaseAgent pipeline.
        Each platform runs in its own thread (non-blocking for FastAPI).
        """
        logger.info(
            f"Pipeline started: location={location}, max={max_events}, "
            f"platforms={target_platforms}"
        )

        # Resolve platform list
        if not target_platforms or "All Platforms" in target_platforms:
            platforms_to_run = ALL_PLATFORMS
        else:
            platforms_to_run = [
                p for p in target_platforms if get_platform_agent(p, location) is not None
            ]

        if not platforms_to_run:
            logger.warning("No valid platforms found.")
            return []

        # Fair per-platform budget
        per_platform = max(2, max_events // len(platforms_to_run))

        # Run each platform concurrently in thread pool
        async def _run_one(platform: str) -> List[Dict]:
            agent = get_platform_agent(platform, location)
            if not agent:
                return []
            try:
                return await agent.extract_events(location, per_platform, max_price)
            except Exception as exc:
                logger.error(f"{platform}: extraction error – {exc}")
                return []

        tasks = [_run_one(p) for p in platforms_to_run]
        results_nested = await asyncio.gather(*tasks, return_exceptions=False)

        # Flatten, deduplicate, apply global limit
        all_events: List[Dict] = []
        for batch in results_nested:
            all_events.extend(batch)

        # Deduplicate by (event_name + event_date + event_url)
        all_events = deduplicate(all_events)

        # Apply max_price filter if set
        if max_price is not None:
            all_events = [e for e in all_events if e.get("price", 0) <= max_price]

        logger.info(f"Pipeline complete: {len(all_events)} total events collected.")
        return all_events[:max_events]
