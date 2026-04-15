import asyncio
import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from agents.platforms import get_platform_agent

PLATFORMS_TO_TEST = [
    "Sort My Scene",
    "Urbanaut",
    "Mera Events",
    "Skillbox",
    "Swiggy Scenes"
]

async def test_all():
    sep = "=" * 65
    print(f"\n{sep}")
    print("PRODUCTION FIX VERIFICATION -- Hyderabad")
    print(sep)

    total_pass = 0
    total_fail = 0

    for platform in PLATFORMS_TO_TEST:
        print(f"\n[{platform}] Testing...")
        agent = get_platform_agent(platform, "Hyderabad")
        if not agent:
            print(f"  ERROR: No agent found for {platform}")
            total_fail += 1
            continue
        try:
            # Test small count for speed
            events = await agent.extract_events("Hyderabad", 3)
            if not events:
                print(f"  FAIL: 0 events returned")
                total_fail += 1
            else:
                print(f"  PASS: {len(events)} events:")
                for ev in events:
                    # UPDATED SCHEMA KEYS
                    title = (ev.get("title") or "N/A")[:55]
                    date  = ev.get("date", "N/A")
                    price = ev.get("price", "?")
                    loc   = ev.get("location", "N/A")
                    url   = ev.get("event_url", "N/A")[:60]
                    desc  = (ev.get("description") or "")[:60]
                    
                    print(f"    - {title}")
                    print(f"      {date} | {loc} | INR {price}")
                    print(f"      {url}")
                    print(f"      Desc: {desc}")
                total_pass += 1
        except Exception as exc:
            print(f"  ERROR: {exc}")
            total_fail += 1

    print(f"\n{sep}")
    print(f"RESULT: {total_pass}/{len(PLATFORMS_TO_TEST)} platforms PASSED")
    print(sep)

if __name__ == "__main__":
    asyncio.run(test_all())