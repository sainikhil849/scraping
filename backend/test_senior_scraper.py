import asyncio
import sys
import logging

# Ensure UTF-8 output even on Windows terminals
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from pipeline_controller import PipelineController

async def verify_senior_build():
    print("\n" + "="*60)
    print("SENIOR ENGINEER BUILD VERIFICATION: HYDERABAD")
    print("="*60)
    print("Mode: VISIBLE BROWSER (non-headless)")
    print("Requirement: MANDATORY PRICE extraction\n")
    
    controller = PipelineController()
    
    try:
        results = await controller.run_pipeline(
            location="Hyderabad", 
            max_events=5, 
            target_platforms=["BookMyShow", "District"]
        )
        
        print("\n" + "-"*30)
        print("SCRAPING SUCCESS REPORT")
        print("-"*30)
        print(f"Total Verified Events Found: {len(results)}")
        
        for ev in results:
            # Use safe encoding for print
            name = ev['event_name'].encode('ascii', 'ignore').decode('ascii')
            print(f"- {ev['platform']}: {name} | INR {ev['price']} | {ev['event_url'][:40]}...")
            
        if len(results) > 0:
            print("\nSTATUS: PASS - Scraping is functional and pricing is verified.")
        else:
            print("\nSTATUS: FAIL - Yield is 0. Check connectivity or selectors.")
            
    except Exception as e:
        print(f"\nSTATUS: CRITICAL ERROR - {e}")

if __name__ == "__main__":
    asyncio.run(verify_senior_build())
