import asyncio
import logging
from agents.platforms import get_platform_agent

logging.basicConfig(level=logging.DEBUG)

async def t():
    a = get_platform_agent("Skillbox", "Hyderabad")
    res = await a.extract_events("Hyderabad", 3)
    print("RESULTS:", res)

if __name__ == "__main__":
    asyncio.run(t())
