import asyncio
import logging
from pipeline_controller import PipelineController

# Setup logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_system():
    controller = PipelineController()
    
    print("\n--- STARTING VERIFICATION (HYDERABAD) ---\n")
    
    # Test request for 5 events from Hyderabad
    # We use a subset of platforms to speed up verification
    target_platforms = ["BookMyShow", "District"]
    
    try:
        results = await controller.run_pipeline(
            location="Hyderabad",
            category="Comedy",
            max_events=5,
            max_price=None,
            target_platforms=target_platforms
        )
        
        print(f"\nTotal Events Collected: {results['total_events']}")
        print(f"Platforms Successfully Used: {results['platforms_used']}")
        
        print("\n--- SAMPLE EVENTS ---")
        for ev in results['events']:
            print(f"[{ev['platform']}] {ev['event_name']} | {ev['event_date']} | ₹{ev['price']}")
            print(f"   URL: {ev['event_url']}")
            
        if results['total_events'] > 0:
            print("\nSUCCESS: Events retrieved without Windows NotImplementedError.")
        else:
            print("\nWARNING: No events found, but code executed successfully (no crash).")
            
    except Exception as e:
        print(f"\nFAILED: System encountered an error: {e}")
        logger.exception(e)

if __name__ == "__main__":
    asyncio.run(verify_system())
