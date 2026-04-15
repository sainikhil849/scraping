import asyncio
import logging
from agents.platforms import get_platform_agent

logging.basicConfig(level=logging.INFO)

async def test_u():
    agent = get_platform_agent("Urbanaut", "Hyderabad")
    res = await agent.extract_events("Hyderabad", 3)
    print("Results:", res)

if __name__ == "__main__":
    asyncio.run(test_u())
